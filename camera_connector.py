from lib.spectralcam.gentl.gentl import GCSystem
from lib.spectralcam.specim.fx10 import FX10
from lib.spectralcam.specim import FXBase
from lib.spectralcam.exceptions import *
import numpy as np
import threading
from models import app_context
from enums import ConnectionState
from lib.spectralcam.gentl import GCDevice
from tkinter import Toplevel, Label, W

def connect():
    if app_context["camera_data"]["system"] is None:
        app_context["camera_data"]["system"] = GCSystem()

    thread = threading.Thread(target=find_and_connect_camera)
    thread.start()

def find_and_connect_camera():
    app_context["set_connection_state"](ConnectionState.CONNECTING)
    system: GCSystem = app_context["camera_data"]["system"]
    system.discover(FX10)

def quick_init_camera():
    cam: FX10 = app_context["camera_data"]["cam"]
    if not cam:
        return app_context["message_box"]("No cam to quick init")

    cam.set_defaults(frame_rate=30.0, exposure_time=30000.0)
    cam.set("BinningHorizontal", 2)
    cam.open_stream()
    cam.show_preview()
    cam.start_acquire(True)

def extract_data():
    cam: FXBase = app_context["camera_data"]["cam"]
    if not cam:
        app_context["message_box"]("No cam to extract data from")
        return
    data = cam.stop_acquire()
    thread = threading.Thread(target = save_data, args = (data, ))
    thread.start()

def save_data(data):
    np.save("data.npy", data)
    app_context["message_box"]("Finished saving data")

def show_info(master):
    win = Toplevel(master)
    win.title("Camera Information")

    dev: GCDevice = app_context["camera_data"]["cam"]
    info_label = Label(win, text=dev._info.get_app_info())
    info_label.grid(row=3, column=1, sticky=W)
