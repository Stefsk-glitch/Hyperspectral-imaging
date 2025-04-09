from tkinter import *
from lib.spectralcam.gentl.gentl import *
from lib.spectralcam.specim.fx10 import *

cam = None

def create_window():
    window = Tk()
    window.geometry("600x400")

    connectButton = Button(window, text="Connect FX10", command=connect_camera)
    connectButton.pack()

    quickInitButton = Button(window, text="Quick Init", command=quick_init_camera)
    quickInitButton.pack()

    window.title("FX10 Configuration App")

    window.mainloop()

def connect_camera():
    global cam
    system = GCSystem()
    cam, intf = system.discover(FX10)

def quick_init_camera():
    global cam
    if cam:
        cam.quick_init()

if __name__ == "__main__":
    create_window()
