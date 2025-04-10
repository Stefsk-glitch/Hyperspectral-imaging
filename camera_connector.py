from lib.spectralcam.gentl.gentl import *
from lib.spectralcam.specim.fx10 import *

class CameraConnector:
    def __init__(self, app=None):
        self.cam = None
        self.intf = None
        self.app = app

    def connect(self):
        system = GCSystem()
        self.cam, self.intf = system.discover(FX10)

        if not self.cam:
            self.app.message_box("No cam detected")
        elif not self.intf:
            self.app.message_box("No interface detected")
        elif len(system.discover(FX10)[0]) > 1:
            self.app.message_box("Multiple cams detected, only connect 1 cam")
        else:
            self.app.set_connection_status(True)
            self.app.message_box("Cam found")

    def quick_init_camera(self):
        if self.cam:
            self.cam.quick_init()
    
    def get_settings(self):
        # todo: get settings here, fxbase contains lots of functions for this
        print()
    
    def get_info(self):
        if self.cam:
            self.cam.get_info()
