from __future__ import annotations

import argparse
import json
import time
from datetime import datetime
from pathlib import Path
from typing import List


DEFAULT_DATASET_NAME = "dobot_trajectory_dataset.json"
DEFAULT_IMAGE_ROOT = "images"


def parse_args() -> argparse.Namespace:
    script_dir = Path(__file__).resolve().parent

    parser = argparse.ArgumentParser(
        description="Record a multi-step Dobot demonstration as many single-step training samples."
    )
    parser.add_argument(
        "--instruction",
        required=True,
        help="Task instruction that will be stored with every sample in the demonstration.",
    )
    parser.add_argument(
        "--waypoints",
        type=Path,
        required=True,
        help="Path to a waypoint JSON file. See trajectory_waypoints_example.json for the format.",
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=script_dir / DEFAULT_DATASET_NAME,
        help="Dataset JSON file to create or append to.",
    )
    parser.add_argument(
        "--image-root",
        default=DEFAULT_IMAGE_ROOT,
        help="Folder, relative to the dataset JSON file, where demonstration images will be stored.",
    )
    parser.add_argument(
        "--demo-name",
        default=None,
        help="Optional folder name for this demonstration. Defaults to a timestamp.",
    )
    parser.add_argument(
        "--camera-index",
        type=int,
        default=0,
        help="OpenCV camera index.",
    )
    parser.add_argument(
        "--camera-warmup-frames",
        type=int,
        default=10,
        help="Number of initial frames to discard before recording starts.",
    )
    parser.add_argument(
        "--settle-seconds",
        type=float,
        default=0.5,
        help="Pause after each executed waypoint so the scene settles before the next capture.",
    )
    parser.add_argument(
        "--robot-port",
        default=None,
        help="Optional serial port for the Dobot. If omitted, the first detected port is used.",
    )
    parser.add_argument(
        "--move-robot",
        action="store_true",
        help="Actually connect to the Dobot and execute the waypoint actions.",
    )
    parser.add_argument(
        "--speed-velocity",
        type=float,
        default=None,
        help="Optional Dobot velocity setting passed to robot.speed().",
    )
    parser.add_argument(
        "--speed-acceleration",
        type=float,
        default=None,
        help="Optional Dobot acceleration setting passed to robot.speed().",
    )
    parser.add_argument(
        "--x-min",
        type=float,
        default=150.0,
        help="Minimum allowed X value for a recorded waypoint.",
    )
    parser.add_argument(
        "--x-max",
        type=float,
        default=320.0,
        help="Maximum allowed X value for a recorded waypoint.",
    )
    parser.add_argument(
        "--y-min",
        type=float,
        default=-180.0,
        help="Minimum allowed Y value for a recorded waypoint.",
    )
    parser.add_argument(
        "--y-max",
        type=float,
        default=180.0,
        help="Maximum allowed Y value for a recorded waypoint.",
    )
    parser.add_argument(
        "--z-min",
        type=float,
        default=0.0,
        help="Minimum allowed Z value for a recorded waypoint.",
    )
    parser.add_argument(
        "--z-max",
        type=float,
        default=120.0,
        help="Maximum allowed Z value for a recorded waypoint.",
    )
    parser.add_argument(
        "--r-min",
        type=float,
        default=-180.0,
        help="Minimum allowed R value for a recorded waypoint.",
    )
    parser.add_argument(
        "--r-max",
        type=float,
        default=180.0,
        help="Maximum allowed R value for a recorded waypoint.",
    )
    return parser.parse_args()


def load_json_list(path: Path) -> List[dict]:
    if not path.exists():
        return []

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list):
        raise ValueError(f"Dataset file must contain a JSON list: {path}")
    return data


