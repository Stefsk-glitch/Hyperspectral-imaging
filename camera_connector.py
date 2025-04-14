from lib.spectralcam.gentl.gentl import GCSystem
from lib.spectralcam.specim.fx10 import FX10

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
    print(type(cam))
    if not cam:
        app["message_box"]("No cam to quick init")
        return

    cam.set_defaults(frame_rate=15.0, exposure_time=30000.0)
    cam.set("BinningHorizontal", 2)
    cam.open_stream()
    cam.show_preview()
    cam.start_acquire(True)
    
def get_info(app):
    cam = app["camera_data"].get("cam")
    if cam:
        cam.get_info()
