# Create calibration points
Move the Dobot tip to known locations.

Example:
```
Point	Robot X	Robot Y
P1	200	-100
P2	300	-100
P3	300	100
P4	200	100
```

# Get and Map Image coordinates

Move Dobot tip to P1: ```device.move_to(200,-100,20,0,wait=True```

Capture image: Put a bright red sticker / red tape on the Dobot tip, then use OpenCV to find the red blob center.

Find the tip position by running: ```python findredtatpe.py```

You'll get : ```Dobot tip pixel position: 315 220``` (Camera Coordinates)

That means:
```
Robot coordinate: X=200, Y=-100
Camera coordinate: u=315, v=220
```
You save this pair for calibration:
```
robot_points.append([200, -100])
image_points.append([315, 220])
```
Do this for 4 or more positions. Then you can calculate the homography. Save these points in ```map.py```

Note: Minimum requirement: 4 point pairs. Better: use 6–9 point pairs for more accurate calibration.

Now call : ```python map.py```

## You now have the Homography

Now to convert call: ```python translatecoordinate.py```