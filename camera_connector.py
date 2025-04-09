from lib.spectralcam.gentl.gentl import *
from lib.spectralcam.specim.fx10 import *

cam = None

class CameraConnector():
    def connect(self):
        global cam
        system = GCSystem()
        cam, intf = system.discover(FX10)
    
    def quick_init_camera():
        global cam
        if cam:
            cam.quick_init()