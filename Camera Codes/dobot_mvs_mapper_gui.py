import os
import sys
import time
import json
import ctypes
import threading

import cv2
import numpy as np

from ctypes import cast, POINTER, c_ubyte

from torch import layout

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QImage, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QHBoxLayout,
    QGridLayout,
    QGroupBox,
    QSlider,
    QTextEdit,
    QMessageBox,
    QDoubleSpinBox,
    QSpinBox,
    QFileDialog,
)

from pydobotplus import Dobot


# ==============================================================================
# CONFIG
# ==============================================================================

DOBOT_PORT = "COM8"

RUNTIME_DIR = r"C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64"

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(PROJECT_DIR, "SDK")


DISPLAY_W = 800
DISPLAY_H = 600

DEFAULT_X = 250.0
DEFAULT_Y = 0.0
DEFAULT_Z = 90.0
DEFAULT_R = 0.0

SAFE_Z = 90.0
PICK_Z = 55.0

JOG_STEP_DEFAULT = 2.0

HOMOGRAPHY_FILE = os.path.join(PROJECT_DIR, "homography.npy")
CALIBRATION_FILE = os.path.join(PROJECT_DIR, "calibration_points.json")


# ==============================================================================
# SAFETY LIMITS
# ==============================================================================

X_MIN = 180.0
X_MAX = 310.0

Y_MIN = -120.0
Y_MAX = 120.0

Z_MIN = 40.0
Z_MAX = 120.0

R_MIN = -90.0
R_MAX = 90.0


# ==============================================================================
# LOAD MVS SDK
# ==============================================================================

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


# ==============================================================================
# SAFETY HELPERS
# ==============================================================================

def clamp_value(value, minimum, maximum):
    return max(minimum, min(maximum, float(value)))


def clamp_pose(x, y, z, r):
    safe_x = clamp_value(x, X_MIN, X_MAX)
    safe_y = clamp_value(y, Y_MIN, Y_MAX)
    safe_z = clamp_value(z, Z_MIN, Z_MAX)
    safe_r = clamp_value(r, R_MIN, R_MAX)

    was_clamped = (
        safe_x != float(x)
        or safe_y != float(y)
        or safe_z != float(z)
        or safe_r != float(r)
    )

    return safe_x, safe_y, safe_z, safe_r, was_clamped


# ==============================================================================
# CAMERA FRAME CONVERSION
# ==============================================================================

def convert_camera_frame(img_raw, width, height, pixel_type):
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

        # Keep this because your earlier setup needed red/blue correction.
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


# ==============================================================================
# DOBOT CONTROLLER
# ==============================================================================

class DobotController:
    def __init__(self, port):
        self.port = port
        self.device = None
        self.connected = False

    def connect(self):
        self.device = Dobot(port=self.port)
        time.sleep(1)
        self.device.clear_alarms()
        self.connected = True

    def home(self):
        self._check()
        self.device.home()

    def move_to(self, x, y, z, r):
        self._check()
        safe_x, safe_y, safe_z, safe_r, was_clamped = clamp_pose(x, y, z, r)
        self.device.move_to(
            x=float(safe_x),
            y=float(safe_y),
            z=float(safe_z),
            r=float(safe_r)
        )
        return safe_x, safe_y, safe_z, safe_r, was_clamped
    
    def suction_on(self):
        self._check()
        self.device.suck(True)
        print("[DOBOT] Suction ON")


    def suction_off(self):
        self._check()
        self.device.suck(False)
        print("[DOBOT] Suction OFF")


    def close(self):
        if self.device is not None:
            self.device.close()
        self.connected = False

    def _check(self):
        if self.device is None or not self.connected:
            raise RuntimeError("Dobot is not connected.")


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

    kernel_size = controls["kernel_size"]
    kernel = np.ones((kernel_size, kernel_size), np.uint8)

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
                "area": float(area),
                "bbox": [x, y, w, h]
            }

            cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cv2.circle(output, (u, v), 7, (0, 0, 255), -1)

            cv2.putText(
                output,
                f"RED u={u}, v={v}, area={int(area)}",
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


def save_calibration(image_points, robot_points, H, path=CALIBRATION_FILE):
    data = {
        "image_points": image_points,
        "robot_points": robot_points,
        "homography": H.tolist() if H is not None else None,
    }

    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4)

    if H is not None:
        np.save(HOMOGRAPHY_FILE, H)


def load_calibration(path=CALIBRATION_FILE):
    if not os.path.exists(path):
        return [], [], None

    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    image_points = data.get("image_points", [])
    robot_points = data.get("robot_points", [])

    H = None

    if data.get("homography") is not None:
        H = np.array(data["homography"], dtype=np.float32)

    return image_points, robot_points, H


# ==============================================================================
# CAMERA THREAD
# ==============================================================================

