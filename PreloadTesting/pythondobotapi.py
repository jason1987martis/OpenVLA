from serial.tools import list_ports
from dobotplus import Dobot
#pip install pydobotplus
port = list_ports.comports()[0].device

robot = Dobot(port=port)

robot.move_to(
    x=250,
    y=0,
    z=50,
    r=0
)

robot.close()