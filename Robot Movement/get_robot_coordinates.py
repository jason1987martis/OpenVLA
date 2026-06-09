import time
from pydobotplus import Dobot


DOBOT_PORT = "COM8"


def get_current_pose(device):
    """
    Tries common pydobot/pydobotplus pose methods.
    Returns robot position if available.
    """

    # Method 1: common in pydobot / pydobotplus
    if hasattr(device, "pose"):
        return device.pose()

    # Method 2: fallback
    if hasattr(device, "get_pose"):
        return device.get_pose()

    raise AttributeError("No pose method found. Tried device.pose() and device.get_pose().")


def main():
    print(f"[DOBOT] Connecting to {DOBOT_PORT}...")

    device = Dobot(port=DOBOT_PORT)
    time.sleep(1)

    try:
        device.clear_alarms()

        pose = get_current_pose(device)

        print("\n[CURRENT DOBOT POSE]")
        print(pose)

        # Many versions return something like:
        # Position(x=..., y=..., z=..., r=...)
        if hasattr(pose, "x"):
            print("\n[COORDINATES]")
            print(f"X = {pose.x}")
            print(f"Y = {pose.y}")
            print(f"Z = {pose.z}")
            print(f"R = {pose.r}")

    except Exception as e:
        print(f"[ERROR] Could not read pose: {e}")

    finally:
        device.close()
        print("[DOBOT] Connection closed.")


if __name__ == "__main__":
    main()