class CameraThread(QThread):
    frame_ready = Signal(object, object, object)
    status = Signal(str)

    def __init__(self):
        super().__init__()
        self.running = False
        self.camera = None

        self.controls = {
            "h1_low": 0,
            "h1_high": 12,
            "h2_low": 168,
            "h2_high": 179,
            "s_low": 70,
            "v_low": 50,
            "min_area": 500,
            "kernel_size": 5,
            "brightness": 0,
            "contrast": 1.2,
        }

        self.controls_lock = threading.Lock()

    def update_controls(self, controls):
        with self.controls_lock:
            self.controls.update(controls)

    def run(self):
        self.running = True
        self.camera = MVSCamera()

        try:
            self.camera.open()
            self.status.emit("[CAMERA] Started successfully.")
        except Exception as e:
            self.status.emit(f"[CAMERA ERROR] {e}")
            self.running = False
            return

        while self.running:
            frame = self.camera.read()

            if frame is None:
                self.status.emit("[CAMERA WARNING] Frame grab failed.")
                self.msleep(20)
                continue

            frame = cv2.resize(frame, (DISPLAY_W, DISPLAY_H), interpolation=cv2.INTER_AREA)

            with self.controls_lock:
                controls_copy = dict(self.controls)

            frame = adjust_brightness_contrast(
                frame,
                brightness=controls_copy["brightness"],
                contrast=controls_copy["contrast"]
            )

            processed_frame, mask, detection = detect_red_block(frame, controls_copy)

            self.frame_ready.emit(processed_frame, mask, detection)

            self.msleep(15)

        try:
            self.camera.close()
            self.status.emit("[CAMERA] Closed.")
        except Exception as e:
            self.status.emit(f"[CAMERA CLOSE ERROR] {e}")

    def stop(self):
        self.running = False
        self.wait(2000)


# ==============================================================================
# QT IMAGE HELPERS
# ==============================================================================

def bgr_to_pixmap(frame_bgr):
    rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w

    qimg = QImage(
        rgb.data,
        w,
        h,
        bytes_per_line,
        QImage.Format_RGB888
    ).copy()

    return QPixmap.fromImage(qimg)


def gray_to_pixmap(gray):
    rgb = cv2.cvtColor(gray, cv2.COLOR_GRAY2RGB)
    h, w, ch = rgb.shape
    bytes_per_line = ch * w

    qimg = QImage(
        rgb.data,
        w,
        h,
        bytes_per_line,
        QImage.Format_RGB888
    ).copy()

    return QPixmap.fromImage(qimg)


# ==============================================================================
# MAIN GUI
# ==============================================================================

