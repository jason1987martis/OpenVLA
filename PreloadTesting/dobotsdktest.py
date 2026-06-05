import DobotDllType as dType

api = dType.load()

state = dType.ConnectDobot(
    api,
    "",
    115200
)

# Move to X=250 Y=0 Z=50 R=0
dType.SetPTPCmd(
    api,
    dType.PTPMode.PTPMOVJXYZMode,
    250,
    0,
    50,
    0,
    isQueued=1
)

dType.DisconnectDobot(api)