from lib.spectralcam.gentl.gentl import GCSystem
from lib.spectralcam.specim.fx10 import FX10
import numpy as np
import threading

def connect(app):
    if app["camera_data"].get("system") is None:
        app["camera_data"]["system"] = GCSystem()

    system = app["camera_data"]["system"]
    cam, intf = system.discover(FX10)

    if not cam:
        app["message_box"]("No cam detected")
    elif not intf:
        app["message_box"]("No interface detected")
    else:
        app["set_connection_status"](True)
        app["message_box"]("Cam found")
        app["camera_data"]["cam"] = cam
        app["camera_data"]["intf"] = intf

def quick_init_camera(app):
    cam = app["camera_data"].get("cam")
    if not cam:
        app["message_box"]("No cam to quick init")
        return

    cam.set_defaults(frame_rate=30.0, exposure_time=30000.0)
    cam.set("BinningHorizontal", 2)
    cam.open_stream()
    cam.show_preview()
    cam.start_acquire(True)

def stop_data(app):
    cam = app["camera_data"].get("cam")
    if not cam:
        app["message_box"]("No cam to quick init")
        return
    data = cam.stop_acquire()
    thread = threading.Thread(target = save_data, args = (data, app, ))
    thread.start()

def save_data(data, app):
    np.save("data.npy", data)
    app["message_box"]("Finished saving data")

def get_settings(app):
    cam = app["camera_data"].get("cam")
    if not cam:
        app["message_box"]("No cam to get categories")
        return
    cam.get_features()

def get_info(app):
    cam = app["camera_data"].get("cam")
    if cam:
        cam.get_info()

def close(app):
    cam = app["camera_data"].get("cam")
    if cam:
        cam.close_stream()