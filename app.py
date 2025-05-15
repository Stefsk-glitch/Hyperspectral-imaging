from tkinter import Tk, Label, Button, W, messagebox, NORMAL, DISABLED
import tkinter as tk
from settings import open_settings_window
from models import app_context
import camera_connector, event_handler
from enums import ConnectionState
from lib.spectralcam.gentl import GCDevice, GCInterface
from typing import Tuple

def run_app():
    window = Tk()
    window.geometry("800x600")
    window.title("FX10 Configuration App")

    main_frame = tk.Frame(window)
    main_frame.pack(padx=10, pady=10, anchor="w")

    app_name_row = tk.Frame(main_frame)
    app_name_row.pack(fill="x", pady=2)

    connection_row = tk.Frame(main_frame)
    connection_row.pack(fill="x", pady=2)

    connection_info_row = tk.Frame(main_frame)
    connection_info_row.pack(fill="x", pady=2)

    cam_actions_row = tk.Frame(main_frame)
    cam_actions_row.pack(fill="x", pady=2)

    settings_row = tk.Frame(main_frame)
    settings_row.pack(fill="x", pady=2)

    connection_label = Label(connection_info_row, text="Connection status: Disconnected")
    connection_label.grid(row=0, column=0)

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
                cam: GCDevice = app_context["camera_data"]["cam"]
                ip = cam._info.host_address
                status = f"Connected to {ip}"
        connection_label.config(text=f"Connection status: {status}")

    app_context["message_box"] = message_box
    app_context["set_connection_state"] = set_connection_state

    Label(app_name_row, text="FX10 Configuration app", font=("", 22)).pack()
    connect_button = Button(connection_row, text="Connect FX10", command=camera_connector.connect)
    connect_button.grid(row=0, column=0, padx="5")

    cam_information_button = Button(connection_row, text="Camera Info", command=lambda:camera_connector.show_info(window))
    cam_information_button.grid(row=0, column=1)

    quick_init_button = Button(cam_actions_row, text="Quick Init", command=camera_connector.quick_init_camera)
    quick_init_button.grid(row=0, column=0, padx="5")

    extract_data_button = Button(cam_actions_row, text="Extract Data", command=camera_connector.extract_data)
    extract_data_button.grid(row=0, column=1)

    Label(settings_row, text="Settings", font=("", 20)).grid(row=7, column=0, sticky=W)

    settings_button = Button(settings_row, text="Open settings", command=lambda: open_settings_window(window))
    settings_button.grid(row=9, column=0, sticky=W)

    toggleable_buttons = [quick_init_button, extract_data_button, settings_button, cam_information_button]

    def cam_event(event: event_handler.Events, args: Tuple[GCDevice, GCInterface]):
        match event:
            case event_handler.Events.CAM_FOUND:
                cam, intf = args
                app_context["camera_data"]["cam"] = cam
                app_context["camera_data"]["intf"] = intf
                set_connection_state(ConnectionState.CONNECTED)
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
        for button in toggleable_buttons:
            button.config(state=state)

    event_handler.add_listener(cam_event)    
    set_buttons(DISABLED)

    def on_close():
        if (app_context["camera_data"]["system"]):
            system = app_context["camera_data"]["system"]
            system.close()
        exit()

    window.protocol("WM_DELETE_WINDOW", on_close)
    window.mainloop()
