from enums import Events

listeners = []

def add_listener(listener):
    listeners.append(listener)

def remove_listener(listener):
    listeners.remove(listener)

def fire_event(event, *args):
    for listener in listeners:
        listener(event, *args)

