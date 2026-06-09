import os
import sys
import time
import json
import ctypes

import cv2
import numpy as np
from pydobotplus import Dobot


# ==============================================================================
# CONFIG
# ==============================================================================

DOBOT_PORT = "COM8"

RUNTIME_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"

DISPLAY_W = 800
DISPLAY_H = 600

DEFAULT_X = 250.0
DEFAULT_Y = 0.0
DEFAULT_Z = 80.0
DEFAULT_R = 0.0

SAFE_Z = 80.0
PICK_Z = 45.0

JOG_STEP_DEFAULT = 5.0

HOMOGRAPHY_FILE = "homography.npy"
CALIBRATION_FILE = "calibration_points.json"

WINDOW_MAIN = "Dobot + MVS Mapper"
WINDOW_MASK = "Red Mask"
WINDOW_CONTROLS = "Controls"
WINDOW_HELP = "Instructions"

CALIBRATION_ROBOT_POINTS = [
    [200, -100],
    [250, -100],
    [300, -100],

    [200, 0],
    [250, 0],
    [300, 0],

    [200, 100],
    [250, 100],
    [300, 100],
]


# ==============================================================================
# LOAD MVS SDK FROM SDK FOLDER
# ==============================================================================

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(PROJECT_DIR, "SDK")

if os.path.exists(RUNTIME_DIR):
    print(f"[MVS] Linking DLL directory: {RUNTIME_DIR}")
    os.add_dll_directory(RUNTIME_DIR)

    try:
        ctypes.WinDLL(os.path.join(RUNTIME_DIR, "MvCameraControl.dll"), use_last_error=True)
        print("[MVS] Industrial camera drivers loaded successfully.")
    except Exception as e:
        print(f"[CRITICAL ERROR] Failed loading MVS runtime: {e}")
        sys.exit()
else:
    print(f"[CRITICAL ERROR] Could not locate MVS runtime folder: {RUNTIME_DIR}")
    sys.exit()


if os.path.exists(os.path.join(SDK_DIR, "MvCameraControl_class.py")):
    sys.path.insert(0, SDK_DIR)
    print(f"[MVS] Using local SDK folder: {SDK_DIR}")
else:
    print("[CRITICAL ERROR] Could not find MvCameraControl_class.py in local SDK folder.")
    print("Expected file:")
    print(os.path.join(SDK_DIR, "MvCameraControl_class.py"))
    print("\nPlease copy the Hikrobot/MVS Python SDK MvImport files into:")
    print(SDK_DIR)
    sys.exit()


try:
    from MvCameraControl_class import *
    print("[MVS] Successfully linked MVS SDK headers from local SDK folder.")
except ImportError as e:
    print(f"[CRITICAL ERROR] Could not import MvCameraControl_class from SDK folder: {e}")
    print("\nMake sure these files are inside the SDK folder:")
    print("  - MvCameraControl_class.py")
    print("  - CameraParams_header.py")
    print("  - MvErrorDefine_const.py")
    print("  - PixelType_header.py")
    print("  - PixelType_const.py")
    sys.exit()



#Old Codes (Uncomment only if not workin')
# if os.path.exists(RUNTIME_DIR):
#     print(f"[MVS] Linking DLL directory: {RUNTIME_DIR}")
#     os.add_dll_directory(RUNTIME_DIR)

#     try:
#         ctypes.WinDLL(os.path.join(RUNTIME_DIR, "MvCameraControl.dll"), use_last_error=True)
#         print("[MVS] Industrial camera drivers loaded successfully.")
#     except Exception as e:
#         print(f"[CRITICAL ERROR] Failed loading MVS runtime: {e}")
#         sys.exit()
# else:
#     print(f"[CRITICAL ERROR] Could not locate MVS runtime folder: {RUNTIME_DIR}")
#     sys.exit()


# possible_import_dirs = [
#     os.getcwd(),
#     os.path.dirname(os.path.abspath(__file__)),

#     r"C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport",
#     r"C:\Program Files\MVS\Development\Samples\Python\MvImport",

#     r"C:\Program Files (x86)\Common Files\MVS\Development\Samples\Python\MvImport",
#     r"C:\Program Files\Common Files\MVS\Development\Samples\Python\MvImport",

