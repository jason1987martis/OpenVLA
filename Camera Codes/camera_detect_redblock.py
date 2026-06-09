import os
import sys
import ctypes
import numpy as np
import cv2

# ==============================================================================
# 1. LINK SYSTEM RUNTIME RUNNING SPACE
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


# ==============================================================================
# 2. CAMERA FRAME CONVERSION
# ==============================================================================
def convert_camera_frame(img_raw, width, height, pixel_type):
    """
    Converts Hikrobot/MVS raw frame into OpenCV BGR format.
    OpenCV uses BGR, not RGB.
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


# ==============================================================================
# 3. RED BLOCK DETECTION FUNCTION
# ==============================================================================
def detect_red_block(frame):
    """
    Detects the largest red block in a BGR frame.
    Returns the processed frame and red mask.
    """

    output_frame = frame.copy()

    # Convert BGR to HSV
    hsv = cv2.cvtColor(output_frame, cv2.COLOR_BGR2HSV)

    # Red has two HSV ranges because red wraps around hue 0/180
    lower_red1 = np.array([0, 60, 40])
    upper_red1 = np.array([12, 255, 255])

    lower_red2 = np.array([168, 60, 40])
    upper_red2 = np.array([180, 255, 255])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    red_mask = cv2.bitwise_or(mask1, mask2)

    # Remove small noise
    kernel = np.ones((5, 5), np.uint8)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    # Find contours
    contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    red_detected = False

    if contours:
        largest_contour = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest_contour)

        # Adjust this value if your block is small or far from camera
        if area > 500:
            red_detected = True

            x, y, w, h = cv2.boundingRect(largest_contour)

            obj_center_x = x + w // 2
            obj_center_y = y + h // 2

            # Draw bounding box
            cv2.rectangle(output_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)

            # Draw center point
            cv2.circle(output_frame, (obj_center_x, obj_center_y), 6, (0, 0, 255), -1)

            # Display label
            label = f"RED BLOCK: X={obj_center_x}, Y={obj_center_y}, AREA={int(area)}"
            cv2.putText(
                output_frame,
                label,
                (x, y - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (0, 255, 0),
                2
            )

            print(f"Red block detected: X={obj_center_x}, Y={obj_center_y}, Area={int(area)}")

    if not red_detected:
        cv2.putText(
            output_frame,
            "NO RED BLOCK DETECTED",
            (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (0, 0, 255),
            2
        )

    return output_frame, red_mask


def adjust_brightness_contrast(frame, brightness=30, contrast=1.2):
    """
    Adjust brightness and contrast using OpenCV.
    
    brightness: positive value makes image brighter
    contrast: 1.0 means no contrast change
    """
    adjusted = cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)
    return adjusted


# ==============================================================================
# 4. MAIN CAMERA PROGRAM
# ==============================================================================
def main():
    cam = MvCamera()
    deviceList = MV_CC_DEVICE_INFO_LIST()

    ret = cam.MV_CC_EnumDevices(MV_USB_DEVICE | MV_GIGE_DEVICE, deviceList)
    if ret != 0 or deviceList.nDeviceNum == 0:
        print(f"[ERROR] No industrial cameras detected. Error code: {hex(ret)}")
        return

    stDeviceInfo = cast(deviceList.pDeviceInfo[0], POINTER(MV_CC_DEVICE_INFO)).contents

    ret = cam.MV_CC_CreateHandle(stDeviceInfo)
    if ret != 0:
        print(f"[ERROR] Pipeline handle allocation failed: {hex(ret)}")
        print("QUICK FIX: Unplug the camera USB, plug it back in, and run the script again.")
        return

    ret = cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
    if ret != 0:
        print(f"[ERROR] Device open rejected. Close MVS app software. Code: {hex(ret)}")
        cam.MV_CC_DestroyHandle()
        return

    # Optional: try to set camera pixel format to RGB8Packed.
    # If this gives non-zero error, comment it out.
    # ret = cam.MV_CC_SetEnumValue("PixelFormat", 0x02180014)
    # print("Set PixelFormat RGB8Packed:", hex(ret))

    stParam = MVCC_INTVALUE()
    ret = cam.MV_CC_GetIntValue("PayloadSize", stParam)

    if ret != 0:
        print(f"[ERROR] Failed to get PayloadSize. Code: {hex(ret)}")
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        return

    payload_size = stParam.nCurValue

    data_buf = (c_ubyte * payload_size)()
    stFrameInfo = MV_FRAME_OUT_INFO_EX()

    window_name = "Industrial Hikrobot Red Block Detection"
    mask_window_name = "Red Mask"

    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 800, 600)

    cv2.namedWindow(mask_window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(mask_window_name, 800, 600)

    ret = cam.MV_CC_StartGrabbing()
    if ret != 0:
        print(f"[ERROR] Failed to start grabbing. Code: {hex(ret)}")
        cam.MV_CC_CloseDevice()
        cam.MV_CC_DestroyHandle()
        return

    print("\n=======================================================")
    print("[SUCCESS] Industrial Camera Frame Stream Opened Successfully!")
    print("Red block detection is active.")
    print("Click on the OpenCV window and press 'q' to stop cleanly.")
    print("=======================================================\n")

    printed_pixel_type = False

    try:
        while True:
            ret = cam.MV_CC_GetOneFrameTimeout(data_buf, payload_size, stFrameInfo, 1000)

            if ret == 0:
                height = stFrameInfo.nHeight
                width = stFrameInfo.nWidth
                pixel_type = stFrameInfo.enPixelType

                if not printed_pixel_type:
                    print("Camera Pixel Type:", hex(pixel_type))
                    printed_pixel_type = True

                img_raw = np.frombuffer(data_buf, dtype=np.uint8)

                # Convert raw camera data to BGR image
                frame = convert_camera_frame(
                    img_raw,
                    width,
                    height,
                    pixel_type
                )
                
                # FIX: Your camera frame is behaving like RGB.
                # Convert RGB to BGR so OpenCV display and HSV detection work correctly.
                frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                display_w = 800
                display_h = 600

                resized_frame = cv2.resize(
                    frame,
                    (display_w, display_h),
                    interpolation=cv2.INTER_AREA
                )

                resized_frame = adjust_brightness_contrast(
                resized_frame,
                brightness=40,
                contrast=1.2
                )
                                
                
                # Detect red block
                processed_frame, red_mask = detect_red_block(resized_frame)

                # Draw center reference crosshair
#               center_x = display_w // 2
#                center_y = display_h // 2

#                cv2.circle(processed_frame, (center_x, center_y), 40, (255, 255, 255), 2)
#                cv2.line(processed_frame, (center_x - 20, center_y), (center_x + 20, center_y), (255, 255, 255), 2)
#                cv2.line(processed_frame, (center_x, center_y - 20), (center_x, center_y + 20), (255, 255, 255), 2)

                cv2.imshow(window_name, processed_frame)
                cv2.imshow(mask_window_name, red_mask)

            else:
                print(f"[WARNING] Frame grab timeout or error. Code: {hex(ret)}")

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