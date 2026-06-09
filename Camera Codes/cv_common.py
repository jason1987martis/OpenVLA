import os
import json
import math
import csv
from datetime import datetime

import cv2
import numpy as np


# ==============================================================================
# COMMON CONFIG
# ==============================================================================

CAMERA_INDEX = 0

DISPLAY_W = 800
DISPLAY_H = 600

CALIBRATION_FILE = "calibration_points.json"
HOMOGRAPHY_FILE = "homography.npy"


# ==============================================================================
# RED DETECTION DEFAULTS
# ==============================================================================

DEFAULT_CONTROLS = {
    "h1_low": 0,
    "h1_high": 12,
    "h2_low": 168,
    "h2_high": 179,
    "s_low": 70,
    "v_low": 50,
    "min_area": 500,
    "max_area": 50000,
    "kernel_size": 5,
    "brightness": 0,
    "contrast": 1.2,
    "min_aspect": 0.4,
    "max_aspect": 2.5,
    "min_circularity": 0.2,
}


# ==============================================================================
# UI TRACKBARS
# ==============================================================================

def nothing(_):
    pass


def create_red_controls(window_name="Controls"):
    cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(window_name, 520, 560)

    cv2.createTrackbar("H1 Low", window_name, DEFAULT_CONTROLS["h1_low"], 179, nothing)
    cv2.createTrackbar("H1 High", window_name, DEFAULT_CONTROLS["h1_high"], 179, nothing)

    cv2.createTrackbar("H2 Low", window_name, DEFAULT_CONTROLS["h2_low"], 179, nothing)
    cv2.createTrackbar("H2 High", window_name, DEFAULT_CONTROLS["h2_high"], 179, nothing)

    cv2.createTrackbar("S Low", window_name, DEFAULT_CONTROLS["s_low"], 255, nothing)
    cv2.createTrackbar("V Low", window_name, DEFAULT_CONTROLS["v_low"], 255, nothing)

    cv2.createTrackbar("Min Area", window_name, DEFAULT_CONTROLS["min_area"], 50000, nothing)
    cv2.createTrackbar("Max Area", window_name, DEFAULT_CONTROLS["max_area"], 100000, nothing)

    cv2.createTrackbar("Kernel", window_name, DEFAULT_CONTROLS["kernel_size"], 25, nothing)

    cv2.createTrackbar("Brightness", window_name, 50, 100, nothing)
    cv2.createTrackbar("Contrast x10", window_name, 12, 30, nothing)

    cv2.createTrackbar("Min Aspect x10", window_name, 4, 50, nothing)
    cv2.createTrackbar("Max Aspect x10", window_name, 25, 50, nothing)

    cv2.createTrackbar("Min Circular x100", window_name, 20, 100, nothing)


def get_red_controls(window_name="Controls"):
    kernel_size = cv2.getTrackbarPos("Kernel", window_name)

    if kernel_size < 1:
        kernel_size = 1

    if kernel_size % 2 == 0:
        kernel_size += 1

    min_area = cv2.getTrackbarPos("Min Area", window_name)
    max_area = cv2.getTrackbarPos("Max Area", window_name)

    if max_area <= min_area:
        max_area = min_area + 1

    brightness_raw = cv2.getTrackbarPos("Brightness", window_name)
    contrast_raw = cv2.getTrackbarPos("Contrast x10", window_name)

    min_aspect_raw = cv2.getTrackbarPos("Min Aspect x10", window_name)
    max_aspect_raw = cv2.getTrackbarPos("Max Aspect x10", window_name)
    min_circular_raw = cv2.getTrackbarPos("Min Circular x100", window_name)

    return {
        "h1_low": cv2.getTrackbarPos("H1 Low", window_name),
        "h1_high": cv2.getTrackbarPos("H1 High", window_name),
        "h2_low": cv2.getTrackbarPos("H2 Low", window_name),
        "h2_high": cv2.getTrackbarPos("H2 High", window_name),
        "s_low": cv2.getTrackbarPos("S Low", window_name),
        "v_low": cv2.getTrackbarPos("V Low", window_name),
        "min_area": min_area,
        "max_area": max_area,
        "kernel_size": kernel_size,
        "brightness": brightness_raw - 50,
        "contrast": max(1, contrast_raw) / 10.0,
        "min_aspect": max(1, min_aspect_raw) / 10.0,
        "max_aspect": max(1, max_aspect_raw) / 10.0,
        "min_circularity": max(0, min_circular_raw) / 100.0,
    }


# ==============================================================================
# IMAGE PROCESSING
# ==============================================================================

def resize_frame(frame, width=DISPLAY_W, height=DISPLAY_H):
    return cv2.resize(frame, (width, height), interpolation=cv2.INTER_AREA)


