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
    os.add_dll_directory(runtime_dir)
    
    try:
        ctypes.WinDLL(os.path.join(runtime_dir, "MvCameraControl.dll"), use_last_error=True)
        print("[SUCCESS] Industrial camera drivers loaded successfully into memory.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed loading binary framework: {e}")
        sys.exit()
else:
    print(f"[CRITICAL ERROR] Could not locate the MVS Runtime folder at: {runtime_dir}")
    sys.exit()

try:
    from MvCameraControl_class import *
    print("[SUCCESS] Successfully linked internal MVS SDK headers.")
except ImportError as e:
    print(f"[ERROR] Import failed: {e}")
    sys.exit()

def convert_camera_frame(img_raw, width, height, pixel_type):
    """
    Converts Hikrobot/MVS raw frame into OpenCV BGR format.
    OpenCV expects BGR, not RGB.
    """

    # Mono8
    if pixel_type == 0x01080001:
        gray = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)

    # BayerGR8
    elif pixel_type == 0x01080008:
        bayer = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(bayer, cv2.COLOR_BAYER_GR2BGR)

    # BayerRG8
    elif pixel_type == 0x01080009:
        bayer = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(bayer, cv2.COLOR_BAYER_RG2BGR)

    # BayerGB8
    elif pixel_type == 0x0108000A:
        bayer = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(bayer, cv2.COLOR_BAYER_GB2BGR)

    # BayerBG8
    elif pixel_type == 0x0108000B:
        bayer = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(bayer, cv2.COLOR_BAYER_BG2BGR)

    # RGB8 Packed
    elif pixel_type == 0x02180014:
        rgb = img_raw[:width * height * 3].reshape((height, width, 3))
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)

    # BGR8 Packed
    elif pixel_type == 0x02180015:
        bgr = img_raw[:width * height * 3].reshape((height, width, 3))
        return bgr

    else:
        print(f"[WARNING] Unsupported pixel type: {hex(pixel_type)}")
        gray = img_raw[:width * height].reshape((height, width))
        return cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)