class MainWindow(QMainWindow):
    log_signal = Signal(str)

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Dobot + MVS Homography Mapper - PySide6 GUI")
        self.resize(1450, 900)

        self.camera_thread = None
        self.dobot = DobotController(DOBOT_PORT)

        self.last_frame = None
        self.last_mask = None
        self.last_detection = None

        self.image_points = []
        self.robot_points = []
        self.H = None

        self.locked_target_pixel = None
        self.locked_target_robot = None

        self.jog_x = DEFAULT_X
        self.jog_y = DEFAULT_Y
        self.jog_z = DEFAULT_Z
        self.jog_r = DEFAULT_R
        self.jog_step = JOG_STEP_DEFAULT

        self.dobot_connected = False
        self.move_busy = False

        self.log_signal.connect(self.log)

        self.build_ui()
        self.update_status_panel()
        self.update_controls_to_camera()

    # --------------------------------------------------------------------------
    # UI BUILD
    # --------------------------------------------------------------------------

    def build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)

        root = QHBoxLayout(central)

        # Left side: camera and mask
        left_layout = QVBoxLayout()

        self.camera_label = QLabel("Camera not started")
        self.camera_label.setFixedSize(DISPLAY_W, DISPLAY_H)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setStyleSheet("background-color: #111; color: white; border: 1px solid #444;")

        self.mask_label = QLabel("Red mask")
        self.mask_label.setFixedSize(400, 300)
        self.mask_label.setAlignment(Qt.AlignCenter)
        self.mask_label.setStyleSheet("background-color: #111; color: white; border: 1px solid #444;")

        left_layout.addWidget(self.camera_label)

        mask_row = QHBoxLayout()
        mask_row.addWidget(self.mask_label)
        mask_row.addWidget(self.create_status_group())
        left_layout.addLayout(mask_row)

        # Right side: controls
        right_layout = QVBoxLayout()
        right_layout.addWidget(self.create_connection_group())
        right_layout.addWidget(self.create_jog_group())
        right_layout.addWidget(self.create_calibration_group())
        right_layout.addWidget(self.create_detection_group())
        right_layout.addWidget(self.create_slider_group())
        right_layout.addWidget(self.create_log_group())

        root.addLayout(left_layout, stretch=3)
        root.addLayout(right_layout, stretch=2)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #202124;
            }
            QLabel {
                color: #f1f1f1;
            }
            QGroupBox {
                color: #ffffff;
                font-weight: bold;
                border: 1px solid #555;
                border-radius: 6px;
                margin-top: 8px;
                padding: 8px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0px 4px 0px 4px;
            }
            QPushButton {
                background-color: #3c4043;
                color: white;
                padding: 8px;
                border-radius: 5px;
            }
            QPushButton:hover {
                background-color: #5f6368;
            }
            QPushButton:pressed {
                background-color: #2b2c2f;
            }
            QTextEdit {
                background-color: #111;
                color: #00ff99;
                border: 1px solid #555;
            }
            QSlider::groove:horizontal {
                height: 6px;
                background: #555;
            }
            QSlider::handle:horizontal {
                background: #00aaff;
                width: 14px;
                margin: -5px 0;
                border-radius: 7px;
            }
            QSpinBox, QDoubleSpinBox {
                background-color: #111;
                color: white;
                border: 1px solid #555;
                padding: 4px;
            }
        """)
        
    def suction_on(self):
        if not self.check_dobot_ready():
            return
        try:
            self.dobot.suction_on()
            self.log("[DOBOT] Suction ON")
        except Exception as e:
            self.log(f"[DOBOT ERROR] Suction ON failed: {e}")


    def suction_off(self):
        if not self.check_dobot_ready():
            return
        try:
            self.dobot.suction_off()
            self.log("[DOBOT] Suction OFF")
        except Exception as e:
            self.log(f"[DOBOT ERROR] Suction OFF failed: {e}")    
        

    def create_connection_group(self):
        box = QGroupBox("Connection")
        layout = QGridLayout(box)

        self.btn_start_camera = QPushButton("Start Camera")
        self.btn_stop_camera = QPushButton("Stop Camera")
        self.btn_connect_dobot = QPushButton("Connect Dobot")
        self.btn_disconnect_dobot = QPushButton("Disconnect Dobot")
        self.btn_home = QPushButton("Home Dobot")
        self.btn_emergency = QPushButton("EMERGENCY STOP / DISCONNECT")
        
        self.btn_suction_on = QPushButton("Suction ON")
        self.btn_suction_off = QPushButton("Suction OFF")
        self.btn_suction_on.clicked.connect(self.suction_on)
        self.btn_suction_off.clicked.connect(self.suction_off)
        

        self.btn_start_camera.clicked.connect(self.start_camera)
        self.btn_stop_camera.clicked.connect(self.stop_camera)
        self.btn_connect_dobot.clicked.connect(self.connect_dobot)
        self.btn_disconnect_dobot.clicked.connect(self.disconnect_dobot)
        self.btn_home.clicked.connect(self.home_dobot)
        self.btn_emergency.clicked.connect(self.emergency_disconnect)
        
        self.btn_pick_locked = QPushButton("Pick Locked Cube")
        self.btn_pick_locked.clicked.connect(self.pick_locked_target)
        
        self.btn_drop = QPushButton("Drop / Suction OFF")
        self.btn_drop.clicked.connect(self.drop_here)
        

        self.btn_emergency.setStyleSheet("background-color: #b00020; color: white; font-weight: bold;")

        layout.addWidget(self.btn_start_camera, 0, 0)
        layout.addWidget(self.btn_stop_camera, 0, 1)
        layout.addWidget(self.btn_connect_dobot, 1, 0)
        layout.addWidget(self.btn_disconnect_dobot, 1, 1)
        layout.addWidget(self.btn_home, 2, 0, 1, 2)
        layout.addWidget(self.btn_emergency, 3, 0, 1, 2)
        layout.addWidget(self.btn_suction_on, 4, 0)
        layout.addWidget(self.btn_suction_off, 4, 1)
        layout.addWidget(self.btn_pick_locked, 8, 0, 1, 2)
        layout.addWidget(self.btn_drop, 9, 0, 1, 2)

        return box

    def create_jog_group(self):
        box = QGroupBox("Manual Jog")
        layout = QGridLayout(box)

        self.spin_x = QDoubleSpinBox()
        self.spin_y = QDoubleSpinBox()
        self.spin_z = QDoubleSpinBox()
        self.spin_r = QDoubleSpinBox()
        self.spin_step = QDoubleSpinBox()

        for spin in [self.spin_x, self.spin_y, self.spin_z, self.spin_r]:
            spin.setRange(-500.0, 500.0)
            spin.setDecimals(2)

        self.spin_x.setValue(self.jog_x)
        self.spin_y.setValue(self.jog_y)
        self.spin_z.setValue(self.jog_z)
        self.spin_r.setValue(self.jog_r)

        self.spin_step.setRange(1.0, 20.0)
        self.spin_step.setValue(self.jog_step)
        self.spin_step.setDecimals(1)

        self.spin_x.valueChanged.connect(self.manual_spin_changed)
        self.spin_y.valueChanged.connect(self.manual_spin_changed)
        self.spin_z.valueChanged.connect(self.manual_spin_changed)
        self.spin_r.valueChanged.connect(self.manual_spin_changed)
        self.spin_step.valueChanged.connect(self.step_changed)

        btn_x_plus = QPushButton("X+")
        btn_x_minus = QPushButton("X-")
        btn_y_plus = QPushButton("Y+")
        btn_y_minus = QPushButton("Y-")
        btn_z_plus = QPushButton("Z+")
        btn_z_minus = QPushButton("Z-")
        btn_move_manual = QPushButton("Move to X/Y/Z/R")

        btn_x_plus.clicked.connect(lambda: self.jog("x", +1))
        btn_x_minus.clicked.connect(lambda: self.jog("x", -1))
        btn_y_plus.clicked.connect(lambda: self.jog("y", +1))
        btn_y_minus.clicked.connect(lambda: self.jog("y", -1))
        btn_z_plus.clicked.connect(lambda: self.jog("z", +1))
        btn_z_minus.clicked.connect(lambda: self.jog("z", -1))
        btn_move_manual.clicked.connect(self.move_manual)

        layout.addWidget(QLabel("X"), 0, 0)
        layout.addWidget(self.spin_x, 0, 1)
        layout.addWidget(QLabel("Y"), 1, 0)
        layout.addWidget(self.spin_y, 1, 1)
        layout.addWidget(QLabel("Z"), 2, 0)
        layout.addWidget(self.spin_z, 2, 1)
        layout.addWidget(QLabel("R"), 3, 0)
        layout.addWidget(self.spin_r, 3, 1)
        layout.addWidget(QLabel("Step"), 4, 0)
        layout.addWidget(self.spin_step, 4, 1)

        layout.addWidget(btn_x_minus, 0, 2)
        layout.addWidget(btn_x_plus, 0, 3)
        layout.addWidget(btn_y_minus, 1, 2)
        layout.addWidget(btn_y_plus, 1, 3)
        layout.addWidget(btn_z_minus, 2, 2)
        layout.addWidget(btn_z_plus, 2, 3)
        layout.addWidget(btn_move_manual, 5, 0, 1, 4)

        return box

    def create_calibration_group(self):
        box = QGroupBox("Calibration / Target")
        layout = QGridLayout(box)

        btn_lock = QPushButton("T - Lock Visible Cube Pixel")
        btn_unlock = QPushButton("X - Unlock / Clear Target")
        btn_add = QPushButton("A - Add Calibration Point")
        btn_compute = QPushButton("C - Compute Homography")
        btn_save = QPushButton("S - Save Calibration")
        btn_load = QPushButton("O - Load Calibration")
        btn_undo = QPushButton("U - Undo Last Point")
        btn_reset = QPushButton("R - Reset Calibration")
        btn_move_locked = QPushButton("B - Move to Locked Cube")
        btn_move_live = QPushButton("G - Move to Live Detected Cube")

        btn_lock.clicked.connect(self.lock_pixel)
        btn_unlock.clicked.connect(self.unlock_target)
        btn_add.clicked.connect(self.add_calibration_point)
        btn_compute.clicked.connect(self.compute_homography_clicked)
        btn_save.clicked.connect(self.save_calibration_clicked)
        btn_load.clicked.connect(self.load_calibration_clicked)
        btn_undo.clicked.connect(self.undo_point)
        btn_reset.clicked.connect(self.reset_calibration)
        btn_move_locked.clicked.connect(self.move_to_locked_target)
        btn_move_live.clicked.connect(self.move_to_live_target)

        btn_move_locked.setStyleSheet("background-color: #0b8043; color: white; font-weight: bold;")
        btn_move_live.setStyleSheet("background-color: #5e35b1; color: white; font-weight: bold;")

        layout.addWidget(btn_lock, 0, 0, 1, 2)
        layout.addWidget(btn_unlock, 1, 0, 1, 2)
        layout.addWidget(btn_add, 2, 0, 1, 2)
        layout.addWidget(btn_compute, 3, 0)
        layout.addWidget(btn_save, 3, 1)
        layout.addWidget(btn_load, 4, 0)
        layout.addWidget(btn_undo, 4, 1)
        layout.addWidget(btn_reset, 5, 0, 1, 2)
        layout.addWidget(btn_move_locked, 6, 0, 1, 2)
        layout.addWidget(btn_move_live, 7, 0, 1, 2)

        return box

    def create_detection_group(self):
        box = QGroupBox("Current Detection")
        layout = QVBoxLayout(box)

        self.lbl_detection = QLabel("No detection")
        self.lbl_detection.setWordWrap(True)

        self.lbl_instructions = QLabel(
            "First-time calibration:\n"
            "1. Place cube\n"
            "2. Lock pixel\n"
            "3. Jog Dobot tip to cube\n"
            "4. Add calibration point\n"
            "Repeat 4+ times, then compute homography."
        )
        self.lbl_instructions.setWordWrap(True)

        layout.addWidget(self.lbl_detection)
        layout.addWidget(self.lbl_instructions)

        return box

    def create_slider_group(self):
        box = QGroupBox("Vision Controls")
        layout = QGridLayout(box)

        self.sliders = {}

        self.add_slider(layout, "H1 Low", "h1_low", 0, 179, 0, 0)
        self.add_slider(layout, "H1 High", "h1_high", 0, 179, 12, 1)
        self.add_slider(layout, "H2 Low", "h2_low", 0, 179, 168, 2)
        self.add_slider(layout, "H2 High", "h2_high", 0, 179, 179, 3)
        self.add_slider(layout, "S Low", "s_low", 0, 255, 70, 4)
        self.add_slider(layout, "V Low", "v_low", 0, 255, 50, 5)
        self.add_slider(layout, "Min Area", "min_area", 0, 20000, 500, 6)
        self.add_slider(layout, "Kernel", "kernel_size", 1, 25, 5, 7)
        self.add_slider(layout, "Brightness", "brightness_raw", 0, 100, 50, 8)
        self.add_slider(layout, "Contrast x10", "contrast_raw", 1, 30, 12, 9)

        return box

    def add_slider(self, layout, label_text, key, minimum, maximum, value, row):
        label = QLabel(f"{label_text}: {value}")
        slider = QSlider(Qt.Horizontal)
        slider.setRange(minimum, maximum)
        slider.setValue(value)

        slider.valueChanged.connect(
            lambda val, lbl=label, name=label_text: self.slider_changed(lbl, name, val)
        )

        self.sliders[key] = slider

        layout.addWidget(label, row, 0)
        layout.addWidget(slider, row, 1)

    def create_status_group(self):
        box = QGroupBox("Status")
        layout = QVBoxLayout(box)

        self.lbl_status = QLabel()
        self.lbl_status.setWordWrap(True)

        layout.addWidget(self.lbl_status)

        return box

    def create_log_group(self):
        box = QGroupBox("Log")
        layout = QVBoxLayout(box)

        self.log_box = QTextEdit()
        self.log_box.setReadOnly(True)
        self.log_box.setMinimumHeight(160)

        layout.addWidget(self.log_box)

        return box

    # --------------------------------------------------------------------------
    # LOGGING / STATUS
    # --------------------------------------------------------------------------

    def log(self, message):
        self.log_box.append(message)
        print(message)

    def update_status_panel(self):
        homography_status = "READY" if self.H is not None else "NOT READY"

        if self.locked_target_pixel is None:
            locked_pixel_text = "None"
        else:
            locked_pixel_text = f"u={self.locked_target_pixel[0]}, v={self.locked_target_pixel[1]}"

        if self.locked_target_robot is None:
            locked_robot_text = "None"
        else:
            locked_robot_text = (
                f"X={self.locked_target_robot[0]:.2f}, "
                f"Y={self.locked_target_robot[1]:.2f}"
            )

        self.lbl_status.setText(
            f"Camera: {'Running' if self.camera_thread and self.camera_thread.running else 'Stopped'}\n"
            f"Dobot: {'Connected' if self.dobot_connected else 'Disconnected'}\n"
            f"Homography: {homography_status}\n"
            f"Calibration Points: {len(self.image_points)} / 4 minimum\n"
            f"Locked Pixel: {locked_pixel_text}\n"
            f"Locked Robot XY: {locked_robot_text}\n"
            f"Jog Target:\n"
            f"  X={self.jog_x:.2f}\n"
            f"  Y={self.jog_y:.2f}\n"
            f"  Z={self.jog_z:.2f}\n"
            f"  R={self.jog_r:.2f}\n"
            f"Step: {self.jog_step:.2f}\n"
            f"Safe Limits:\n"
            f"  X {X_MIN} to {X_MAX}\n"
            f"  Y {Y_MIN} to {Y_MAX}\n"
            f"  Z {Z_MIN} to {Z_MAX}"
        )

    def update_detection_label(self):
        if self.last_detection is None:
            self.lbl_detection.setText("No red cube detected.")
            return

        u = self.last_detection["u"]
        v = self.last_detection["v"]
        area = self.last_detection["area"]

        text = f"Live Detection:\nPixel u={u}, v={v}\nArea={area:.0f}"

        if self.H is not None:
            robot_xy = pixel_to_robot(self.H, u, v)
            if robot_xy is not None:
                text += f"\nMapped XY:\nX={robot_xy[0]:.2f}, Y={robot_xy[1]:.2f}"

        self.lbl_detection.setText(text)

    # --------------------------------------------------------------------------
    # CAMERA
    # --------------------------------------------------------------------------

    def start_camera(self):
        if self.camera_thread is not None and self.camera_thread.running:
            self.log("[CAMERA] Already running.")
            return

        self.camera_thread = CameraThread()
        self.camera_thread.frame_ready.connect(self.on_frame_ready)
        self.camera_thread.status.connect(self.log_signal.emit)
        self.camera_thread.start()

        self.log("[CAMERA] Starting...")
        self.update_status_panel()

    def stop_camera(self):
        if self.camera_thread is not None:
            self.camera_thread.stop()
            self.camera_thread = None
            self.log("[CAMERA] Stopped.")

        self.update_status_panel()

    def on_frame_ready(self, frame, mask, detection):
        self.last_frame = frame
        self.last_mask = mask
        self.last_detection = detection

        display_frame = frame.copy()
        self.draw_overlay(display_frame)

        self.camera_label.setPixmap(bgr_to_pixmap(display_frame))
        self.mask_label.setPixmap(
            gray_to_pixmap(mask).scaled(
                self.mask_label.width(),
                self.mask_label.height(),
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
        )

        self.update_detection_label()
        self.update_status_panel()

    def draw_overlay(self, frame):
        for i, point in enumerate(self.image_points):
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

        if self.locked_target_pixel is not None:
            lu = int(self.locked_target_pixel[0])
            lv = int(self.locked_target_pixel[1])

            cv2.circle(frame, (lu, lv), 14, (255, 255, 0), 2)
            cv2.line(frame, (lu - 15, lv), (lu + 15, lv), (255, 255, 0), 2)
            cv2.line(frame, (lu, lv - 15), (lu, lv + 15), (255, 255, 0), 2)

            cv2.putText(
                frame,
                "LOCKED",
                (lu + 16, lv),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 0),
                2
            )

        mode = "READY" if self.H is not None else "CALIBRATION REQUIRED"

        text = (
            f"{mode} | Points: {len(self.image_points)}/4 | "
            f"Jog X={self.jog_x:.1f}, Y={self.jog_y:.1f}, Z={self.jog_z:.1f}"
        )

        cv2.rectangle(frame, (0, 0), (DISPLAY_W, 35), (0, 0, 0), -1)
        cv2.putText(
            frame,
            text,
            (10, 24),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.58,
            (255, 255, 255),
            2
        )

    # --------------------------------------------------------------------------
    # VISION CONTROLS
    # --------------------------------------------------------------------------

    def slider_changed(self, label, name, value):
        label.setText(f"{name}: {value}")
        self.update_controls_to_camera()

    def update_controls_to_camera(self):
        kernel = self.sliders["kernel_size"].value()

        if kernel < 1:
            kernel = 1

        if kernel % 2 == 0:
            kernel += 1

        controls = {
            "h1_low": self.sliders["h1_low"].value(),
            "h1_high": self.sliders["h1_high"].value(),
            "h2_low": self.sliders["h2_low"].value(),
            "h2_high": self.sliders["h2_high"].value(),
            "s_low": self.sliders["s_low"].value(),
            "v_low": self.sliders["v_low"].value(),
            "min_area": self.sliders["min_area"].value(),
            "kernel_size": kernel,
            "brightness": self.sliders["brightness_raw"].value() - 50,
            "contrast": max(1, self.sliders["contrast_raw"].value()) / 10.0,
        }

        if self.camera_thread is not None:
            self.camera_thread.update_controls(controls)

    # --------------------------------------------------------------------------
    # DOBOT CONNECTION / MOVEMENT
    # --------------------------------------------------------------------------

    def connect_dobot(self):
        if self.dobot_connected:
            self.log("[DOBOT] Already connected.")
            return

        def worker():
            try:
                self.log_signal.emit(f"[DOBOT] Connecting on {DOBOT_PORT}...")
                self.dobot.connect()
                self.dobot_connected = True
                self.log_signal.emit("[DOBOT] Connected.")
            except Exception as e:
                self.dobot_connected = False
                self.log_signal.emit(f"[DOBOT ERROR] Connection failed: {e}")

        threading.Thread(target=worker, daemon=True).start()

    def disconnect_dobot(self):
        try:
            self.dobot.close()
            self.dobot_connected = False
            self.log("[DOBOT] Disconnected.")
        except Exception as e:
            self.log(f"[DOBOT ERROR] Disconnect failed: {e}")

        self.update_status_panel()

    def emergency_disconnect(self):
        self.log("[EMERGENCY] Disconnect requested.")

        try:
            self.dobot.close()
        except Exception:
            pass

        self.dobot_connected = False
        self.move_busy = False
        self.update_status_panel()

        QMessageBox.warning(
            self,
            "Emergency Disconnect",
            "Dobot connection was closed.\n"
            "If the arm is still moving, use the physical power/emergency stop."
        )

    def home_dobot(self):
        if not self.check_dobot_ready():
            return

        confirm = QMessageBox.question(
            self,
            "Home Dobot",
            "Home Dobot now? The arm will move.",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        def worker():
            try:
                self.move_busy = True
                self.log_signal.emit("[DOBOT] Homing started...")
                self.dobot.home()

                self.jog_x = DEFAULT_X
                self.jog_y = DEFAULT_Y
                self.jog_z = DEFAULT_Z
                self.jog_r = DEFAULT_R

                self.log_signal.emit("[DOBOT] Homing completed.")
            except Exception as e:
                self.log_signal.emit(f"[DOBOT ERROR] Homing failed: {e}")
            finally:
                self.move_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def check_dobot_ready(self):
        if not self.dobot_connected:
            QMessageBox.warning(self, "Dobot Not Connected", "Connect Dobot first.")
            return False

        if self.move_busy:
            QMessageBox.warning(self, "Dobot Busy", "Wait for current movement to finish.")
            return False

        return True

    def move_async(self, x, y, z, r, label="Move"):
        if not self.check_dobot_ready():
            return

        def worker():
            try:
                self.move_busy = True

                safe_x, safe_y, safe_z, safe_r, was_clamped = self.dobot.move_to(x, y, z, r)

                self.jog_x = safe_x
                self.jog_y = safe_y
                self.jog_z = safe_z
                self.jog_r = safe_r

                self.log_signal.emit(
                    f"[DOBOT] {label}: X={safe_x:.2f}, Y={safe_y:.2f}, Z={safe_z:.2f}, R={safe_r:.2f}"
                )

                if was_clamped:
                    self.log_signal.emit("[SAFETY] Requested pose was outside limits and was clamped.")

                self.set_spin_values_from_jog()

            except Exception as e:
                self.log_signal.emit(f"[DOBOT ERROR] {label} failed: {e}")
            finally:
                self.move_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def move_sequence_async(self, sequence, label="Sequence"):
        if not self.check_dobot_ready():
            return

        def worker():
            try:
                self.move_busy = True

                for i, pose in enumerate(sequence):
                    x, y, z, r = pose
                    safe_x, safe_y, safe_z, safe_r, was_clamped = self.dobot.move_to(x, y, z, r)

                    self.jog_x = safe_x
                    self.jog_y = safe_y
                    self.jog_z = safe_z
                    self.jog_r = safe_r

                    self.log_signal.emit(
                        f"[DOBOT] {label} step {i + 1}: "
                        f"X={safe_x:.2f}, Y={safe_y:.2f}, Z={safe_z:.2f}, R={safe_r:.2f}"
                    )

                    if was_clamped:
                        self.log_signal.emit("[SAFETY] Requested pose was outside limits and was clamped.")

                    time.sleep(0.3)

                self.set_spin_values_from_jog()
                self.log_signal.emit(f"[DOBOT] {label} completed.")

            except Exception as e:
                self.log_signal.emit(f"[DOBOT ERROR] {label} failed: {e}")
            finally:
                self.move_busy = False

        threading.Thread(target=worker, daemon=True).start()

    def set_spin_values_from_jog(self):
        self.spin_x.blockSignals(True)
        self.spin_y.blockSignals(True)
        self.spin_z.blockSignals(True)
        self.spin_r.blockSignals(True)

        self.spin_x.setValue(self.jog_x)
        self.spin_y.setValue(self.jog_y)
        self.spin_z.setValue(self.jog_z)
        self.spin_r.setValue(self.jog_r)

        self.spin_x.blockSignals(False)
        self.spin_y.blockSignals(False)
        self.spin_z.blockSignals(False)
        self.spin_r.blockSignals(False)

    def manual_spin_changed(self):
        self.jog_x = self.spin_x.value()
        self.jog_y = self.spin_y.value()
        self.jog_z = self.spin_z.value()
        self.jog_r = self.spin_r.value()
        self.update_status_panel()

    def step_changed(self):
        self.jog_step = self.spin_step.value()
        self.update_status_panel()

    def jog(self, axis, direction):
        if axis == "x":
            self.jog_x += direction * self.jog_step
        elif axis == "y":
            self.jog_y += direction * self.jog_step
        elif axis == "z":
            self.jog_z += direction * self.jog_step

        self.move_async(self.jog_x, self.jog_y, self.jog_z, self.jog_r, label=f"Jog {axis.upper()}")

    def move_manual(self):
        self.jog_x = self.spin_x.value()
        self.jog_y = self.spin_y.value()
        self.jog_z = self.spin_z.value()
        self.jog_r = self.spin_r.value()

        self.move_async(self.jog_x, self.jog_y, self.jog_z, self.jog_r, label="Manual move")

    # --------------------------------------------------------------------------
    # CALIBRATION / TARGET LOGIC
    # --------------------------------------------------------------------------

    def lock_pixel(self):
        if self.last_detection is None:
            QMessageBox.warning(self, "No Detection", "No red cube detected.")
            return

        u = self.last_detection["u"]
        v = self.last_detection["v"]

        self.locked_target_pixel = [int(u), int(v)]
        self.locked_target_robot = None

        self.log(f"[LOCKED PIXEL] u={u}, v={v}")

        if self.H is not None:
            robot_xy = pixel_to_robot(self.H, u, v)

            if robot_xy is not None:
                self.locked_target_robot = [float(robot_xy[0]), float(robot_xy[1])]
                self.log(
                    f"[LOCKED ROBOT XY] X={robot_xy[0]:.2f}, Y={robot_xy[1]:.2f}"
                )

        else:
            self.log("[INFO] Homography not ready. Jog Dobot tip to cube, then Add Calibration Point.")

        self.update_status_panel()

    def unlock_target(self):
        self.locked_target_pixel = None
        self.locked_target_robot = None
        self.log("[UNLOCKED] Target cleared.")
        self.update_status_panel()

    def add_calibration_point(self):
        if self.locked_target_pixel is not None:
            u = self.locked_target_pixel[0]
            v = self.locked_target_pixel[1]
            source = "locked pixel"
        elif self.last_detection is not None:
            u = self.last_detection["u"]
            v = self.last_detection["v"]
            source = "live detection"
        else:
            QMessageBox.warning(
                self,
                "No Pixel Available",
                "No locked pixel and no live red detection.\nPress Lock Pixel first."
            )
            return

        self.image_points.append([float(u), float(v)])
        self.robot_points.append([float(self.jog_x), float(self.jog_y)])

        self.log(
            f"[CALIBRATION ADDED] P{len(self.image_points)} | "
            f"Source={source} | Pixel=({u}, {v}) -> "
            f"Robot=(X={self.jog_x:.2f}, Y={self.jog_y:.2f})"
        )

        self.locked_target_pixel = None
        self.locked_target_robot = None

        self.update_status_panel()

    def compute_homography_clicked(self):
        H, status = compute_homography(self.image_points, self.robot_points)

        if H is None:
            QMessageBox.warning(
                self,
                "Homography Failed",
                "Need at least 4 calibration points."
            )
            self.log("[ERROR] Need at least 4 calibration point pairs.")
            return

        self.H = H
        self.log("[HOMOGRAPHY COMPUTED]")
        self.log(str(self.H))
        self.update_status_panel()

    def save_calibration_clicked(self):
        try:
            save_calibration(self.image_points, self.robot_points, self.H)
            self.log(f"[SAVED] {CALIBRATION_FILE}")
            self.log(f"[SAVED] {HOMOGRAPHY_FILE}")
        except Exception as e:
            QMessageBox.critical(self, "Save Failed", str(e))
            self.log(f"[SAVE ERROR] {e}")

    def load_calibration_clicked(self):
        try:
            self.image_points, self.robot_points, self.H = load_calibration()

            if len(self.image_points) == 0:
                QMessageBox.information(
                    self,
                    "No Calibration Found",
                    f"No calibration file found at:\n{CALIBRATION_FILE}"
                )

            self.log(f"[LOADED] {len(self.image_points)} calibration points.")
            self.update_status_panel()

        except Exception as e:
            QMessageBox.critical(self, "Load Failed", str(e))
            self.log(f"[LOAD ERROR] {e}")

    def undo_point(self):
        if len(self.image_points) == 0:
            self.log("[UNDO] No calibration points to remove.")
            return

        removed_img = self.image_points.pop()
        removed_robot = self.robot_points.pop()

        self.log(f"[UNDO] Removed image point {removed_img}")
        self.log(f"[UNDO] Removed robot point {removed_robot}")

        self.update_status_panel()

    def reset_calibration(self):
        confirm = QMessageBox.question(
            self,
            "Reset Calibration",
            "Clear all calibration points, homography, and locked target?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        self.image_points = []
        self.robot_points = []
        self.H = None
        self.locked_target_pixel = None
        self.locked_target_robot = None

        self.log("[RESET] Calibration and locked target cleared.")
        self.update_status_panel()

    # --------------------------------------------------------------------------
    # TARGET MOVEMENT
    # --------------------------------------------------------------------------

    # def move_to_locked_target(self):
    #     if self.locked_target_pixel is None:
    #         QMessageBox.warning(self, "No Locked Target", "Lock the cube pixel first.")
    #         return

    #     if self.H is None:
    #         QMessageBox.warning(
    #             self,
    #             "Homography Not Ready",
    #             "First calibrate:\nLock Pixel -> Jog to Cube -> Add Point.\nRepeat 4+ times, then Compute Homography."
    #         )
    #         return

    #     if self.locked_target_robot is None:
    #         u = self.locked_target_pixel[0]
    #         v = self.locked_target_pixel[1]

    #         robot_xy = pixel_to_robot(self.H, u, v)

    #         if robot_xy is None:
    #             QMessageBox.warning(self, "Mapping Failed", "Could not map locked pixel to Dobot XY.")
    #             return

    #         self.locked_target_robot = [float(robot_xy[0]), float(robot_xy[1])]

    #     x = self.locked_target_robot[0]
    #     y = self.locked_target_robot[1]

    #     confirm = QMessageBox.question(
    #         self,
    #         "Move to Locked Target",
    #         f"Move Dobot to locked cube?\n\n"
    #         f"X={x:.2f}, Y={y:.2f}\n"
    #         f"Safe Z={SAFE_Z:.2f}\n"
    #         f"Pick Z={PICK_Z:.2f}\n\n"
    #         f"The arm will move.",
    #         QMessageBox.Yes | QMessageBox.No
    #     )

    #     if confirm != QMessageBox.Yes:
    #         return

    #     sequence = [
    #         (x, y, SAFE_Z, self.jog_r),
    #         (x, y, PICK_Z, self.jog_r),
    #         (x, y, SAFE_Z, self.jog_r),
    #     ]

    #     self.move_sequence_async(sequence, label="Move to locked target")

    def drop_here(self):
        if not self.check_dobot_ready():
            return

        confirm = QMessageBox.question(
            self,
            "Drop Object",
            "Turn suction OFF here?",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        try:
            self.dobot.suction_off()
            self.log("[DROP] Suction OFF. Object released.")
        except Exception as e:
            self.log(f"[DROP ERROR] {e}")



    def pick_locked_target(self):
        if self.locked_target_pixel is None:
            QMessageBox.warning(self, "No Locked Target", "Lock the cube pixel first.")
            return

        if self.H is None:
            QMessageBox.warning(self, "Homography Not Ready", "Compute homography first.")
            return

        if self.locked_target_robot is None:
            u = self.locked_target_pixel[0]
            v = self.locked_target_pixel[1]

            robot_xy = pixel_to_robot(self.H, u, v)

            if robot_xy is None:
                QMessageBox.warning(self, "Mapping Failed", "Could not map locked pixel to Dobot XY.")
                return

            self.locked_target_robot = [float(robot_xy[0]), float(robot_xy[1])]

        x = self.locked_target_robot[0]
        y = self.locked_target_robot[1]

        confirm = QMessageBox.question(
            self,
            "Pick Locked Target",
            f"Pick cube at:\n\nX={x:.2f}, Y={y:.2f}\nSafe Z={SAFE_Z:.2f}\nPick Z={PICK_Z:.2f}",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        def worker():
            try:
                self.move_busy = True

                self.log_signal.emit("[PICK] Moving above cube...")
                self.dobot.move_to(x, y, SAFE_Z, self.jog_r)
                time.sleep(0.3)

                self.log_signal.emit("[PICK] Moving down...")
                self.dobot.move_to(x, y, PICK_Z, self.jog_r)
                time.sleep(0.3)

                self.log_signal.emit("[PICK] Suction ON...")
                self.dobot.suction_on()
                time.sleep(0.8)

                self.log_signal.emit("[PICK] Lifting cube...")
                self.dobot.move_to(x, y, SAFE_Z, self.jog_r)
                time.sleep(0.3)

                self.jog_x = x
                self.jog_y = y
                self.jog_z = SAFE_Z

                self.set_spin_values_from_jog()

                self.log_signal.emit("[PICK] Pick completed.")

            except Exception as e:
                self.log_signal.emit(f"[PICK ERROR] {e}")
            finally:
                self.move_busy = False
        threading.Thread(target=worker, daemon=True).start()

    def move_to_live_target(self):
        if self.last_detection is None:
            QMessageBox.warning(self, "No Detection", "No live red cube detected.")
            return

        if self.H is None:
            QMessageBox.warning(
                self,
                "Homography Not Ready",
                "Compute homography before using live movement."
            )
            return

        u = self.last_detection["u"]
        v = self.last_detection["v"]

        robot_xy = pixel_to_robot(self.H, u, v)

        if robot_xy is None:
            QMessageBox.warning(self, "Mapping Failed", "Could not map live pixel to Dobot XY.")
            return

        x = float(robot_xy[0])
        y = float(robot_xy[1])

        confirm = QMessageBox.question(
            self,
            "Move to Live Target",
            f"Move Dobot to live detected cube?\n\n"
            f"Pixel u={u}, v={v}\n"
            f"Mapped X={x:.2f}, Y={y:.2f}\n\n"
            f"Recommended: use Lock Pixel then Move to Locked Cube instead.",
            QMessageBox.Yes | QMessageBox.No
        )

        if confirm != QMessageBox.Yes:
            return

        sequence = [
            (x, y, SAFE_Z, self.jog_r),
            (x, y, PICK_Z, self.jog_r),
            (x, y, SAFE_Z, self.jog_r),
        ]

        self.move_sequence_async(sequence, label="Move to live target")

    # --------------------------------------------------------------------------
    # KEYBOARD SHORTCUTS
    # --------------------------------------------------------------------------

    def keyPressEvent(self, event):
        key = event.key()

        if key == Qt.Key_T:
            self.lock_pixel()
        elif key == Qt.Key_X:
            self.unlock_target()
        elif key == Qt.Key_A:
            self.add_calibration_point()
        elif key == Qt.Key_C:
            self.compute_homography_clicked()
        elif key == Qt.Key_S:
            self.save_calibration_clicked()
        elif key == Qt.Key_O:
            self.load_calibration_clicked()
        elif key == Qt.Key_U:
            self.undo_point()
        elif key == Qt.Key_R:
            self.reset_calibration()
        elif key == Qt.Key_B:
            self.move_to_locked_target()
        elif key == Qt.Key_G:
            self.move_to_live_target()
        elif key == Qt.Key_H:
            self.home_dobot()
        elif key == Qt.Key_I:
            self.jog("x", +1)
        elif key == Qt.Key_K:
            self.jog("x", -1)
        elif key == Qt.Key_L:
            self.jog("y", +1)
        elif key == Qt.Key_J:
            self.jog("y", -1)
        elif key == Qt.Key_E:
            self.jog("z", +1)
        elif key == Qt.Key_Z:
            self.jog("z", -1)
        elif key == Qt.Key_V:
            self.suction_on()
        elif key == Qt.Key_F:
            self.suction_off()    
        elif key == Qt.Key_Q:
            self.close()
        else:
            super().keyPressEvent(event)

    # --------------------------------------------------------------------------
    # CLOSE EVENT
    # --------------------------------------------------------------------------

    def closeEvent(self, event):
        try:
            self.stop_camera()
        except Exception:
            pass

        try:
            self.dobot.close()
        except Exception:
            pass

        event.accept()


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()