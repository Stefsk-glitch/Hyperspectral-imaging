import queue

camera_data = {
    "system": None,                 # GCSystem
    "cam": None                     # FXBase
}

app_context = {
    "camera_data": camera_data,
    "message_box": None,            # function to show a message box
    "set_connection_state": None    # function to set app connection state
}

command_queue = queue.Queue()
esp32_status = {"connected": False}
stopped = {"stop": False}
pipeline = {"visualize": False}
cam_was_scanning = {"cam_was_scanning": False}