def main():
    cam = MvCamera()
    deviceList = MV_CC_DEVICE_INFO_LIST()
    
    ret = cam.MV_CC_EnumDevices(MV_USB_DEVICE | MV_GIGE_DEVICE, deviceList)
    if ret != 0 or deviceList.nDeviceNum == 0:
        print(f"[ERROR] No industrial cameras detected. Error code: {hex(ret)}")
        return

    # Direct pointer array element addressing
    stDeviceInfo = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents
    
    ret = cam.MV_CC_CreateHandle(stDeviceInfo)
    if ret != 0:
        print(f"[ERROR] Pipeline handle allocation failed: {hex(ret)}")
        print("💡 QUICK FIX: Unplug the camera USB, plug it back in, and run the script again.")
        return

    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"[ERROR] Device open rejected. Close MVS app software. Code: {hex(ret)}")
        cam.MV_CC_DestroyHandle()
        return

    stParam = MVCC_INTVALUE()
    cam.MV_CC_GetIntValue("PayloadSize", stParam)
    payload_size = stParam.nCurValue

    data_buf = (c_ubyte * payload_size)()
    stFrameInfo = MV_FRAME_OUT_INFO_EX()

    # --------------------------------------------------------------------------
    # NEW: Prepare named OpenCV window configuration flags
    # --------------------------------------------------------------------------
    window_name = "Industrial Hikrobot OpenCV Viewport"
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600) # Constrain display size on screen

    cam.MV_CC_StartGrabbing()
    print("\n=======================================================")
    print("[SUCCESS] Industrial Camera Frame Stream Opened Successfully!")
    print("Click on the popup screen window and press 'q' to stop cleanly.")
    print("=======================================================")

    try:
        while True:
            ret = cam.MV_CC_GetOneFrameTimeout(data_buf, payload_size, stFrameInfo, 1000)
            
            if ret == 0:
                height = stFrameInfo.nHeight
                width = stFrameInfo.nWidth
                
                # Turn raw frame buffer memory bytes into numpy numerical matrix arrays
                img_raw = np.frombuffer(data_buf, dtype=np.uint8)

                frame = convert_camera_frame(
                    img_raw,
                    width,
                    height,
                    stFrameInfo.enPixelType
                )
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
                # --------------------------------------------------------------
                # NEW RESIZING OPTION: Scale image matrix to match desktop monitor sizing
                # --------------------------------------------------------------
                display_w = 800
                display_h = 600
                resized_frame = cv2.resize(frame, (display_w, display_h), interpolation=cv2.INTER_AREA)

                # ==============================================================
                # RED OBJECT DETECTION INTERFACE
                # ==============================================================
                # 1. Force the frame to a 3-channel color layout so color spaces map properly
                if len(resized_frame.shape) == 2:
                    color_frame = cv2.cvtColor(resized_frame, cv2.COLOR_GRAY2BGR)
                else:
                    color_frame = resized_frame.copy()

                # 2. Convert tracking matrix space from BGR into HSV
                hsv = cv2.cvtColor(color_frame, cv2.COLOR_BGR2HSV)

                # 3. Match true red color bounds (Red wraps around 0 and 180 degrees)
                lower_red1 = np.array([0, 120, 70])
                upper_red1 = np.array([10, 255, 255])
                lower_red2 = np.array([170, 120, 70])
                upper_red2 = np.array([180, 255, 255])

                # 4. Isolate matching pixel arrays and combine them
                mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
                mask2 = cv2.inRange(hsv, lower_red2, upper_red2)
                red_mask = cv2.add(mask1, mask2)

                # 5. Clean up image sensor noise using a pixel filter kernel
                kernel = np.ones((5, 5), np.uint8)
                red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)

                # 6. Extract contour maps around the white tracking shapes
                contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

                # 7. Identify the largest solid red target item
                if contours:
                    largest_contour = max(contours, key=cv2.contourArea)
                    
                    # Ignore tiny background dust or speckle arrays (Area filter threshold)
                    if cv2.contourArea(largest_contour) > 400:
                        x, y, w, h = cv2.boundingRect(largest_contour)
                        
                        # Since your screen window view might be grayscale or color,
                        # ensure we write the green/red graphics directly to whatever frame type is displaying
                        if len(resized_frame.shape) == 2:
                            resized_frame = cv2.cvtColor(resized_frame, cv2.COLOR_GRAY2BGR)

                        # Draw a solid Green bounding tracking box outline
                        cv2.rectangle(resized_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
                        
                        # Pinpoint target box center pixel placement coordinates
                        obj_center_x = int(x + (w / 2))
                        obj_center_y = int(y + (h / 2))
                        
                        # Add a solid tracking center point marker point layer
                        cv2.circle(resized_frame, (obj_center_x, obj_center_y), 5, (0, 0, 255), -1)
                        
                        # Print live coordinates right onto the screen display matrix
                        label = f"RED TARGET: X={obj_center_x}, Y={obj_center_y}"
                        cv2.putText(resized_frame, label, (x, y - 10), 
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)
                # ==============================================================
                
                # Overlay target layouts relative to our new 800x600 layout
                center_x, center_y = int(display_w / 2), int(display_h / 2)
                cv2.circle(resized_frame, (center_x, center_y), 40, (255, 255, 255), 2)
                cv2.line(resized_frame, (center_x-20, center_y), (center_x+20, center_y), (255, 255, 255), 2)
                cv2.line(resized_frame, (center_x, center_y-20), (center_x, center_y+20), (255, 255, 255), 2)
                
                # Show the scaled image matrix instead of the raw, giant array
                cv2.imshow(window_name, resized_frame)
 
            
            # Use short 10ms wait key parameter window to evaluate keyboard inputs
            if cv2.waitKey(10) & 0xFF == ord('q'):
                break
                
    finally:
        cam.MV_CC_StopGrabbing()
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        cv2.destroyAllWindows()
        print("Hardware tracking threads successfully terminated.")


if __name__ == "__main__":
    main()
