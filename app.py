from tkinter import Tk, Label, Button, W, messagebox, Frame, SE, NORMAL, DISABLED
from settings import open_settings_window
from lib.spectralcam.gentl.gentl import GCSystem, GCDevice
from context import app_context
import camera_connector, event_handler
from enums import ConnectionState

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

    def set_connection_state(connected: ConnectionState):
        status = ""
        match connected:
            case ConnectionState.DISCONNECTED:
                status = "Disconnected"
            case ConnectionState.CONNECTING:
                status = "Connecting..."
            case ConnectionState.CONNECTED:
                status = "Connected"
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
        "set_connection_state": set_connection_state,
        "close_app": close_app
    })

    Label(frame, text="FX10 Configuration app", font=("", 22)).grid(row=0, column=0, sticky=W)
    connect_button = Button(frame, text="Connect FX10", command=camera_connector.connect)
    connect_button.grid(row=1, column=0, sticky=W)

    quick_init_button = Button(frame, text="Quick Init", command=camera_connector.quick_init_camera)
    quick_init_button.grid(row=3, column=0, sticky=W)

    extract_data_button = Button(frame, text="Extract Data", command=camera_connector.extract_data)
    extract_data_button.grid(row=4, column=0, sticky=W)

    Button(window, text="Close App", command=camera_connector.close).grid(row=1, column=1, sticky=SE, padx=10, pady=10)
    Label(frame, text="Settings", font=("", 20)).grid(row=7, column=0, sticky=W)

    settings_button = Button(frame, text="Open settings", command=lambda: open_settings_window(window))
    settings_button.grid(row=9, column=0, sticky=W)

    buttons = [quick_init_button, extract_data_button, settings_button]

    def cam_event(event: event_handler.Events, args):
        match event:
            case event_handler.Events.CAM_FOUND:
                cam, intf = args
                set_connection_state(ConnectionState.CONNECTED)
                app_context["camera_data"]["cam"] = cam
                app_context["camera_data"]["intf"] = intf
                set_buttons(NORMAL)
            case event_handler.Events.MULTIPLE_CAMS:
                app_context["message_box"]("Found multiple cams. This app does not support multiple cams yet")
                set_connection_state(ConnectionState.DISCONNECTED)
            case event_handler.Events.NO_CAM:
                app_context["message_box"]("No cams found")
                set_connection_state(ConnectionState.DISCONNECTED)

    def set_buttons(state):
        if state is NORMAL:
            connect_button.config(state=DISABLED)
        for button in buttons:
            button.config(state=state)

    event_handler.add_listener(cam_event)    

    set_buttons(DISABLED)
    window.mainloop()
