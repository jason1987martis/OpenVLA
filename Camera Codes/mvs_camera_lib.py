# All your OpenCV scripts can use these codes to use the Hikrobot/Hikvision MVS industrial camera with the official SDK.:
# from cap = cv2.VideoCapture(0) to
#============================================================================
# from mvs_camera_lib import MVSCamera
# camera = MVSCamera()
# camera.open()
# frame = camera.read()
# camera.close()

# OR 

# from mvs_camera_lib import MVSCamera
# cap = MVSCamera(
#     resize_width=800,
#     resize_height=600,
#     apply_color_fix=True
# )
# cap.open()
#===============================================================================
# For frame retrieval Replace:
# ret, frame = cap.read()
# if not ret:
#     continue

# with:

# frame = camera.read()
# if frame is None:
#     continue

#================================================================================
# for frame realease Replace:
# cap.release()

# with :

# cap.close()
# ==============================================================================

# ==============================================================================
# Finally to only test camera 
# python mvs_camera_lib.py
# ==============================================================================


import os
import sys
import ctypes

import cv2
import numpy as np

from ctypes import cast, POINTER, c_ubyte


# ==============================================================================
# LOCAL PROJECT / SDK CONFIG
# ==============================================================================
#RUNTIME_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(PROJECT_DIR, "SDK")

# Use local SDK folder for DLL and Python SDK files
RUNTIME_DIR = SDK_DIR

MVS_DLL_NAME = "MvCameraControl.dll"
MVS_DLL_PATH = os.path.join(RUNTIME_DIR, MVS_DLL_NAME)
MVS_PYTHON_WRAPPER = os.path.join(SDK_DIR, "MvCameraControl_class.py")


# ==============================================================================
# LOAD MVS SDK FROM LOCAL SDK FOLDER
# ==============================================================================

