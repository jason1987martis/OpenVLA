# This tests your homography accuracy.

# Before running this, you should already have:

# calibration_points.json

# or:

# homography.npy

# Workflow:

# 1. Place red cube at a known robot coordinate.
# 2. Type actual robot X/Y in the terminal.
# 3. Press R in the OpenCV window.
# 4. Script detects red pixel, maps pixel -> Dobot XY.
# 5. It calculates error in mm.
# 6. Saves result to mapping_accuracy_results.csv.


import math
import cv2

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
    append_csv_row,
    now_timestamp,
)


WINDOW_MAIN = "Mapping Accuracy Test"
WINDOW_MASK = "Red Mask"
WINDOW_CONTROLS = "Controls"

RESULTS_CSV = "mapping_accuracy_results.csv"


def ask_actual_xy():
    while True:
        try:
            raw = input("Enter actual robot X,Y for this test point: ").strip()
            parts = raw.replace(",", " ").split()

            if len(parts) != 2:
                print("Enter like: 230,0")
                continue

            x = float(parts[0])
            y = float(parts[1])

            return x, y

        except ValueError:
            print("Invalid number. Try again.")


def main():
    try:
        H = load_homography()
        print("[OK] Homography loaded.")
        print(H)
    except Exception as e:
        print(f"[ERROR] {e}")
        return

    actual_x, actual_y = ask_actual_xy()

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
    print("Mapping Accuracy Test")
    print("===================================================")
    print("R = record current detected point")
    print("N = enter next actual robot X/Y")
    print("Q = quit")
    print("===================================================")

    errors = []
    test_id = 0

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

        predicted_x = None
        predicted_y = None
        current_error = None

        if detections:
            best = detections[0]
            draw_detection(output, best, label="TEST TARGET")

            predicted_x, predicted_y = pixel_to_robot(H, best["u"], best["v"])

            current_error = math.sqrt(
                (predicted_x - actual_x) ** 2 +
                (predicted_y - actual_y) ** 2
            )

            cv2.putText(
                output,
                f"Predicted XY: X={predicted_x:.2f}, Y={predicted_y:.2f}",
                (12, DISPLAY_H - 75),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

            cv2.putText(
                output,
                f"Error: {current_error:.2f} mm",
                (12, DISPLAY_H - 45),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 255),
                2
            )

        average_error = sum(errors) / len(errors) if errors else 0.0

        status = [
            "Mapping Accuracy Test",
            f"Actual XY: X={actual_x:.2f}, Y={actual_y:.2f}",
            f"Recorded tests: {len(errors)}",
            f"Average error: {average_error:.2f} mm",
            "R=record | N=next actual XY | Q=quit",
        ]

        draw_text_panel(output, status)

        cv2.imshow(WINDOW_MAIN, output)
        cv2.imshow(WINDOW_MASK, mask)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("n"):
            actual_x, actual_y = ask_actual_xy()

        elif key == ord("r"):
            if not detections:
                print("[WARNING] No red object detected. Cannot record.")
                continue

            best = detections[0]
            predicted_x, predicted_y = pixel_to_robot(H, best["u"], best["v"])

            error = math.sqrt(
                (predicted_x - actual_x) ** 2 +
                (predicted_y - actual_y) ** 2
            )

            test_id += 1
            errors.append(error)

            append_csv_row(
                RESULTS_CSV,
                [
                    "test_id",
                    "timestamp",
                    "pixel_u",
                    "pixel_v",
                    "actual_x",
                    "actual_y",
                    "predicted_x",
                    "predicted_y",
                    "error_mm",
                ],
                [
                    test_id,
                    now_timestamp(),
                    best["u"],
                    best["v"],
                    actual_x,
                    actual_y,
                    round(predicted_x, 4),
                    round(predicted_y, 4),
                    round(error, 4),
                ]
            )

            print()
            print(f"[RECORDED] Test {test_id}")
            print(f"Pixel       : u={best['u']}, v={best['v']}")
            print(f"Actual XY   : X={actual_x:.2f}, Y={actual_y:.2f}")
            print(f"Predicted XY: X={predicted_x:.2f}, Y={predicted_y:.2f}")
            print(f"Error       : {error:.2f} mm")
            print(f"[SAVED] {RESULTS_CSV}")
            print()

    cap.release()
    cv2.destroyAllWindows()

    if errors:
        print("===================================================")
        print("Final Mapping Accuracy Report")
        print("===================================================")
        print(f"Tests recorded : {len(errors)}")
        print(f"Average error  : {sum(errors) / len(errors):.2f} mm")
        print(f"Minimum error  : {min(errors):.2f} mm")
        print(f"Maximum error  : {max(errors):.2f} mm")
        print("===================================================")


if __name__ == "__main__":
    main()