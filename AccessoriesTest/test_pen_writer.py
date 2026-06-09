import time
from pydobotplus import Dobot


DOBOT_PORT = "COM8"


# Safe starting position
START_X = 230.0
START_Y = 0.0
START_Z = 90.0
START_R = 0.0

# Pen movement heights
PEN_UP_Z = 70.0
PEN_DOWN_Z = 45.0

# Writing area
CENTER_X = 230.0
CENTER_Y = 0.0

# Size of drawn square
SIZE = 30.0


def move(device, x, y, z, r=0.0, delay=0.3):
    print(f"[MOVE] X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}")
    device.move_to(x=float(x), y=float(y), z=float(z), r=float(r))
    time.sleep(delay)


def pen_up(device, x, y):
    print("[PEN] UP")
    move(device, x, y, PEN_UP_Z)


def pen_down(device, x, y):
    print("[PEN] DOWN")
    move(device, x, y, PEN_DOWN_Z)


def draw_line(device, x1, y1, x2, y2):
    """
    Move to start with pen up,
    lower pen,
    draw line,
    lift pen.
    """

    pen_up(device, x1, y1)
    pen_down(device, x1, y1)

    move(device, x2, y2, PEN_DOWN_Z, delay=0.5)

    pen_up(device, x2, y2)


def draw_square(device, center_x, center_y, size):
    half = size / 2.0

    x1 = center_x - half
    y1 = center_y - half

    x2 = center_x + half
    y2 = center_y - half

    x3 = center_x + half
    y3 = center_y + half

    x4 = center_x - half
    y4 = center_y + half

    print("[DRAW] Square started")

    pen_up(device, x1, y1)
    pen_down(device, x1, y1)

    move(device, x2, y2, PEN_DOWN_Z)
    move(device, x3, y3, PEN_DOWN_Z)
    move(device, x4, y4, PEN_DOWN_Z)
    move(device, x1, y1, PEN_DOWN_Z)

    pen_up(device, x1, y1)

    print("[DRAW] Square completed")


def main():
    device = None

    try:
        print(f"[DOBOT] Connecting to {DOBOT_PORT}...")
        device = Dobot(port=DOBOT_PORT)
        time.sleep(1)

        device.clear_alarms()

        print("[INFO] Moving to safe start position")
        move(device, START_X, START_Y, START_Z, START_R)

        print("[INFO] Drawing square")
        draw_square(device, CENTER_X, CENTER_Y, SIZE)

        print("[INFO] Returning to safe position")
        move(device, START_X, START_Y, START_Z, START_R)

        print("[DONE] Pen writing test completed.")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        if device is not None:
            try:
                move(device, START_X, START_Y, START_Z, START_R)
            except Exception:
                pass

            device.close()
            print("[DOBOT] Connection closed.")


if __name__ == "__main__":
    main()