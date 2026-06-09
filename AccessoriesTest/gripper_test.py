import time
from pydobotplus import Dobot

DOBOT_PORT = "COM8"

def gripper_close(device):
    """
    Close gripper.
    Different Dobot libraries may use grip(True) or gripper(True).
    This tries both.
    """

    if hasattr(device, "grip"):
        device.grip(True)
        return

    if hasattr(device, "gripper"):
        device.gripper(True)
        return

    raise AttributeError("No gripper method found. Tried grip(True) and gripper(True).")


def gripper_open(device):
    """
    Open gripper.
    Different Dobot libraries may use grip(False) or gripper(False).
    This tries both.
    """

    if hasattr(device, "grip"):
        device.grip(False)
        return

    if hasattr(device, "gripper"):
        device.gripper(False)
        return

    raise AttributeError("No gripper method found. Tried grip(False) and gripper(False).")


def main():
    device = None

    try:
        print(f"[DOBOT] Connecting to {DOBOT_PORT}...")
        device = Dobot(port=DOBOT_PORT)
        time.sleep(1)

        device.clear_alarms()

        print("[GRIPPER] OPEN")
        gripper_open(device)
        time.sleep(2)

        print("[GRIPPER] CLOSE")
        gripper_close(device)
        time.sleep(2)

        print("[GRIPPER] OPEN")
        gripper_open(device)
        time.sleep(1)

        print("[DONE] Gripper test completed.")

    except Exception as e:
        print(f"[ERROR] {e}")

    finally:
        if device is not None:
            try:
                gripper_open(device)
            except Exception:
                pass

            device.close()
            print("[DOBOT] Connection closed.")


if __name__ == "__main__":
    main()