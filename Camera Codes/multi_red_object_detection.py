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
)


WINDOW_MAIN = "Multi Red Object Detection"
WINDOW_MASK = "Red Mask"
WINDOW_CONTROLS = "Controls"


def main():
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
    print("Multi Red Object Detection")
    print("===================================================")
    print("Q = quit")
    print("S = save frame")
    print("Objects are sorted by area, largest first.")
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

        for index, detection in enumerate(detections, start=1):
            draw_detection(
                output,
                detection,
                label=f"RED-{index}",
                color=(0, 255, 0)
            )

            cv2.putText(
                output,
                str(index),
                (detection["u"] + 10, detection["v"] + 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (255, 255, 0),
                2
            )

        status = [
            "Multi Red Object Detection",
            f"Objects found: {len(detections)}",
            "Largest object is RED-1.",
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
            filename = f"multi_detection_{save_count:03d}.png"
            cv2.imwrite(filename, output)
            print(f"[SAVED] {filename}")

            for index, detection in enumerate(detections, start=1):
                print(
                    f"Object {index}: "
                    f"u={detection['u']}, "
                    f"v={detection['v']}, "
                    f"area={detection['area']:.0f}, "
                    f"aspect={detection['aspect_ratio']:.2f}, "
                    f"circularity={detection['circularity']:.2f}, "
                    f"angle={detection['angle']:.2f}"
                )

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()