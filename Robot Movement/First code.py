import time
from pydobotplus import Dobot

def main():
    # Target port identified by your system scan
    port = "COM8"
    
    print(f"[1/4] Connecting directly to Dobot Magician on {port}...")
    try:
        # Initialize connection (verbose parameter removed to fix the TypeError)
        device = Dobot(port=port)
        time.sleep(1) # Let the serial stream settle
        
        # Clear any silent system crash states/alarms
        device.clear_alarms()
        
        # 2. Physical calibration
        print("[2/4] Homing initialized. The arm will physically move backwards.")
        device.home() 
        print("[3/4] Calibration finished successfully.")
        
        # 3. Perform your coordinates
        print("[4/4] Moving to target position...")
        # pydobotplus defaults to blocking wait=True automatically
        device.move_to(x=250, y=0, z=50, r=0)
        
        print("\n[SUCCESS] Sequence completed without errors!")
        
        # Always disconnect to free up the COM8 port channel
        device.close()

    except Exception as e:
        print(f"\n[CRITICAL ERROR] Python execution failed: {e}")
        print("\nIf it hangs or fails here: Close DobotLab/Studio completely so it stops blocking COM8.")

if __name__ == "__main__":
    main()