def adjust_brightness_contrast(frame, brightness=0, contrast=1.0):
    return cv2.convertScaleAbs(frame, alpha=contrast, beta=brightness)


def create_red_mask(frame_bgr, controls):
    hsv = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2HSV)

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

    return red_mask


def contour_circularity(contour):
    area = cv2.contourArea(contour)
    perimeter = cv2.arcLength(contour, True)

    if perimeter <= 0:
        return 0.0

    return float(4.0 * math.pi * area / (perimeter * perimeter))


def contour_to_detection(contour):
    area = cv2.contourArea(contour)
    x, y, w, h = cv2.boundingRect(contour)

    moment = cv2.moments(contour)

    if moment["m00"] != 0:
        u = int(moment["m10"] / moment["m00"])
        v = int(moment["m01"] / moment["m00"])
    else:
        u = x + w // 2
        v = y + h // 2

    aspect_ratio = w / float(h) if h > 0 else 0.0
    circularity = contour_circularity(contour)

    rect = cv2.minAreaRect(contour)
    angle = float(rect[-1])

    return {
        "u": int(u),
        "v": int(v),
        "area": float(area),
        "bbox": [int(x), int(y), int(w), int(h)],
        "aspect_ratio": float(aspect_ratio),
        "circularity": float(circularity),
        "angle": angle,
        "contour": contour,
    }


def is_valid_detection(detection, controls):
    area = detection["area"]
    aspect = detection["aspect_ratio"]
    circularity = detection["circularity"]

    if area < controls["min_area"]:
        return False

    if area > controls["max_area"]:
        return False

    if aspect < controls["min_aspect"]:
        return False

    if aspect > controls["max_aspect"]:
        return False

    if circularity < controls["min_circularity"]:
        return False

    return True


def detect_red_objects(frame_bgr, controls):
    mask = create_red_mask(frame_bgr, controls)

    contours, _ = cv2.findContours(
        mask,
        cv2.RETR_EXTERNAL,
        cv2.CHAIN_APPROX_SIMPLE
    )

    detections = []

    for contour in contours:
        detection = contour_to_detection(contour)

        if is_valid_detection(detection, controls):
            detections.append(detection)

    detections.sort(key=lambda d: d["area"], reverse=True)

    return detections, mask


def draw_detection(frame, detection, label="OBJ", color=(0, 255, 0)):
    x, y, w, h = detection["bbox"]
    u = detection["u"]
    v = detection["v"]
    area = detection["area"]
    circularity = detection["circularity"]
    aspect = detection["aspect_ratio"]
    angle = detection["angle"]

    cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
    cv2.circle(frame, (u, v), 6, (0, 0, 255), -1)

    text = (
        f"{label}: u={u}, v={v}, area={area:.0f}, "
        f"asp={aspect:.2f}, circ={circularity:.2f}, ang={angle:.1f}"
    )

    cv2.putText(
        frame,
        text,
        (x, max(25, y - 8)),
        cv2.FONT_HERSHEY_SIMPLEX,
        0.48,
        color,
        2
    )


# ==============================================================================
# HOMOGRAPHY HELPERS
# ==============================================================================

def load_homography():
    if os.path.exists(HOMOGRAPHY_FILE):
        H = np.load(HOMOGRAPHY_FILE)
        return H.astype(np.float32)

    if os.path.exists(CALIBRATION_FILE):
        with open(CALIBRATION_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        if data.get("homography") is not None:
            return np.array(data["homography"], dtype=np.float32)

    raise FileNotFoundError(
        "Could not find homography. Expected homography.npy or calibration_points.json."
    )


def pixel_to_robot(H, u, v):
    pixel_point = np.array([[[float(u), float(v)]]], dtype=np.float32)
    robot_point = cv2.perspectiveTransform(pixel_point, H)

    x = float(robot_point[0][0][0])
    y = float(robot_point[0][0][1])

    return x, y


def robot_to_pixel(H, x, y):
    H_inv = np.linalg.inv(H)

    robot_point = np.array([[[float(x), float(y)]]], dtype=np.float32)
    pixel_point = cv2.perspectiveTransform(robot_point, H_inv)

    u = float(pixel_point[0][0][0])
    v = float(pixel_point[0][0][1])

    return u, v


def draw_text_panel(frame, lines, start_y=25):
    y = start_y

    for line in lines:
        cv2.putText(
            frame,
            line,
            (12, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.52,
            (255, 255, 255),
            1
        )
        y += 24


def append_csv_row(path, header, row):
    file_exists = os.path.exists(path)

    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        if not file_exists:
            writer.writerow(header)

        writer.writerow(row)


def now_timestamp():
    return datetime.now().isoformat(timespec="seconds")