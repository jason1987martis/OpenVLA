import csv
import json
import os
import time
from datetime import datetime

from pydobotplus import Dobot


# ==============================================================================
# CONFIG
# ==============================================================================

DOBOT_PORT = "COM8"

CSV_FILE = "recorded_robot_points.csv"
JSON_FILE = "recorded_robot_points.json"


# ==============================================================================
# DOBOT HELPERS
# ==============================================================================

def get_current_pose(device):
    """
    Reads current Dobot coordinates.

    Different pydobotplus versions may use:
    - device.pose()
    - device.get_pose()

    This function tries both.
    """

    if hasattr(device, "pose"):
        return device.pose()

    if hasattr(device, "get_pose"):
        return device.get_pose()

    raise AttributeError("No pose method found. Tried device.pose() and device.get_pose().")


def extract_pose_values(pose):
    """
    Converts Dobot pose object into x, y, z, r values.
    """

    if hasattr(pose, "x"):
        return float(pose.x), float(pose.y), float(pose.z), float(pose.r)

    # fallback if pose is tuple/list
    if isinstance(pose, (tuple, list)) and len(pose) >= 4:
        return float(pose[0]), float(pose[1]), float(pose[2]), float(pose[3])

    raise ValueError(f"Unsupported pose format: {pose}")


# ==============================================================================
# FILE HELPERS
# ==============================================================================

def load_existing_points():
    """
    Loads existing JSON points if available.
    This allows you to continue recording later.
    """

    if not os.path.exists(JSON_FILE):
        return []

    try:
        with open(JSON_FILE, "r", encoding="utf-8") as f:
            points = json.load(f)

        if isinstance(points, list):
            return points

    except Exception:
        pass

    return []


def save_json(points):
    with open(JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(points, f, indent=4)


def save_csv(points):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        writer.writerow([
            "point_id",
            "timestamp",
            "x",
            "y",
            "z",
            "r"
        ])

        for point in points:
            writer.writerow([
                point["point_id"],
                point["timestamp"],
                point["x"],
                point["y"],
                point["z"],
                point["r"]
            ])


def save_points(points):
    save_json(points)
    save_csv(points)


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    device = None

    print("===================================================")
    print("Dobot Manual Coordinate Recorder")
    print("===================================================")
    print()
    print("Instructions:")
    print("1. Connect Dobot.")
    print("2. Run this script.")
    print("3. Unlock/free-move the Dobot manually.")
    print("4. Move Dobot tip to the required point.")
    print("5. Press ENTER to record the current coordinates.")
    print("6. Repeat for next points.")
    print("7. Type q and press ENTER to quit.")
    print()
    print("Output files:")
    print(f"- {CSV_FILE}")
    print(f"- {JSON_FILE}")
    print("===================================================")
    print()

    points = load_existing_points()

    if points:
        print(f"[INFO] Loaded {len(points)} existing points.")
        print("[INFO] New points will continue from next number.")
        print()

    try:
        print(f"[DOBOT] Connecting to {DOBOT_PORT}...")
        device = Dobot(port=DOBOT_PORT)
        time.sleep(1)

        try:
            device.clear_alarms()
        except Exception:
            pass

        print("[DOBOT] Connected.")
        print()

        print("Now manually unlock/free-move the Dobot.")
        print("Do not force the arm. Use the Dobot unlock button/manual mode.")
        print()

        while True:
            next_id = len(points) + 1

            user_input = input(
                f"Move Dobot to point {next_id}, then press ENTER to record "
                f"or type q to quit: "
            ).strip().lower()

            if user_input == "q":
                print("[INFO] Quit requested.")
                break

            try:
                pose = get_current_pose(device)
                x, y, z, r = extract_pose_values(pose)

                point = {
                    "point_id": next_id,
                    "timestamp": datetime.now().isoformat(timespec="seconds"),
                    "x": round(x, 4),
                    "y": round(y, 4),
                    "z": round(z, 4),
                    "r": round(r, 4)
                }

                points.append(point)
                save_points(points)

                print()
                print(f"[RECORDED] Point {next_id}")
                print(f"X = {x:.2f}")
                print(f"Y = {y:.2f}")
                print(f"Z = {z:.2f}")
                print(f"R = {r:.2f}")
                print(f"[SAVED] {CSV_FILE}")
                print(f"[SAVED] {JSON_FILE}")
                print()

            except Exception as e:
                print(f"[ERROR] Could not record pose: {e}")
                print()

    except Exception as e:
        print(f"[DOBOT ERROR] {e}")

    finally:
        if device is not None:
            try:
                device.close()
            except Exception:
                pass

        print()
        print("[DONE] Dobot connection closed.")
        print(f"[DONE] Total recorded points: {len(points)}")


if __name__ == "__main__":
    main()