#     r"C:\Program Files (x86)\Hikrobot\MVS\Development\Samples\Python\MvImport",
#     r"C:\Program Files\Hikrobot\MVS\Development\Samples\Python\MvImport",
# ]

# found_import_dir = None

# for path in possible_import_dirs:
#     if os.path.exists(os.path.join(path, "MvCameraControl_class.py")):
#         found_import_dir = path
#         break

# if found_import_dir is not None:
#     sys.path.append(found_import_dir)
#     print(f"[MVS] Found Python SDK import path: {found_import_dir}")
# else:
#     print("[CRITICAL ERROR] Could not find MvCameraControl_class.py.")
#     print("Copy MvCameraControl_class.py and related MvImport files into this folder:")
#     print(os.path.dirname(os.path.abspath(__file__)))
#     sys.exit()
# try:
#     from MvCameraControl_class import *
#     print("[MVS] Successfully linked MVS SDK headers.")
# except ImportError as e:
#     print(f"[CRITICAL ERROR] Could not import MvCameraControl_class: {e}")
#     sys.exit()


# ==============================================================================
# CAMERA FRAME CONVERSION
# ==============================================================================

def convert_camera_frame(img_raw, width, height, pixel_type):
    """
    Converts Hikrobot/MVS raw frame into OpenCV image.
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
    def __init__(self):
        self.cam = MvCamera()
        self.device_list = MV_CC_DEVICE_INFO_LIST()
        self.payload_size = None
        self.data_buf = None
        self.frame_info = MV_FRAME_OUT_INFO_EX()
        self.opened = False
        self.printed_pixel_type = False

    def open(self):
        ret = self.cam.MV_CC_EnumDevices(MV_USB_DEVICE | MV_GIGE_DEVICE, self.device_list)

        if ret != 0 or self.device_list.nDeviceNum == 0:
            raise RuntimeError(f"No industrial cameras detected. Error code: {hex(ret)}")

        print(f"[MVS] Detected cameras: {self.device_list.nDeviceNum}")

        st_device_info = cast(
            self.device_list.pDeviceInfo[0],
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
        if not self.opened:
            return None

        ret = self.cam.MV_CC_GetOneFrameTimeout(
            self.data_buf,
            self.payload_size,
            self.frame_info,
            1000
        )

        if ret != 0:
            return None

        height = self.frame_info.nHeight
        width = self.frame_info.nWidth
        pixel_type = self.frame_info.enPixelType

        if not self.printed_pixel_type:
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
        frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

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


# ==============================================================================
# DOBOT CLASS
# ==============================================================================

class DobotController:
    def __init__(self, port):
        self.port = port
        self.device = None
        self.connected = False

    def connect(self):
        print(f"[DOBOT] Connecting on {self.port}...")
        self.device = Dobot(port=self.port)
        time.sleep(1)

        self.device.clear_alarms()
        self.connected = True

        print("[DOBOT] Connected successfully.")

    def home(self):
        self._check()
        print("[DOBOT] Homing started. Arm will move.")
        self.device.home()
        print("[DOBOT] Homing completed.")

    def move_to(self, x, y, z, r):
        self._check()

        print(f"[DOBOT] Moving to X={x:.2f}, Y={y:.2f}, Z={z:.2f}, R={r:.2f}")
        self.device.move_to(x=float(x), y=float(y), z=float(z), r=float(r))
        print("[DOBOT] Move completed.")

    def close(self):
        if self.device is not None:
            self.device.close()
            print("[DOBOT] Connection closed.")

        self.connected = False

    def _check(self):
        if self.device is None or not self.connected:
            raise RuntimeError("Dobot is not connected.")


# ==============================================================================
# OPENCV CONTROLS
# ==============================================================================

def nothing(_):
    pass


def create_controls():
    cv2.namedWindow(WINDOW_CONTROLS, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(WINDOW_CONTROLS, 520, 520)

    cv2.createTrackbar("H1 Low", WINDOW_CONTROLS, 0, 179, nothing)
    cv2.createTrackbar("H1 High", WINDOW_CONTROLS, 12, 179, nothing)

    cv2.createTrackbar("H2 Low", WINDOW_CONTROLS, 168, 179, nothing)
    cv2.createTrackbar("H2 High", WINDOW_CONTROLS, 179, 179, nothing)

    cv2.createTrackbar("S Low", WINDOW_CONTROLS, 70, 255, nothing)
    cv2.createTrackbar("V Low", WINDOW_CONTROLS, 50, 255, nothing)

    cv2.createTrackbar("Min Area", WINDOW_CONTROLS, 500, 20000, nothing)
    cv2.createTrackbar("Kernel", WINDOW_CONTROLS, 5, 25, nothing)

    cv2.createTrackbar("Brightness", WINDOW_CONTROLS, 50, 100, nothing)
    cv2.createTrackbar("Contrast x10", WINDOW_CONTROLS, 12, 30, nothing)


def get_controls():
    kernel_size = cv2.getTrackbarPos("Kernel", WINDOW_CONTROLS)

    if kernel_size < 1:
        kernel_size = 1

    if kernel_size % 2 == 0:
        kernel_size += 1

    brightness_raw = cv2.getTrackbarPos("Brightness", WINDOW_CONTROLS)
    contrast_raw = cv2.getTrackbarPos("Contrast x10", WINDOW_CONTROLS)

    return {
        "h1_low": cv2.getTrackbarPos("H1 Low", WINDOW_CONTROLS),
        "h1_high": cv2.getTrackbarPos("H1 High", WINDOW_CONTROLS),
        "h2_low": cv2.getTrackbarPos("H2 Low", WINDOW_CONTROLS),
        "h2_high": cv2.getTrackbarPos("H2 High", WINDOW_CONTROLS),
        "s_low": cv2.getTrackbarPos("S Low", WINDOW_CONTROLS),
        "v_low": cv2.getTrackbarPos("V Low", WINDOW_CONTROLS),
        "min_area": cv2.getTrackbarPos("Min Area", WINDOW_CONTROLS),
        "kernel_size": kernel_size,
        "brightness": brightness_raw - 50,
        "contrast": max(1, contrast_raw) / 10.0,
    }


# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================

def adjust_brightness_contrast(frame, brightness=0, contrast=1.0):
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)


def detect_red_block(frame, controls):
    output = frame.copy()

    hsv = cv2.cvtColor(output, cv2.COLOR_BGR2HSV)

    lower_red1 = np.array([
        controls["h1_low"],
        controls["s_low"],
        controls["v_low"]
    ])

    upper_red1 = np.array([
        controls["h1_high"],
        255,
        255
    ])

    lower_red2 = np.array([
        controls["h2_low"],
        controls["s_low"],
        controls["v_low"]
    ])

    upper_red2 = np.array([
        controls["h2_high"],
        255,
        255
    ])

    mask1 = cv2.inRange(hsv, lower_red1, upper_red1)
    mask2 = cv2.inRange(hsv, lower_red2, upper_red2)

    red_mask = cv2.bitwise_or(mask1, mask2)

    kernel = np.ones(
        (controls["kernel_size"], controls["kernel_size"]),
        np.uint8
    )

    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
    red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_CLOSE, kernel)

    contours, _ = cv2.findContours(
        red_mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    detection = None

    if contours:
        largest = max(contours, key=cv2.contourArea)
        area = cv2.contourArea(largest)

        if area >= controls["min_area"]:
            x, y, w, h = cv2.boundingRect(largest)

            moment = cv2.moments(largest)

            if moment["m00"] != 0:
                u = int(moment["m10"] / moment["m00"])
                v = int(moment["m01"] / moment["m00"])
            else:
                u = x + w // 2
                v = y + h // 2

            detection = {
                "u": u,
                "v": v,
                "area": area,
                "bbox": [x, y, w, h]
            }

            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(output, (u, v), 7, (0, 0, 255), -1)

            cv2.putText(
                output,
                f"RED: u={u}, v={v}, area={int(area)}",
                (x, max(30, y - 10)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (0, 255, 0),
                2
            )

    return output, red_mask, detection


# ==============================================================================
# HOMOGRAPHY
# ==============================================================================

def compute_homography(image_points, robot_points):
    if len(image_points) < 4:
        print("[ERROR] Need at least 4 point pairs.")
        return None, None

    image_np = np.array(image_points, dtype=np.float32)
    robot_np = np.array(robot_points, dtype=np.float32)

    H, status = cv2.findHomography(image_np, robot_np, method=cv2.RANSAC)
    return H, status


def pixel_to_robot(H, u, v):
    if H is None:
        return None

    pixel_point = np.array([[[float(u), float(v)]]], dtype=np.float32)
    robot_point = cv2.perspectiveTransform(pixel_point, H)

    x = float(robot_point[0][0][0])
    y = float(robot_point[0][0][1])

    return x, y


def save_calibration(image_points, robot_points, H):
    data = {
        "image_points": image_points,
        "robot_points": robot_points,
        "homography": H.tolist() if H is not None else None,
    }

    with open(CALIBRATION_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    if H is not None:
        np.save(HOMOGRAPHY_FILE, H)

    print(f"[SAVED] {CALIBRATION_FILE}")

    if H is not None:
        print(f"[SAVED] {HOMOGRAPHY_FILE}")


def load_calibration():
    if not os.path.exists(CALIBRATION_FILE):
        print("[INFO] No existing calibration file found.")
        return [], [], None

    with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_points = data.get("image_points", [])
    robot_points = data.get("robot_points", [])

    H = None

    if data.get("homography") is not None:
        H = np.array(data["homography"], dtype=np.float32)

    print(f"[LOADED] {len(image_points)} calibration points.")

    return image_points, robot_points, H


# ==============================================================================
# DRAW WINDOWS
# ==============================================================================

def draw_main_ui(
    frame,
    image_points,
    H,
    detection,
    jog_x,
    jog_y,
    jog_z,
    jog_step,
    locked_target_pixel,
    locked_target_robot
):
    h, w = frame.shape[:2]

    overlay = frame.copy()
    cv2.rectangle(overlay, (0, 0), (w, 95), (0, 0, 0), -1)
    frame = cv2.addWeighted(overlay, 0.55, frame, 0.45, 0)

    mode = "READY" if H is not None else "CALIBRATION REQUIRED"

    top_lines = [
        f"Mode: {mode} | Points: {len(image_points)}/4 min | Jog: X={jog_x:.1f}, Y={jog_y:.1f}, Z={jog_z:.1f}, Step={jog_step:.1f}",
        "Use Instructions window for keys. Main keys: T=lock pixel, A=add calibration, C=compute, B=move locked target."
    ]

    y = 28

    for line in top_lines:
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )
        y += 30

    for i, point in enumerate(image_points):
        u, v = int(point[0]), int(point[1])
        cv2.circle(frame, (u, v), 6, (255, 0, 255), -1)
        cv2.putText(
            frame,
            f"P{i + 1}",
            (u + 8, v - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 0, 255),
            2
        )

    if locked_target_pixel is not None:
        lu = int(locked_target_pixel[0])
        lv = int(locked_target_pixel[1])

        cv2.circle(frame, (lu, lv), 14, (255, 255, 0), 2)
        cv2.line(frame, (lu - 15, lv), (lu + 15, lv), (255, 255, 0), 2)
        cv2.line(frame, (lu, lv - 15), (lu, lv + 15), (255, 255, 0), 2)

        cv2.putText(
            frame,
            "LOCKED PIXEL",
            (lu + 16, lv),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.55,
            (255, 255, 0),
            2
        )

    if detection is not None:
        u = detection["u"]
        v = detection["v"]

        bottom_text = f"Live red pixel: u={u}, v={v}"

        if H is not None:
            robot_xy = pixel_to_robot(H, u, v)
            if robot_xy is not None:
                x, y_robot = robot_xy
                bottom_text += f" -> Dobot XY: X={x:.2f}, Y={y_robot:.2f}"

        color = (0, 255, 255)
    else:
        bottom_text = "No live red block detected. If pixel is locked, you can still use A or B."
        color = (0, 0, 255)

    cv2.putText(
        frame,
        bottom_text,
        (12, h - 25),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.6,
        color,
        2
    )

    return frame


def draw_help_window(
    image_points,
    H,
    locked_target_pixel,
    locked_target_robot,
    jog_x,
    jog_y,
    jog_z,
    jog_step
):
    help_img = np.zeros((620, 720, 3), dtype=np.uint8)

    if H is None:
        status = "HOMOGRAPHY: NOT READY"
        status_color = (0, 0, 255)
    else:
        status = "HOMOGRAPHY: READY"
        status_color = (0, 255, 0)

    if locked_target_pixel is None:
        lock_status = "LOCKED PIXEL: NONE"
    else:
        lock_status = f"LOCKED PIXEL: u={locked_target_pixel[0]}, v={locked_target_pixel[1]}"

    if locked_target_robot is None:
        robot_lock_status = "LOCKED ROBOT XY: NONE"
    else:
        robot_lock_status = f"LOCKED ROBOT XY: X={locked_target_robot[0]:.2f}, Y={locked_target_robot[1]:.2f}"

    lines = [
        ("DOBOT + CAMERA MAPPING INSTRUCTIONS", (255, 255, 255), 0.75),
        ("", (255, 255, 255), 0.5),

        (status, status_color, 0.65),
        (f"CALIBRATION POINTS: {len(image_points)} / 4 minimum", (0, 255, 255), 0.6),
        (lock_status, (255, 255, 0), 0.55),
        (robot_lock_status, (255, 255, 0), 0.55),
        (f"JOG TARGET: X={jog_x:.1f}, Y={jog_y:.1f}, Z={jog_z:.1f}, STEP={jog_step:.1f}", (255, 255, 255), 0.55),
        ("", (255, 255, 255), 0.5),

        ("FIRST TIME CALIBRATION WORKFLOW:", (0, 255, 255), 0.6),
        ("1. Keep Dobot away from cube.", (255, 255, 255), 0.52),
        ("2. Put red cube at calibration position.", (255, 255, 255), 0.52),
        ("3. Press T to lock cube pixel.", (255, 255, 255), 0.52),
        ("4. Jog Dobot tip to the cube using I/K/J/L/E/Z.", (255, 255, 255), 0.52),
        ("5. Press A to save locked pixel -> current Dobot X/Y.", (255, 255, 255), 0.52),
        ("6. Repeat at least 4 different cube positions.", (255, 255, 255), 0.52),
        ("7. Press C to compute homography, then S to save.", (255, 255, 255), 0.52),
        ("", (255, 255, 255), 0.5),

        ("AFTER CALIBRATION:", (0, 255, 0), 0.6),
        ("T = lock visible cube", (255, 255, 255), 0.52),
        ("B = move Dobot to locked cube", (255, 255, 255), 0.52),
        ("G = move Dobot to live detected cube", (255, 255, 255), 0.52),
        ("", (255, 255, 255), 0.5),

        ("MOVEMENT KEYS:", (0, 255, 255), 0.6),
        ("H = home Dobot", (255, 255, 255), 0.52),
        ("M = manual coordinate input", (255, 255, 255), 0.52),
        ("I/K = X + / X -", (255, 255, 255), 0.52),
        ("J/L = Y - / Y +", (255, 255, 255), 0.52),
        ("E/Z = Z up / Z down", (255, 255, 255), 0.52),
        ("+/- = increase/decrease jog step", (255, 255, 255), 0.52),
        ("P = print current jog target", (255, 255, 255), 0.52),
        ("", (255, 255, 255), 0.5),

        ("CALIBRATION KEYS:", (0, 255, 255), 0.6),
        ("N = next predefined calibration point", (255, 255, 255), 0.52),
        ("A = add calibration point", (255, 255, 255), 0.52),
        ("C = compute homography", (255, 255, 255), 0.52),
        ("S = save calibration", (255, 255, 255), 0.52),
        ("O = load calibration", (255, 255, 255), 0.52),
        ("U = undo last point", (255, 255, 255), 0.52),
        ("R = reset calibration and locked target", (255, 255, 255), 0.52),
        ("Q = quit", (255, 255, 255), 0.52),
    ]

    y = 28

    for text, color, scale in lines:
        if text == "":
            y += 12
            continue

        cv2.putText(
            help_img,
            text,
            (15, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            scale,
            color,
            1 if scale < 0.7 else 2
        )
        y += 22

    return help_img


# ==============================================================================
# INPUT HELPERS
# ==============================================================================

def ask_float(prompt, default=None):
    while True:
        value = input(prompt).strip()

        if value == "" and default is not None:
            return float(default)

        try:
            return float(value)
        except ValueError:
            print("[ERROR] Enter a valid number.")


def manual_input_move(dobot, jog_x, jog_y, jog_z, jog_r):
    print("\n========== Manual Dobot Move ==========")
    x = ask_float(f"X [{jog_x}]: ", jog_x)
    y = ask_float(f"Y [{jog_y}]: ", jog_y)
    z = ask_float(f"Z [{jog_z}]: ", jog_z)
    r = ask_float(f"R [{jog_r}]: ", jog_r)

    dobot.move_to(x, y, z, r)

    return x, y, z, r


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    camera = MVSCamera()
    dobot = DobotController(DOBOT_PORT)

    image_points = []
    robot_points = []
    H = None

    locked_target_pixel = None
    locked_target_robot = None

    next_calibration_index = 0

    jog_x = DEFAULT_X
    jog_y = DEFAULT_Y
    jog_z = DEFAULT_Z
    jog_r = DEFAULT_R
    jog_step = JOG_STEP_DEFAULT

    try:
        camera.open()

        try:
            dobot.connect()
        except Exception as e:
            print(f"[DOBOT WARNING] Could not connect to Dobot: {e}")
            print("[INFO] Camera UI will still run, but movement keys will not work.")
            dobot = None

        create_controls()

        cv2.namedWindow(WINDOW_MAIN, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_MAIN, DISPLAY_W, DISPLAY_H)

        cv2.namedWindow(WINDOW_MASK, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_MASK, 480, 360)

        cv2.namedWindow(WINDOW_HELP, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(WINDOW_HELP, 720, 620)

        print("\n=======================================================")
        print("Dobot + MVS Mapper Started")
        print("A separate Instructions window is open.")
        print("Important first-time workflow: T -> Jog -> A, repeat 4 times, then C and S.")
        print("=======================================================\n")

        while True:
            frame = camera.read()

            if frame is None:
                print("[CAMERA WARNING] Frame grab failed or timed out.")
                key = cv2.waitKey(10) & 0xFF
                if key == ord("q"):
                    break
                continue

            controls = get_controls()

            frame = cv2.resize(frame, (DISPLAY_W, DISPLAY_H), interpolation=cv2.INTER_AREA)

            frame = adjust_brightness_contrast(
                frame,
                brightness=controls["brightness"],
                contrast=controls["contrast"]
            )

            processed_frame, red_mask, detection = detect_red_block(frame, controls)

            processed_frame = draw_main_ui(
                processed_frame,
                image_points,
                H,
                detection,
                jog_x,
                jog_y,
                jog_z,
                jog_step,
                locked_target_pixel,
                locked_target_robot
            )

            help_img = draw_help_window(
                image_points,
                H,
                locked_target_pixel,
                locked_target_robot,
                jog_x,
                jog_y,
                jog_z,
                jog_step
            )

            cv2.imshow(WINDOW_MAIN, processed_frame)
            cv2.imshow(WINDOW_MASK, red_mask)
            cv2.imshow(WINDOW_HELP, help_img)

            key = cv2.waitKey(1) & 0xFF

            # ------------------------------------------------------------------
            # Quit
            # ------------------------------------------------------------------
            if key == ord("q"):
                break

            # ------------------------------------------------------------------
            # Home
            # ------------------------------------------------------------------
            elif key == ord("h"):
                if dobot is None:
                    print("[DOBOT] Not connected.")
                    continue

                try:
                    dobot.home()
                    jog_x = DEFAULT_X
                    jog_y = DEFAULT_Y
                    jog_z = DEFAULT_Z
                    jog_r = DEFAULT_R
                except Exception as e:
                    print(f"[DOBOT ERROR] Homing failed: {e}")

            # ------------------------------------------------------------------
            # Manual coordinate input
            # ------------------------------------------------------------------
            elif key == ord("m"):
                if dobot is None:
                    print("[DOBOT] Not connected.")
                    continue

                try:
                    jog_x, jog_y, jog_z, jog_r = manual_input_move(
                        dobot,
                        jog_x,
                        jog_y,
                        jog_z,
                        jog_r
                    )
                except Exception as e:
                    print(f"[DOBOT ERROR] Manual move failed: {e}")

            # ------------------------------------------------------------------
            # Jog controls
            # ------------------------------------------------------------------
            elif key == ord("i"):
                if dobot is not None:
                    jog_x += jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("k"):
                if dobot is not None:
                    jog_x -= jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("l"):
                if dobot is not None:
                    jog_y += jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("j"):
                if dobot is not None:
                    jog_y -= jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("e"):
                if dobot is not None:
                    jog_z += jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("z"):
                if dobot is not None:
                    jog_z -= jog_step
                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                    print(f"[JOG] X={jog_x}, Y={jog_y}, Z={jog_z}, step={jog_step}")

            elif key == ord("+") or key == ord("="):
                jog_step += 5.0
                print(f"[JOG] Step increased to {jog_step}")

            elif key == ord("-"):
                jog_step = max(1.0, jog_step - 5.0)
                print(f"[JOG] Step decreased to {jog_step}")

            elif key == ord("p"):
                print(f"[CURRENT TARGET] X={jog_x}, Y={jog_y}, Z={jog_z}, R={jog_r}")

            # ------------------------------------------------------------------
            # Next predefined calibration point
            # ------------------------------------------------------------------
            elif key == ord("n"):
                if dobot is None:
                    print("[DOBOT] Not connected.")
                    continue

                if next_calibration_index >= len(CALIBRATION_ROBOT_POINTS):
                    print("[INFO] All predefined calibration points completed.")
                    continue

                x, y = CALIBRATION_ROBOT_POINTS[next_calibration_index]

                try:
                    jog_x = float(x)
                    jog_y = float(y)
                    jog_z = DEFAULT_Z
                    jog_r = DEFAULT_R

                    dobot.move_to(jog_x, jog_y, jog_z, jog_r)

                    print(f"[CALIBRATION] Dobot moved to P{next_calibration_index + 1}")
                    print(f"[CALIBRATION] Robot coordinate: X={jog_x}, Y={jog_y}")
                    print("[CALIBRATION] When red marker is detected, press A.")

                except Exception as e:
                    print(f"[DOBOT ERROR] Failed to move to calibration point: {e}")

            # ------------------------------------------------------------------
            # Lock pixel only
            # This works BEFORE homography also.
            # ------------------------------------------------------------------
            elif key == ord("t"):
                if detection is None:
                    print("[TARGET] No red block detected. Cannot lock pixel.")
                    continue

                u = detection["u"]
                v = detection["v"]

                locked_target_pixel = [int(u), int(v)]

                print("\n[PIXEL TARGET LOCKED]")
                print(f"Pixel : u={u}, v={v}")

                if H is not None:
                    robot_xy = pixel_to_robot(H, u, v)

                    if robot_xy is not None:
                        x, y = robot_xy
                        locked_target_robot = [float(x), float(y)]

                        print(f"Dobot : X={x:.2f}, Y={y:.2f}")
                        print("Press B to move Dobot to this locked target.")
                    else:
                        locked_target_robot = None
                        print("Homography exists, but conversion failed.")
                else:
                    locked_target_robot = None
                    print("Homography not computed yet.")
                    print("Now manually jog Dobot tip to this cube, then press A.")

            # ------------------------------------------------------------------
            # Add calibration point
            # Uses locked pixel if available.
            # ------------------------------------------------------------------
            elif key == ord("a"):
                if locked_target_pixel is not None:
                    u = locked_target_pixel[0]
                    v = locked_target_pixel[1]
                    source_text = "locked pixel"
                elif detection is not None:
                    u = detection["u"]
                    v = detection["v"]
                    source_text = "live detection"
                else:
                    print("[WARNING] No red block detected and no locked pixel available.")
                    print("First press T while the cube is visible.")
                    continue

                image_points.append([float(u), float(v)])
                robot_points.append([float(jog_x), float(jog_y)])

                print("\n[ADDED CALIBRATION POINT]")
                print(f"P{len(image_points)}")
                print(f"Source       : {source_text}")
                print(f"Camera pixel : u={u}, v={v}")
                print(f"Dobot point  : X={jog_x}, Y={jog_y}")

                if next_calibration_index < len(CALIBRATION_ROBOT_POINTS):
                    next_calibration_index += 1

                locked_target_pixel = None
                locked_target_robot = None

            # ------------------------------------------------------------------
            # Compute homography
            # ------------------------------------------------------------------
            elif key == ord("c"):
                H, status = compute_homography(image_points, robot_points)

                if H is None:
                    print("[ERROR] Homography computation failed.")
                else:
                    print("\n[HOMOGRAPHY COMPUTED]")
                    print(H)
                    print("[STATUS]")
                    print(status)

            # ------------------------------------------------------------------
            # Save calibration
            # ------------------------------------------------------------------
            elif key == ord("s"):
                save_calibration(image_points, robot_points, H)

            # ------------------------------------------------------------------
            # Load calibration
            # ------------------------------------------------------------------
            elif key == ord("o"):
                image_points, robot_points, H = load_calibration()
                next_calibration_index = len(robot_points)

            # ------------------------------------------------------------------
            # Move to locked target
            # ------------------------------------------------------------------
            elif key == ord("b"):
                if dobot is None:
                    print("[DOBOT] Not connected.")
                    continue

                if locked_target_pixel is None:
                    print("[DOBOT] No locked pixel. Press T first when cube is visible.")
                    continue

                if H is None:
                    print("[DOBOT] Homography not computed.")
                    print("For first-time setup: T -> jog to cube -> A. Repeat 4 times. Then C.")
                    continue

                if locked_target_robot is None:
                    u = locked_target_pixel[0]
                    v = locked_target_pixel[1]
                    robot_xy = pixel_to_robot(H, u, v)

                    if robot_xy is None:
                        print("[DOBOT] Could not convert locked pixel to robot XY.")
                        continue

                    locked_target_robot = [float(robot_xy[0]), float(robot_xy[1])]

                x = locked_target_robot[0]
                y = locked_target_robot[1]

                print("\n[MOVE TO LOCKED TARGET]")
                print(f"Target X={x:.2f}, Y={y:.2f}")
                print(f"Safe Z={SAFE_Z:.2f}, Pick/approach Z={PICK_Z:.2f}")

                confirm = input("Type YES to move to locked target: ").strip()

                if confirm == "YES":
                    try:
                        jog_x = float(x)
                        jog_y = float(y)

                        jog_z = SAFE_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                        time.sleep(0.3)

                        jog_z = PICK_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                        time.sleep(0.3)

                        jog_z = SAFE_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)

                        print("[DOBOT] Locked target movement completed.")

                    except Exception as e:
                        print(f"[DOBOT ERROR] Move to locked target failed: {e}")
                else:
                    print("[CANCELLED] Locked target movement cancelled.")

            # ------------------------------------------------------------------
            # Move to live detected target
            # ------------------------------------------------------------------
            elif key == ord("g"):
                if dobot is None:
                    print("[DOBOT] Not connected.")
                    continue

                if H is None:
                    print("[ERROR] Homography not computed yet.")
                    print("First collect at least 4 points and press C.")
                    continue

                if detection is None:
                    print("[ERROR] No red block detected.")
                    continue

                u = detection["u"]
                v = detection["v"]

                robot_xy = pixel_to_robot(H, u, v)

                if robot_xy is None:
                    print("[ERROR] Could not convert pixel to Dobot coordinate.")
                    continue

                x, y = robot_xy

                print("\n[GO TO LIVE DETECTED POINT]")
                print(f"Pixel coordinate: u={u}, v={v}")
                print(f"Mapped Dobot XY : X={x:.2f}, Y={y:.2f}")

                confirm = input("Type YES to move Dobot: ").strip()

                if confirm == "YES":
                    try:
                        jog_x = float(x)
                        jog_y = float(y)

                        jog_z = SAFE_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                        time.sleep(0.3)

                        jog_z = PICK_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)
                        time.sleep(0.3)

                        jog_z = SAFE_Z
                        dobot.move_to(jog_x, jog_y, jog_z, jog_r)

                    except Exception as e:
                        print(f"[DOBOT ERROR] Move failed: {e}")
                else:
                    print("[CANCELLED] Movement cancelled.")

            # ------------------------------------------------------------------
            # Undo last calibration point
            # ------------------------------------------------------------------
            elif key == ord("u"):
                if len(image_points) == 0:
                    print("[INFO] No calibration point to undo.")
                    continue

                removed_img = image_points.pop()
                removed_robot = robot_points.pop()

                next_calibration_index = max(0, next_calibration_index - 1)

                print(f"[UNDO] Removed image point: {removed_img}")
                print(f"[UNDO] Removed robot point: {removed_robot}")

            # ------------------------------------------------------------------
            # Reset calibration
            # ------------------------------------------------------------------
            elif key == ord("r"):
                image_points = []
                robot_points = []
                H = None
                next_calibration_index = 0
                locked_target_pixel = None
                locked_target_robot = None
                print("[RESET] Calibration and locked target cleared.")

    finally:
        camera.close()

        if dobot is not None:
            dobot.close()

        cv2.destroyAllWindows()
        print("Program closed cleanly.")


if __name__ == "__main__":
    main()