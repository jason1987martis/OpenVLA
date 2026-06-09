import os
import sys
import ctypes
import numpy as np
import cv2

# ==============================================================================
# 1. LINK SYSTEM RUNTIME RUNNING SPACE (Loads all DLL dependencies together)
# ==============================================================================
runtime_dir = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"

if os.path.exists(runtime_dir):
    print(f"[1/2] Linking Windows DLL dependency tracking directory: {runtime_dir}")
    # Tell Python it is safe to load binaries from this specific path
    os.add_dll_directory(runtime_dir)
    
    try:
        # Force load the main file using standard Windows API search rules
        ctypes.WinDLL(os.path.join(runtime_dir, "MvCameraControl.dll"), use_last_error=True)
        print("[SUCCESS] Industrial camera drivers loaded successfully into memory.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed loading binary framework: {e}")
        sys.exit()
else:
    print(f"[CRITICAL ERROR] Could not locate the MVS Runtime folder at: {runtime_dir}")
    sys.exit()

try:
    # Import the local Python SDK files present right beside this script in D:\Matrix
    from MvCameraControl_class import *
    print("[SUCCESS] Successfully linked internal MVS SDK headers.")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    print("Ensure all .py files from the MvImport folder are pasted inside your D:\\Matrix workspace folder.")
    sys.exit()


def main():
    # CRITICAL REMINDER: The desktop MVS app dashboard MUST be completely closed!
    cam = MvCamera()
    deviceList = MV_CC_DEVICE_INFO_LIST()
    
    # Poll system for active industrial camera endpoints over USB
    ret = cam.MV_CC_EnumDevices(MV_USB_DEVICE | MV_GIGE_DEVICE, deviceList)
    if ret != 0 or deviceList.nDeviceNum == 0:
        print(f"[ERROR] No industrial cameras detected. Error code: {hex(ret)}")
        return

    # ==========================================================================
    # FIXING THE 0x80000004 PARAMETER GLITCH:
    # Explicitly fetching device index 0 pointer memory slice array structures 
    # instead of passing raw container instances.
    # ==========================================================================
    stDeviceInfo = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    
    ret = cam.MV_CC_CreateHandle(stDeviceInfo)
    if ret != 0:
        print(f"[ERROR] Pipeline handle allocation failed: {hex(ret)}")
        return

    # Claim exclusive connection priority channel overrides over the hardware
    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"[ERROR] Device open rejected. Close the MVS software window screen. Code: {hex(ret)}")
        cam.MV_CC_DestroyHandle()
        return

    # Check the required block sizes matching your MV-CE050-30UC data output profiles
    stParam = MVCC_INTVALUE()
    cam.MV_CC_GetIntValue("PayloadSize", stParam)
    payload_size = stParam.nCurValue

    # Prepare active memory structures to capture video stream frames
    data_buf = (c_ubyte * payload_size)()
    stFrameInfo = MV_FRAME_OUT_INFO_EX()

    # Trigger frame grabbing loop updates
    cam.MV_CC_StartGrabbing()
    print("\n=======================================================")
    print("[SUCCESS] Industrial Camera Frame Stream Opened Successfully!")
    print("Click on the popup screen window and press 'q' to stop cleanly.")
    print("=======================================================")

    try:
        while True:
            # Grab raw frame blocks with a 1000ms timeout threshold check parameter
            ret = cam.MV_CC_GetOneFrameTimeout(data_buf, payload_size, stFrameInfo, 1000)
            
            if ret == 0:
                height = stFrameInfo.nHeight
                width = stFrameInfo.nWidth
                
                # Reshape raw data streams directly into an NumPy array matrix
                img_raw = np.frombuffer(data_buf, dtype=np.uint8)
                
                # Check formatting hex codes for Mono8 vs generic Color arrays
                if stFrameInfo.enPixelType == 0x01080001:  # Mono8 mapping standard 
                    frame = img_raw.reshape((height, width))
                else:
                    frame = img_raw.reshape((height, width, -1))

                # Superimpose a graphic alignment targeting crosshair layer across the view matrix
                cv2.circle(frame, (int(width/2), int(height/2)), 40, (255, 255, 255), 2)
                cv2.line(frame, (int(width/2)-20, int(height/2)), (int(width/2)+20, int(height/2)), (255, 255, 255), 2)
                cv2.line(frame, (int(width/2), int(height/2)-20), (int(width/2), int(height/2)+20), (255, 255, 255), 2)
                
                # Route out visual matrix layers into the live OpenCV rendering loop viewport
                cv2.imshow("Industrial Hikrobot OpenCV Viewport", frame)
            
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    finally:
        # Tear down ongoing video grab loops and disconnect ports safely
        cam.MV_CC_StopGrabbing()
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        cv2.destroyAllWindows()
        print("Hardware tracking threads successfully terminated.")


if __name__ == "__main__":
    main()
