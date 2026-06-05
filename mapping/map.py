import cv2
import numpy as np

# Camera pixel points: [u, v]
image_points = np.array([
    [315, 220],
    [420, 220],
    [420, 330],
    [315, 330]
], dtype=np.float32)

# Matching Dobot coordinates: [x, y]
robot_points = np.array([
    [200, -100],
    [250, -100],
    [250, -50],
    [200, -50]
], dtype=np.float32)

# Compute homography
H, status = cv2.findHomography(image_points, robot_points)

print("Homography matrix:")
print(H)

# Save it
np.save("homography.npy", H)
print("Saved homography.npy")