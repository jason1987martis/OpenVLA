#Coded to convert pixel coordinates from camera to Dobot coordinates using a homography matrix. The homography matrix is loaded from a file named "homography.npy". The function `pixel_to_dobot` takes pixel coordinates (u, v) as input and returns the corresponding Dobot coordinates (x, y). An example usage is provided at the end, where a pixel coordinate from a red sticker detected by YOLO is converted to Dobot coordinates and printed.
import cv2
import numpy as np

H = np.load("homography.npy")

def pixel_to_dobot(u, v):
    pixel_point = np.array([[[u, v]]], dtype=np.float32)

    robot_point = cv2.perspectiveTransform(pixel_point, H)

    x = robot_point[0][0][0]
    y = robot_point[0][0][1]

    return x, y

# Example camera point from red sticker / YOLO
u = 360
v = 250

x, y = pixel_to_dobot(u, v)

print("Camera pixel:", u, v)
print("Dobot coordinate:", x, y)