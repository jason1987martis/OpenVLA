import cv2
import numpy as np

from cv_common import (
    CAMERA_INDEX,
    DISPLAY_W,
    DISPLAY_H,
    create_red_controls,
    get_red_controls,
    resize_frame,
    adjust_brightness_contrast,
    detect_red_objects,
    draw_detection,
    draw_text_panel,
    load_homography,
    pixel_to_robot,
    robot_to_pixel,
)


WINDOW_MAIN = "Workspace Boundary Overlay"
WINDOW_MASK = "Red Mask"
WINDOW_CONTROLS = "Controls"


# ==============================================================================
# SAFE ROBOT WORKSPACE
# Change these values based on your actual safe Dobot region.
# ==============================================================================

X_MIN = 180.0
X_MAX = 310.0

Y_MIN = -120.0
Y_MAX = 120.0


ROBOT_WORKSPACE_CORNERS = [
    [X_MIN, Y_MIN],
    [X_MAX, Y_MIN],
    [X_MAX, Y_MAX],
    [X_MIN, Y_MAX],
]


def robot_workspace_to_pixel_polygon(H):
    pixel_points = []

    for x, y in ROBOT_WORKSPACE_CORNERS:
        u, v = robot_to_pixel(H, x, y)
        pixel_points.append([int(round(u)), int(round(v))])

    return np.array(pixel_points, dtype=np.int32)


def draw_workspace(frame, pixel_polygon):
    overlay = frame.copy()

    cv2.fillPoly(
        overlay,
        [pixel_polygon],
        color=(0, 120, 0)
    )

    frame[:] = cv2.addWeighted(overlay, 0.25, frame, 0.75, 0)

    cv2.polylines(
        frame,
        [pixel_polygon],
        isClosed=True,
        color=(0, 255, 0),
        thickness=3
    )

    for i, point in enumerate(pixel_polygon):
        u, v = point
        cv2.circle(frame, (u, v), 6, (0, 255, 0), -1)
        cv2.putText(
            frame,
            f"W{i + 1}",
            (u + 8, v - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            (0, 255, 0),
            2
        )


def is_robot_xy_inside_workspace(x, y):
    return X_MIN <= x <= X_MAX and Y_MIN <= y <= Y_MAX


def main():
    try:
        H = load_homography()
        pixel_polygon = robot_workspace_to_pixel_polygon(H)

        print("[OK] Homography loaded.")
        print("[OK] Workspace pixel polygon:")
        print(pixel_polygon)

    except Exception as e:
        print(f"[ERROR] {e}")
        return

    cap = cv2.VideoCapture(CAMERA_INDEX)

    if not cap.isOpened():
        print("[ERROR] Could not open camera.")
        return

    create_red_controls(WINDOW_CONTROLS)

    cv2.namedWindow(WINDOW_MAIN, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_MAIN, DISPLAY_W, DISPLAY_H)

    cv2.namedWindow(WINDOW_MASK, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_MASK, 480, 360)

    print("===================================================")
    print("Workspace Boundary Overlay")
    print("===================================================")
    print("Q = quit")
    print("S = save frame")
    print("Green area = safe robot workspace")
    print("===================================================")

    save_count = 0

    while True:
        ret, frame = cap.read()

        if not ret:
            print("[WARNING] Frame grab failed.")
            continue

        frame = resize_frame(frame)

        controls = get_red_controls(WINDOW_CONTROLS)

        frame = adjust_brightness_contrast(
            frame,
            brightness=controls["brightness"],
            contrast=controls["contrast"]
        )

        detections, mask = detect_red_objects(frame, controls)

        output = frame.copy()

        draw_workspace(output, pixel_polygon)

        if detections:
            best = detections[0]

            x_robot, y_robot = pixel_to_robot(H, best["u"], best["v"])
            inside = is_robot_xy_inside_workspace(x_robot, y_robot)

            color = (0, 255, 0) if inside else (0, 0, 255)
            label = "INSIDE" if inside else "OUTSIDE"

            draw_detection(
                output,
                best,
                label=label,
                color=color
            )

            cv2.putText(
                output,
                f"Mapped XY: X={x_robot:.2f}, Y={y_robot:.2f}",
                (12, DISPLAY_H - 65),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

            cv2.putText(
                output,
                f"Workspace Status: {label}",
                (12, DISPLAY_H - 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                color,
                2
            )

        status = [
            "Workspace Boundary Overlay",
            f"Robot workspace: X {X_MIN} to {X_MAX}, Y {Y_MIN} to {Y_MAX}",
            "Green polygon = safe workspace",
            "Red target label = outside workspace",
            "Q=quit | S=save frame",
        ]

        draw_text_panel(output, status)

        cv2.imshow(WINDOW_MAIN, output)
        cv2.imshow(WINDOW_MASK, mask)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("s"):
            save_count += 1
            filename = f"workspace_overlay_{save_count:03d}.png"
            cv2.imwrite(filename, output)
            print(f"[SAVED] {filename}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()