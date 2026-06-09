import time
from pydobotplus import Dobot


DOBOT_PORT = "COM8"


SAFE_Z = 90.0
PICK_Z = 55.0
DROP_Z = 55.0

PICK_X = 230.0
PICK_Y = 0.0

DROP_X = 260.0
DROP_Y = 60.0

R = 0.0


def move(device, x, y, z, r=0.0, delay=0.4):
    print(f"[MOVE] X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}")
    device.move_to(x=float(x), y=float(y), z=float(z), r=float(r))
    time.sleep(delay)


def suction_on(device):
    print("[SUCTION] ON")
    device.suck(True)
    time.sleep(0.8)


def suction_off(device):
    print("[SUCTION] OFF")
    device.suck(False)
    time.sleep(0.5)


def main():
    device = None

    try:
        print(f"[DOBOT] Connecting to {DOBOT_PORT}...")
        device = Dobot(port=DOBOT_PORT)
        time.sleep(1)

        device.clear_alarms()

        print("[PICK] Moving above pick point")
        move(device, PICK_X, PICK_Y, SAFE_Z, R)

        print("[PICK] Moving down")
        move(device, PICK_X, PICK_Y, PICK_Z, R)

        suction_on(device)

        print("[PICK] Lifting object")
        move(device, PICK_X, PICK_Y, SAFE_Z, R)

        print("[PLACE] Moving above drop point")
        move(device, DROP_X, DROP_Y, SAFE_Z, R)

        print("[PLACE] Moving down")
        move(device, DROP_X, DROP_Y, DROP_Z, R)

        suction_off(device)

        print("[PLACE] Lifting")
        move(device, DROP_X, DROP_Y, SAFE_Z, R)

        print("[DONE] Pick and place completed.")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        if device is not None:
            try:
                device.suck(False)
            except Exception:
                pass

            device.close()
            print("[DOBOT] Connection closed.")


if __name__ == "__main__":
    main()