#-----------------------------
# How to run
#1. Keep homography.npy in the same folder.
#2. Put red block in camera view.
#3. Run the code.
#4. Press m to move Dobot to the detected block.
#5. Press q to quit.
#-----------------------------


import cv2
import numpy as np
from serial.tools import list_ports
from pydobot import Dobot

# -----------------------------
# Load calibration matrix
# -----------------------------
H = np.load("homography.npy")

def pixel_to_dobot(u, v):
    point = np.array([[[u, v]]], dtype=np.float32)
    robot_point = cv2.perspectiveTransform(point, H)

    x = float(robot_point[0][0][0])
    y = float(robot_point[0][0][1])

    return x, y


# -----------------------------
# Detect colored block
# Example: red block
# -----------------------------
def find_red_block(frame):
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([0, 100, 100])
    upper_red1 = np.array([10, 255, 255])

    lower_red2 = np.array([160, 100, 100])
    upper_red2 = np.array([179, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    mask = mask1 + mask2

    mask = cv2.erode(mask, None, iterations=2)
    mask = cv2.dilate(mask, None, iterations=2)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    if not contours:
        return None, mask

    largest = max(contours, key=cv2.contourArea)

    if cv2.contourArea(largest) < 500:
        return None, mask

    M = cv2.moments(largest)

    if M["m00"] == 0:
        return None, mask

    u = int(M["m10"] / M["m00"])
    v = int(M["m01"] / M["m00"])

    return (u, v), mask


# -----------------------------
# Dobot movement
# -----------------------------
def move_dobot_to_block(robot, x, y):
    safe_z = 80
    pick_z = 25
    r = 0

    # Safety limits for Dobot Magician
    if not (150 <= x <= 320):
        raise ValueError(f"Unsafe X value: {x}")

    if not (-180 <= y <= 180):
        raise ValueError(f"Unsafe Y value: {y}")

    print(f"Moving to X={x:.2f}, Y={y:.2f}")

    robot.move_to(x, y, safe_z, r, wait=True)
    robot.move_to(x, y, pick_z, r, wait=True)

    # suction on
    robot.suck(True)

    robot.move_to(x, y, safe_z, r, wait=True)


# -----------------------------
# Main program
# -----------------------------
def main():
    # Connect camera
    cap = cv2.VideoCapture(0)

    if not cap.isOpened():
        raise RuntimeError("Camera not found")

    # Connect Dobot
    port = list_ports.comports()[0].device
    robot = Dobot(port=port, verbose=True)

    print("Connected to Dobot")

    # Optional but recommended
    # robot.home()

    while True:
        ret, frame = cap.read()

        if not ret:
            print("Failed to read camera")
            break

        center, mask = find_red_block(frame)

        if center is not None:
            u, v = center

            cv2.circle(frame, (u, v), 8, (0, 255, 0), -1)
            cv2.putText(
                frame,
                f"Pixel: {u},{v}",
                (u + 10, v),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

            x, y = pixel_to_dobot(u, v)

            cv2.putText(
                frame,
                f"Dobot: {x:.1f},{y:.1f}",
                (u + 10, v + 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 0, 0),
                2
            )

        cv2.imshow("Camera", frame)
        cv2.imshow("Mask", mask)

        key = cv2.waitKey(1)

        # Press m to move Dobot to block
        if key == ord("m") and center is not None:
            u, v = center
            x, y = pixel_to_dobot(u, v)
            move_dobot_to_block(robot, x, y)

        # Press q to quit
        if key == ord("q"):
            break

    robot.suck(False)
    robot.close()
    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    main()