def load_mvs_sdk():
    """
    Loads the Hikrobot/Hikvision MVS SDK from the local SDK folder.

    Required structure:

        project_folder/
        ├── mvs_camera_lib.py
        ├── your_opencv_script.py
        └── SDK/
            ├── MvCameraControl.dll
            ├── MvCameraControl_class.py
            ├── CameraParams_header.py
            ├── MvErrorDefine_const.py
            ├── PixelType_header.py
            ├── PixelType_const.py
            └── other MVS DLL / Python SDK files

    If DLL loading fails, copy all DLL files from the MVS runtime folder
    into the local SDK folder or Uncomment the lines in this RUNTIME_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64" to load directly from the MVS runtime folder.
    """

    if not os.path.exists(RUNTIME_DIR):
        print(f"[CRITICAL ERROR] Could not locate MVS runtime folder: {RUNTIME_DIR}")
        sys.exit()

    if not os.path.exists(MVS_DLL_PATH):
        print("[CRITICAL ERROR] Could not find MvCameraControl.dll.")
        print("Expected DLL:")
        print(MVS_DLL_PATH)
        print()
        print("Copy MvCameraControl.dll and other MVS runtime DLLs into:")
        print(SDK_DIR)
        sys.exit()

    if not os.path.exists(MVS_PYTHON_WRAPPER):
        print("[CRITICAL ERROR] Could not find MvCameraControl_class.py in local SDK folder.")
        print("Expected file:")
        print(MVS_PYTHON_WRAPPER)
        print()
        print("Please copy the Hikrobot/MVS Python SDK MvImport files into:")
        print(SDK_DIR)
        sys.exit()

    print(f"[MVS] Linking DLL directory: {RUNTIME_DIR}")

    try:
        os.add_dll_directory(RUNTIME_DIR)
    except Exception as e:
        print(f"[CRITICAL ERROR] Could not add DLL directory: {e}")
        sys.exit()

    try:
        ctypes.WinDLL(MVS_DLL_PATH, use_last_error=True)
        print("[MVS] Industrial camera drivers loaded successfully from local SDK folder.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed loading MVS runtime: {e}")
        print()
        print("Possible fix:")
        print("Copy all DLL files from:")
        print(r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64")
        print("into:")
        print(SDK_DIR)
        sys.exit()

    if SDK_DIR not in sys.path:
        sys.path.insert(0, SDK_DIR)

    print(f"[MVS] Using local SDK folder: {SDK_DIR}")


load_mvs_sdk()


try:
    from MvCameraControl_class import *
    print("[MVS] Successfully linked MVS SDK headers from local SDK folder.")
except ImportError as e:
    print(f"[CRITICAL ERROR] Could not import MvCameraControl_class from SDK folder: {e}")
    print()
    print("Make sure these files are inside the SDK folder:")
    print("  - MvCameraControl_class.py")
    print("  - CameraParams_header.py")
    print("  - MvErrorDefine_const.py")
    print("  - PixelType_header.py")
    print("  - PixelType_const.py")
    sys.exit()


# ==============================================================================
# CAMERA FRAME CONVERSION
# ==============================================================================

def convert_camera_frame(img_raw, width, height, pixel_type):
    """
    Converts Hikrobot/MVS raw frame into OpenCV BGR image.
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
# MVS CAMERA CLASS
# ==============================================================================

class MVSCamera:
    def __init__(
        self,
        device_index=0,
        timeout_ms=1000,
        resize_width=None,
        resize_height=None,
        apply_color_fix=True
    ):
        """
        MVS industrial camera wrapper.

        Parameters
        ----------
        device_index:
            Camera index from the MVS detected device list.
            Usually 0 if only one camera is connected.

        timeout_ms:
            Frame grab timeout.

        resize_width / resize_height:
            Optional output resize.
            If None, original camera resolution is returned.

        apply_color_fix:
            Keep True because your camera setup needed red/blue correction.
            If the color becomes wrong, set it to False.
        """

        self.device_index = device_index
        self.timeout_ms = timeout_ms
        self.resize_width = resize_width
        self.resize_height = resize_height
        self.apply_color_fix = apply_color_fix

        self.cam = MvCamera()
        self.device_list = MV_CC_DEVICE_INFO_LIST()
        self.payload_size = None
        self.data_buf = None
        self.frame_info = MV_FRAME_OUT_INFO_EX()
        self.opened = False
        self.printed_pixel_type = False

    def open(self):
        ret = self.cam.MV_CC_EnumDevices(
            MV_USB_DEVICE | MV_GIGE_DEVICE,
            self.device_list
        )

        if ret != 0 or self.device_list.nDeviceNum == 0:
            raise RuntimeError(
                f"No industrial cameras detected. Error code: {hex(ret)}"
            )

        print(f"[MVS] Detected cameras: {self.device_list.nDeviceNum}")

        if self.device_index >= self.device_list.nDeviceNum:
            raise RuntimeError(
                f"Requested device index {self.device_index}, "
                f"but only {self.device_list.nDeviceNum} camera(s) detected."
            )

        st_device_info = cast(
            self.device_list.pDeviceInfo[self.device_index],
            POINTER(MV_CC_DEVICE_INFO)
        ).contents

        ret = self.cam.MV_CC_CreateHandle(st_device_info)
        if ret != 0:
            raise RuntimeError(f"Camera handle allocation failed: {hex(ret)}")

        ret = self.cam.MV_CC_OpenDevice(MV_ACCESS_Exclusive, 0)
        if ret != 0:
            self.cam.MV_CC_DestroyHandle()
            raise RuntimeError(
                f"Device open failed: {hex(ret)}. Close MVS Viewer if it is open."
            )

        st_param = MVCC_INTVALUE()
        ret = self.cam.MV_CC_GetIntValue("PayloadSize", st_param)

        if ret != 0:
            self.close()
            raise RuntimeError(f"Failed to get PayloadSize: {hex(ret)}")

        self.payload_size = st_param.nCurValue
        self.data_buf = (c_ubyte * self.payload_size)()

        ret = self.cam.MV_CC_StartGrabbing()
        if ret != 0:
            self.close()
            raise RuntimeError(f"Failed to start grabbing: {hex(ret)}")

        self.opened = True
        print("[MVS] Camera stream started successfully.")

    def read(self):
        """
        Reads one frame from the MVS camera.

        Returns
        -------
        frame:
            OpenCV BGR image.

        None:
            If frame grab failed.
        """

        if not self.opened:
            return None

        ret = self.cam.MV_CC_GetOneFrameTimeout(
            self.data_buf,
            self.payload_size,
            self.frame_info,
            self.timeout_ms
        )

        if ret != 0:
            return None

        height = self.frame_info.nHeight
        width = self.frame_info.nWidth
        pixel_type = self.frame_info.enPixelType

        if not self.printed_pixel_type:
            print("[MVS] Frame size:", width, "x", height)
            print("[MVS] Pixel Type:", hex(pixel_type))
            self.printed_pixel_type = True

        img_raw = np.frombuffer(self.data_buf, dtype=np.uint8)

        frame = convert_camera_frame(
            img_raw,
            width,
            height,
            pixel_type
        )

        # Your camera setup needed this correction because red/blue were swapped.
        if self.apply_color_fix:
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        if self.resize_width is not None and self.resize_height is not None:
            frame = cv2.resize(
                frame,
                (self.resize_width, self.resize_height),
                interpolation=cv2.INTER_AREA
            )

        return frame

    def close(self):
        try:
            self.cam.MV_CC_StopGrabbing()
        except Exception:
            pass

        try:
            self.cam.MV_CC_CloseDevice()
        except Exception:
            pass

        try:
            self.cam.MV_CC_DestroyHandle()
        except Exception:
            pass

        self.opened = False
        print("[MVS] Camera closed.")

    def release(self):
        """
        Compatibility method so this behaves like cv2.VideoCapture.
        """
        self.close()

    def isOpened(self):
        """
        Compatibility method so this behaves like cv2.VideoCapture.
        """
        return self.opened

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


# ==============================================================================
# SIMPLE TEST
# ==============================================================================

def test_camera():
    camera = MVSCamera(
        resize_width=800,
        resize_height=600,
        apply_color_fix=True
    )

    try:
        camera.open()

        while True:
            frame = camera.read()

            if frame is None:
                print("[WARNING] Frame grab failed.")
                continue

            cv2.imshow("MVS Camera Library Test", frame)

            key = cv2.waitKey(1) & 0xFF

            if key == ord("q"):
                break

    finally:
        camera.close()
        cv2.destroyAllWindows()


if __name__ == "__main__":
    test_camera()