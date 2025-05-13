from lib.spectralcam.gentl.gentl import GCSystem
from lib.spectralcam.specim.fx10 import FX10
from lib.spectralcam.exceptions import *
import numpy as np
import threading
from enum import Enum
from context import app_context
from enums import ConnectionState

def connect():
    if app_context["camera_data"].get("system") is None:
        app_context["camera_data"]["system"] = GCSystem()

    thread = threading.Thread(target=find_and_connect_camera)
    thread.start()

def find_and_connect_camera():
    system = app_context["camera_data"]["system"]
    system.discover(FX10)
    app_context["set_connection_state"](ConnectionState.CONNECTING)

def quick_init_camera():
    cam = app_context["camera_data"].get("cam")
    if not cam:
        return app_context["message_box"]("No cam to quick init")

    cam.set_defaults(frame_rate=30.0, exposure_time=30000.0)
    cam.set("BinningHorizontal", 2)
    cam.open_stream()
    cam.show_preview()
    cam.start_acquire(True)

def extract_data():
    cam = app_context["camera_data"].get("cam")
    if not cam:
        app_context["message_box"]("No cam to extract data from")
        return
    data = cam.stop_acquire()
    thread = threading.Thread(target = save_data, args = (data, ))
    thread.start()

def save_data(data):
    np.save("data.npy", data)
    app_context["message_box"]("Finished saving data")

def get_categories():
    cam = app_context["camera_data"].get("cam")
    if not cam:
        app_context["message_box"]("No cam to get categories")
        return
    cam.get_features()

def get_info():
    cam = app_context["camera_data"].get("cam")
    if cam:
        cam.get_info()

def close():
    canClose = False
    try:
        cam = app_context["camera_data"].get("cam")
        if cam:
            cam.close()
        canClose = True
    except NotConnectedError:
        # todo: debug, remove in final version
        app_context["message_box"]("Cam was not connected")
        canClose = True
    except AckError:
        app_context["message_box"]("Problem with an acknowledgement from the camera")
    finally:
        if (canClose == True):
            app_context["close_app"]()
