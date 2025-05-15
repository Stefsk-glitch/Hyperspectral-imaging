from tkinter import Toplevel
from models import app_context

def on_open(app_context):
    camera = app_context["camera_data"]["cam"]
    features = camera.get_features()
    for feature in features:
        try:
            with open("output.txt", "a") as f:
                f.write(str(feature.node.name) + ": " + str(camera.get(feature)) + "\n")
        except Exception as error:
            with open("output.txt", "a") as f:
                f.write(str(error) + "\n")
    

def open_settings_window(master):
    win = Toplevel(master)
    win.title("Settings")
    if app_context['camera_data']['cam'] is None:
        app_context['message_box']("Cam is not connected")
        return win.destroy()
    on_open(app_context)
    