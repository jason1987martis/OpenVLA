# Dobot + Hikrobot MVS Camera Homography Mapper

This project provides an interactive computer-vision mapping system for a **Dobot Magician** and a **Hikrobot/Hikvision MVS industrial camera**.

The goal is to detect a red cube or red marker in the camera image, map its camera pixel coordinate to Dobot robot coordinates using homography, and then move the Dobot to the detected target position.

The system supports:

* Hikrobot/MVS industrial camera streaming
* Red object detection using HSV thresholding
* Brightness and contrast tuning through OpenCV sliders
* Manual Dobot jogging
* Pixel locking before calibration
* Homography calibration
* Saving and loading calibration data
* Moving Dobot to a locked target
* Separate instruction window to keep the main camera feed clean

---

## 1. Project Structure

Recommended folder structure:

```text
MappingCode/
│
├── dobot_mvs_mapper_final.py
├── calibration_points.json          # generated after saving calibration
├── homography.npy                   # generated after saving homography
├── README.md
│
└── SDK/
    ├── MvCameraControl_class.py
    ├── CameraParams_header.py
    ├── MvErrorDefine_const.py
    ├── PixelType_header.py
    ├── PixelType_const.py
    └── other MVS Python SDK support files
```

The `SDK` folder should contain the Python wrapper files from the Hikrobot/MVS SDK `MvImport` folder.

---

## 2. Important SDK Path Change

This project expects the Hikrobot/MVS Python SDK files to be inside:

```text
MappingCode/SDK/
```

So the main script should include this SDK path:

```python
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
SDK_DIR = os.path.join(PROJECT_DIR, "SDK")

if os.path.exists(os.path.join(SDK_DIR, "MvCameraControl_class.py")):
    sys.path.append(SDK_DIR)
    print(f"[MVS] Using local SDK folder: {SDK_DIR}")
else:
    print("[CRITICAL ERROR] Could not find MvCameraControl_class.py in SDK folder.")
    print("Please copy the MVS Python SDK files into:")
    print(SDK_DIR)
    sys.exit()
```

This is better than depending on the SDK installation path because the project becomes portable.

---

## 3. Required Hardware

* Dobot Magician
* Hikrobot/Hikvision MVS industrial camera
* Red cube, red tape, or red marker
* Windows PC
* USB connection for Dobot
* USB/GigE connection for camera

---

## 4. Required Software

Install:

* Python 3.10 or 3.11 recommended
* Hikrobot MVS software and runtime
* Dobot driver/software
* Python packages:

```bash
pip install opencv-python numpy pydobotplus
```

If you use Python 3.13 and face SDK or serial issues, switch to Python 3.10 or 3.11.

---

## 5. MVS Runtime Requirement

The script uses the MVS runtime DLL from:

```text
C:\Program Files (x86)\Common Files\MVS\Runtime\Win64_x64
```

The important DLL is:

```text
MvCameraControl.dll
```

If the script cannot find this folder, install or reinstall the Hikrobot MVS software.

---

## 6. Copying the MVS SDK Files

Find the MVS Python SDK folder on your system. It is usually located at one of these paths:

```text
C:\Program Files (x86)\MVS\Development\Samples\Python\MvImport
C:\Program Files\MVS\Development\Samples\Python\MvImport
C:\Program Files (x86)\Hikrobot\MVS\Development\Samples\Python\MvImport
```

Copy the contents of `MvImport` into:

```text
MappingCode/SDK/
```

At minimum, the `SDK` folder should contain:

```text
MvCameraControl_class.py
CameraParams_header.py
MvErrorDefine_const.py
PixelType_header.py
PixelType_const.py
```

---

## 7. Dobot Port Configuration

By default, the script uses:

```python
DOBOT_PORT = "COM8"
```

If your Dobot is on another COM port, change it in the script:

```python
DOBOT_PORT = "COM3"
```

To check the correct COM port:

1. Open Windows Device Manager.
2. Go to **Ports (COM & LPT)**.
3. Look for the Dobot serial port.
4. Update `DOBOT_PORT` accordingly.

