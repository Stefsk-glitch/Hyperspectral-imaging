from lib.spectralcam.gentl.gentl import *
from lib.spectralcam.specim.fx10 import *

class CameraConnector:
    def __init__(self):
        self.cam = None
        self.intf = None

    def connect(self):
        system = GCSystem()
        self.cam, self.intf = system.discover(FX10)

    def quick_init_camera(self):
        if self.cam:
            self.cam.quick_init()
