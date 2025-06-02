from tkinter import Toplevel, Button
from lib.spectralcam.specim.fx10 import FX10
from models import app_context
import time
import numpy as np

def open_calibration_window(master):
    win = Toplevel(master)
    win.title("Calibrate Camera")

    cam: FX10 = app_context["camera_data"]["cam"]
    Button(win, text="Start black calibration", command=lambda:calibrate_black()).pack(padx="5")
    Button(win, text="Start white calibration", command=lambda:calibrate_white()).pack(pady="5")

    def calibrate_black():
        cam.set_defaults()
        cam.open_stream()
        cam.start_acquire(True)
        time.sleep(1000)
        data = cam.stop_acquire()
        np.save("calibration/black.npy", data)
        app_context["message_box"]("Calibrated black reference")
    
    def calibrate_white():
        cam.set_defaults()
        cam.open_stream()
        cam.start_acquire(True)
        time.sleep(1000)
        data = cam.stop_acquire()
        np.save("calibration/white.npy", data)
        app_context["message_box"]("Calibrated white reference")
        