from tkinter import Tk, Label, Button, W, messagebox
import camera_connector

def run_app():
    window = Tk()
    window.geometry("600x400")
    window.columnconfigure(0, minsize=300)
    window.columnconfigure(1, minsize=300)
    window.title("FX10 Configuration App")

    connection_label = Label(window)
    connection_label.grid(row=1, column=0, sticky=W)
    connection_label.config(text="Connection status: Disconnected")

    camera_data = {
        "system": None
    }

    def message_box(text):
        messagebox.showinfo("Message", text)

    def set_connection_status(connected):
        status = "Connected" if connected else "Disconnected"
        connection_label.config(text=f"Connection status: {status}")

    app_context = {
        "camera_data": camera_data,
        "message_box": message_box,
        "set_connection_status": set_connection_status
    }

    Label(window, text="Settings", font=("", 20)).grid(row=5, column=0, sticky=W)
    Button(window, text="Connect FX10", command=lambda: camera_connector.connect(app_context)).grid(row=0, column=0, sticky=W)
    Button(window, text="Quick Init", command=lambda: camera_connector.quick_init_camera(app_context)).grid(row=2, column=0, sticky=W)

    window.mainloop()
