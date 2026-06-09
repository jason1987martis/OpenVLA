import time
from pydobotplus import Dobot

def main():
    port = "COM8"
    print(f"Connecting to Dobot Magician on {port}...")
    
    try:
        device = Dobot(port=port)
        time.sleep(1)
        
        # 1. Always clear alarms and home first
        device.clear_alarms()
        print("Homing arm...")
        device.home()
        print("Homing done. Starting job sequence...")
        
        # ====================================================
        # 2. DEFINE YOUR JOB POSITIONS HERE
        # Format: device.move_to(X, Y, Z, R)
        # X = Forward/Backward, Y = Left/Right, Z = Up/Down, R = Wrist Rotation
        # ====================================================
        
        # Position 1: Hover above the pickup area
        print("Moving to Position 1 (Hovering)...")
        device.move_to(x=200, y=0, z=100, r=0)
        time.sleep(0.5) # Optional: Pause for half a second
        
        # Position 2: Drop down to pick up an item
        print("Moving to Position 2 (Low Center)...")
        device.move_to(x=200, y=0, z=20, r=0)
        time.sleep(0.5)
        
        # Position 3: Lift up and swing to the left side
        print("Moving to Position 3 (High Left)...")
        device.move_to(x=200, y=100, z=80, r=0)
        time.sleep(0.5)
        
        # Position 4: Swing to the right side
        print("Moving to Position 4 (High Right)...")
        device.move_to(x=200, y=-100, z=80, r=0)
        time.sleep(0.5)
        
        # Position 5: Safe travel height back to center
        print("Moving back to safe center position...")
        device.move_to(x=250, y=0, z=50, r=0)

        print("\n[SUCCESS] All positions reached!")
        device.close()

    except Exception as e:
        print(f"\n[ERROR] Movement failed: {e}")

if __name__ == "__main__":
    main()
