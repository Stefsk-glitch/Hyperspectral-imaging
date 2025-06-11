from enum import Enum

class Events(Enum):
    CAM_FOUND = 1,
    MULTIPLE_CAMS = 2,
    NO_CAM = 3,
    CAM_DISCONNECTED = 4

class ConnectionState(Enum):
    DISCONNECTED = 1,
    CONNECTING = 2,
    CONNECTED = 3