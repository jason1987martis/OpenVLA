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


WINDOW_MAIN = "Single Red Object Detection"
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
    print("Single Red Object Detection")
    print("===================================================")
    print("Q = quit")
    print("S = save current frame")
    print("===================================================")

    frame_count = 0

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

        if detections:
            best = detections[0]
            draw_detection(output, best, label="RED-1")

            status = [
                "Single Red Object Detection",
                f"Detected: YES",
                f"Pixel: u={best['u']}, v={best['v']}",
                f"Area: {best['area']:.0f}",
                f"Aspect: {best['aspect_ratio']:.2f}",
                f"Circularity: {best['circularity']:.2f}",
                "Q=quit | S=save frame",
            ]
        else:
            status = [
                "Single Red Object Detection",
                "Detected: NO",
                "Tune HSV/brightness/area sliders.",
                "Q=quit | S=save frame",
            ]

        draw_text_panel(output, status)

        cv2.imshow(WINDOW_MAIN, output)
        cv2.imshow(WINDOW_MASK, mask)

        key = cv2.waitKey(1) & 0xFF

        if key == ord("q"):
            break

        elif key == ord("s"):
            frame_count += 1
            filename = f"single_detection_{frame_count:03d}.png"
            cv2.imwrite(filename, output)
            print(f"[SAVED] {filename}")

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()