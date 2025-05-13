from enum import Enum

listeners = []

def add_listener(listener):
    listeners.append(listener)

def remove_listener(listener):
    listeners.remove(listener)

def fire_event(event, *args):
    for listener in listeners:
        listener(event, *args)

class Events(Enum):
    CAM_FOUND = 1,
    MULTIPLE_CAMS = 2,
    NO_CAM = 3