Close DobotStudio or DobotLab before running the script, because they may block the COM port.

---

## 8. Running the Program

From the project folder:

```bash
python dobot_mvs_mapper_final.py
```

Before running:

* Close MVS Viewer.
* Close DobotStudio/DobotLab.
* Connect the camera.
* Connect the Dobot.
* Keep the robot workspace clear.

---

## 9. Windows Opened by the Program

The program opens four windows:

### 1. Main Camera Window

Shows:

* Camera feed
* Red cube detection
* Locked pixel marker
* Calibration points
* Current Dobot jog target
* Live mapped coordinates after homography is ready

### 2. Red Mask Window

Shows the binary mask used for red detection.

White areas are detected as red.

Use this window to tune HSV sliders.

### 3. Controls Window

Contains sliders for:

* HSV red threshold
* Minimum detected area
* Morphological cleanup kernel
* Brightness
* Contrast

### 4. Instructions Window

Shows all keys and the current calibration status.

This keeps the main camera feed clean.

---

## 10. Keyboard Controls

Click the OpenCV window first before pressing keys.

### General Controls

| Key | Action                   |
| --- | ------------------------ |
| `Q` | Quit program             |
| `H` | Home Dobot               |
| `M` | Manual coordinate input  |
| `P` | Print current jog target |

### Manual Jog Controls

| Key | Action            |
| --- | ----------------- |
| `I` | Move X positive   |
| `K` | Move X negative   |
| `J` | Move Y negative   |
| `L` | Move Y positive   |
| `E` | Move Z up         |
| `Z` | Move Z down       |
| `+` | Increase jog step |
| `-` | Decrease jog step |

### Calibration Controls

| Key | Action                                                         |
| --- | -------------------------------------------------------------- |
| `T` | Lock current visible red cube pixel                            |
| `A` | Add calibration point using locked pixel and current Dobot X/Y |
| `C` | Compute homography                                             |
| `S` | Save calibration and homography                                |
| `O` | Load saved calibration                                         |
| `U` | Undo last calibration point                                    |
| `R` | Reset calibration and locked target                            |

### Movement Controls After Calibration

| Key | Action                                   |
| --- | ---------------------------------------- |
| `T` | Lock visible cube                        |
| `B` | Move Dobot to locked cube                |
| `G` | Move Dobot to current live detected cube |

For normal use after calibration, prefer:

```text
T -> B
```

instead of `G`, because the robot head may hide the cube during movement.

---

## 11. First-Time Calibration Workflow

Homography is required before the camera can convert pixels into Dobot coordinates.

A camera can detect:

```text
u = 320, v = 240
```

But the Dobot needs:

```text
X = 250, Y = 0
```

Calibration teaches the system this relationship.

### Step-by-step calibration

Use this sequence:

```text
T -> Jog -> A
```

Repeat at least four times.

Detailed process:

1. Place the red cube at the first calibration position.
2. Keep the Dobot away from the cube so the camera can see it clearly.
3. Press `T`.

This locks the cube pixel position.

4. Manually jog the Dobot tip to the cube using:

```text
I / K = X movement
J / L = Y movement
E / Z = Z movement
```

5. When the Dobot tip is exactly above the cube, press `A`.

This saves:

```text
locked camera pixel -> current Dobot X/Y
```

6. Move the cube to another visible position.
7. Repeat `T -> Jog -> A`.

Use at least four different positions.

Recommended positions:

```text
top-left
top-right
bottom-left
bottom-right
center
```

After four or more points:

8. Press `C` to compute homography.
9. Press `S` to save calibration.

This creates:

```text
calibration_points.json
homography.npy
```

---

## 12. Normal Use After Calibration

Once homography is ready:

1. Place the red cube anywhere in the calibrated camera area.
2. Press `T` to lock the cube.
3. Press `B` to move Dobot to the locked cube position.

Recommended movement sequence:

```text
T -> B
```

