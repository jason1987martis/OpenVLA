import time
from pydobotplus import Dobot

device = Dobot(port="COM8")
time.sleep(1)

device.clear_alarms()

print("Suction ON")
device.suck(True)
time.sleep(3)

print("Suction OFF")
device.suck(False)

device.close()