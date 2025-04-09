# TODO: add Tkinter lib and FX10 lib
# TODO: add basic functionality to interact with the camera

from tkinter import *
from lib.spectralcam.gentl.gentl import *
from lib.spectralcam.specim.fx10 import *

def create_window():
    window = Tk()
    window.geometry("600x300")

    connectButton = Button(window, text="Connect FX10", command=connect_camera)
    connectButton.pack()

    window.title("FX10 Configuration App")

    window.mainloop()

def connect_camera():
    system = GCSystem()
    fx10, intf = system.discover(FX10)

if __name__ == "__main__":
    create_window()