def save_json_list(path: Path, items: List[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(items, handle, indent=2)


def load_waypoints(path: Path) -> List[dict]:
    if not path.is_file():
        raise FileNotFoundError(f"Waypoint file not found: {path}")

    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)

    if not isinstance(data, list) or not data:
        raise ValueError("Waypoint file must contain a non-empty JSON list.")

    normalized_waypoints: List[dict] = []
    for index, item in enumerate(data):
        if not isinstance(item, dict):
            raise ValueError(f"Waypoint {index} must be a JSON object.")

        required_keys = ("x", "y", "z", "r", "suction")
        for key in required_keys:
            if key not in item:
                raise ValueError(f"Waypoint {index} is missing required key: {key}")
            if not isinstance(item[key], (int, float)):
                raise ValueError(f"Waypoint {index} field {key} must be numeric.")

        suction = float(item["suction"])
        if suction not in (0.0, 1.0):
            raise ValueError(f"Waypoint {index} suction must be 0 or 1, but received {suction}.")

        normalized_waypoints.append(
            {
                "x": float(item["x"]),
                "y": float(item["y"]),
                "z": float(item["z"]),
                "r": float(item["r"]),
                "suction": suction,
                "note": str(item.get("note", "")),
            }
        )

    return normalized_waypoints


def validate_waypoint_bounds(waypoint: dict, args: argparse.Namespace, index: int) -> None:
    if not args.x_min <= waypoint["x"] <= args.x_max:
        raise ValueError(f"Waypoint {index} X={waypoint['x']} is outside [{args.x_min}, {args.x_max}].")
    if not args.y_min <= waypoint["y"] <= args.y_max:
        raise ValueError(f"Waypoint {index} Y={waypoint['y']} is outside [{args.y_min}, {args.y_max}].")
    if not args.z_min <= waypoint["z"] <= args.z_max:
        raise ValueError(f"Waypoint {index} Z={waypoint['z']} is outside [{args.z_min}, {args.z_max}].")
    if not args.r_min <= waypoint["r"] <= args.r_max:
        raise ValueError(f"Waypoint {index} R={waypoint['r']} is outside [{args.r_min}, {args.r_max}].")


def make_demo_name(user_value: str | None) -> str:
    if user_value:
        return user_value
    return datetime.now().strftime("demo_%Y%m%d_%H%M%S")


def connect_robot(args: argparse.Namespace):
    from serial.tools import list_ports
    from pydobot import Dobot

    port = args.robot_port
    if port is None:
        available_ports = list(list_ports.comports())
        if not available_ports:
            raise RuntimeError("No serial ports were detected for the Dobot.")
        port = available_ports[0].device

    robot = Dobot(port=port, verbose=True)

    if args.speed_velocity is not None and args.speed_acceleration is not None:
        robot.speed(args.speed_velocity, args.speed_acceleration)
    elif args.speed_velocity is not None or args.speed_acceleration is not None:
        raise ValueError("Provide both --speed-velocity and --speed-acceleration together.")

    return robot


def main() -> None:
    args = parse_args()

    import cv2

    dataset_path = args.dataset.resolve()
    dataset_root = dataset_path.parent
    waypoints = load_waypoints(args.waypoints.resolve())
    demo_name = make_demo_name(args.demo_name)
    image_dir = dataset_root / args.image_root / demo_name
    dataset_samples = load_json_list(dataset_path)

    for index, waypoint in enumerate(waypoints):
        validate_waypoint_bounds(waypoint, args, index)

    cap = cv2.VideoCapture(args.camera_index)
    if not cap.isOpened():
        raise RuntimeError(f"Could not open camera index {args.camera_index}.")

    for _ in range(max(args.camera_warmup_frames, 0)):
        cap.read()

    robot = None
    if args.move_robot:
        robot = connect_robot(args)
        print("Connected to Dobot. Recording live trajectory.")
    else:
        print(
            "Running without --move-robot. The script will capture frames and write dataset samples, "
            "but it will not execute the waypoint actions."
        )

    image_dir.mkdir(parents=True, exist_ok=True)

    try:
        for step_index, waypoint in enumerate(waypoints, start=1):
            # Record the current observation before executing the next action.
            ret, frame = cap.read()
            if not ret:
                raise RuntimeError(f"Failed to capture frame for step {step_index}.")

            image_path = image_dir / f"frame_{step_index:06d}.jpg"
            if not cv2.imwrite(str(image_path), frame):
                raise RuntimeError(f"Failed to save image: {image_path}")

            relative_image_path = image_path.relative_to(dataset_root).as_posix()
            action = [
                waypoint["x"],
                waypoint["y"],
                waypoint["z"],
                waypoint["r"],
                waypoint["suction"],
            ]

            dataset_samples.append(
                {
                    "image": relative_image_path,
                    "instruction": args.instruction.strip(),
                    "action": action,
                }
            )
            save_json_list(dataset_path, dataset_samples)

            print(
                f"Recorded step {step_index}/{len(waypoints)} | "
                f"image={relative_image_path} | action={action}"
            )
            if waypoint["note"]:
                print(f"  note: {waypoint['note']}")

            if robot is not None:
                robot.move_to(
                    x=waypoint["x"],
                    y=waypoint["y"],
                    z=waypoint["z"],
                    r=waypoint["r"],
                    wait=True,
                )
                robot.suck(bool(waypoint["suction"]))
                time.sleep(max(args.settle_seconds, 0.0))

    finally:
        cap.release()
        if robot is not None:
            robot.close()

    print(f"Saved {len(waypoints)} new samples to {dataset_path}")


if __name__ == "__main__":
    main()