The reason for locking first is that when the Dobot head moves toward the cube, it may hide the cube from the top camera. Once the target is locked, the system no longer needs to see the cube while moving.

---

## 13. Safety Limits

The robot should not be allowed to move outside a safe workspace.

Recommended starting limits:

```python
X_MIN = 180.0
X_MAX = 310.0

Y_MIN = -120.0
Y_MAX = 120.0

Z_MIN = 40.0
Z_MAX = 120.0
```

Use a high safe Z value while testing:

```python
SAFE_Z = 80.0
PICK_Z = 45.0
```

Start with a high `PICK_Z`, verify alignment, then slowly reduce it.

Never test low Z movement until the XY mapping is verified.

---

## 14. Red Detection Tuning

Use the Controls window.

Default red HSV values:

```text
H1 Low  = 0
H1 High = 12

H2 Low  = 168
H2 High = 179

S Low   = 70
V Low   = 50
```

If the red cube is not detected:

* Increase brightness.
* Reduce `V Low`.
* Reduce `S Low`.
* Check the Red Mask window.
* Make sure the cube appears white in the Red Mask window.

If red appears blue or blue appears red, the camera color channel order may need correction. In the script this is handled by:

```python
frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
```

---

## 15. Common Errors and Fixes

### Error: `No module named 'MvCameraControl_class'`

The SDK Python files are missing.

Fix:

```text
Copy MvCameraControl_class.py and related MvImport files into MappingCode/SDK/
```

### Error: camera opens in MVS Viewer but not in Python

Close MVS Viewer. The camera may be locked by another application.

### Error: Dobot COM port blocked

Close DobotStudio or DobotLab.

### Error: homography not computed

You need at least four calibration pairs.

Do:

```text
T -> Jog -> A
```

at four different cube positions, then press `C`.

### Problem: Dobot head reaches cube and detection disappears

This is normal. Use locked movement:

```text
T -> B
```

Do not rely on live detection while the robot is covering the cube.

### Problem: robot crossed boundary

Stop the script immediately with `Q` or power off the Dobot.

Then reduce workspace limits and use smaller jog steps.

Recommended jog step:

```python
JOG_STEP_DEFAULT = 2.0
```

---

## 16. Output Files

### `calibration_points.json`

Stores image-to-robot calibration pairs.

Example:

```json
{
    "image_points": [
        [310.0, 220.0],
        [500.0, 230.0],
        [320.0, 420.0],
        [510.0, 430.0]
    ],
    "robot_points": [
        [210.0, -80.0],
        [290.0, -80.0],
        [210.0, 80.0],
        [290.0, 80.0]
    ],
    "homography": [...]
}
```

### `homography.npy`

Stores the computed homography matrix.

This file is used to convert camera pixel coordinates into Dobot X/Y coordinates.

---

## 17. Recommended Calibration Quality

Use more than four points for better accuracy.

Minimum:

```text
4 points
```

Recommended:

```text
6 to 9 points
```

Spread them across the camera-visible robot workspace.

Avoid using points that are too close together.

Good layout:

```text
top-left      top-center      top-right
middle-left   center          middle-right
bottom-left   bottom-center   bottom-right
```

---

## 18. Important Notes

* Always keep the Dobot at a safe Z height during testing.
* Do not allow the robot to move outside safe workspace limits.
* Do not press `B` or `G` until homography is computed.
* Use `T -> B` for reliable movement after calibration.
* Use `T -> Jog -> A` for first-time calibration.
* Close MVS Viewer before running the script.
* Close DobotStudio/DobotLab before running the script.

---

## 19. Quick Start Summary

First-time setup:

```text
1. Copy MVS Python SDK files into SDK/
2. Connect camera and Dobot
3. Close MVS Viewer and DobotStudio
4. Run: python dobot_mvs_mapper_final.py
5. Press T to lock cube pixel
6. Jog Dobot tip to cube
7. Press A to save calibration pair
8. Repeat 4 or more times
9. Press C to compute homography
10. Press S to save
```

Normal use:

```text
1. Place cube
2. Press T
3. Press B
```
