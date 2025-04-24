from lib.spectralcam.gentl.gentl import GCSystem
from lib.spectralcam.specim.fx10 import FX10
from lib.spectralcam.exceptions import *
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

def extract_data(app):
    cam = app["camera_data"].get("cam")
    if not cam:
        app["message_box"]("No cam to extract data from")
        return
    data = cam.stop_acquire()
    thread = threading.Thread(target = save_data, args = (data, app, ))
    thread.start()

def save_data(data, app):
    np.set_printoptions(threshold=np.inf)
    with open("data.txt", "w") as f:
        f.write(np.array2string(data))

    app["message_box"]("Finished saving data")

def get_categories(app):
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
    canClose = False
    try:
        cam = app["camera_data"].get("cam")
        if cam:
            cam.close()
        canClose = True
    except NotConnectedError:
        # todo: debug, remove in final version
        app["message_box"]("Cam was not connected")
        canClose = True
    except AckError:
        app["message_box"]("Problem with an acknowledgement from the camera")
    finally:
        if (canClose == True):
            app["close_app"]()
