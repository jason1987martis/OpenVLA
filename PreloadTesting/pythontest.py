from serial.tools import list_ports
from pydobot import Dobot
#pip install pydobot pyserial
# Find Dobot port
available_ports = list_ports.comports()
print([p.device for p in available_ports])

port = available_ports[0].device

# Connect
device = Dobot(port=port, verbose=True)

# Current position
x, y, z, r, j1, j2, j3, j4 = device.pose()

print(f"Current Position: X={x} Y={y} Z={z}")

# Set speed
device.speed(100, 100)

# Move to a position
device.move_to(
    x=250,
    y=0,
    z=50,
    r=0,
    wait=True
)

print("Move complete")

device.close()