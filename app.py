from tkinter import Tk, Label, Button, W, messagebox, Frame, SE, Toplevel
from settings import open_settings_window
from lib.spectralcam.gentl.gentl import GCSystem, GCDevice
from context import app_context
import camera_connector

def run_app():
    window = Tk()
    window.geometry("600x400")
    window.title("FX10 Configuration App")

    window.rowconfigure(1, weight=1)
    window.columnconfigure(1, weight=1)

    frame = Frame(window, padx=10, pady=10)
    frame.grid(row=0, column=0, sticky="nsew")

    right_pad = Frame(window, width=50)
    right_pad.grid(row=0, column=1, rowspan=2, sticky="nse")

    connection_label = Label(frame, text="Connection status: Disconnected")
    connection_label.grid(row=2, column=0, sticky=W)

    camera_data = {
        "system": None,
        "cam": None
    }

    def message_box(text):
        messagebox.showinfo("Message", text)

    def set_connection_status(connected):
        status = "Connected" if connected else "Disconnected"
        connection_label.config(text=f"Connection status: {status}")

    def close_app():
        print("destroy")
        window.destroy()
        if (camera_data["system"]):
            system = camera_data["system"]
            system.close()
        exit()

    app_context.update({
        "camera_data": camera_data,
        "message_box": message_box,
        "set_connection_status": set_connection_status,
        "close_app": close_app
    })

    Label(frame, text="FX10 Configuration app", font=("", 22)).grid(row=0, column=0, sticky=W)
    Button(frame, text="Connect FX10", command=camera_connector.connect).grid(row=1, column=0, sticky=W)
    Button(frame, text="Quick Init", command=camera_connector.quick_init_camera).grid(row=3, column=0, sticky=W)
    Button(frame, text="Extract Data", command=camera_connector.extract_data).grid(row=4, column=0, sticky=W)
    Button(window, text="Close App", command=camera_connector.close).grid(row=1, column=1, sticky=SE, padx=10, pady=10)
    Label(frame, text="Settings", font=("", 20)).grid(row=7, column=0, sticky=W)
    Button(frame, text="Get settings", command=camera_connector.get_categories).grid(row=8, column=0, sticky=W)
    Button(frame, text="Open settings", command=lambda: open_settings_window(window)).grid(row=9, column=0, sticky=W)

    window.mainloop()
