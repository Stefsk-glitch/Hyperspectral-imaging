from tkinter import *
from tkinter import messagebox
from camera_connector import CameraConnector

class ConfigurationApp():
    def __init__(self):
        self.camera_connector = CameraConnector(self)

        self.window = Tk()
        self.window.geometry("600x400")
        self.window.columnconfigure(0, minsize=300)
        self.window.columnconfigure(1, minsize=300)
        self.window.title("FX10 Configuration App")

        self.connectionLabel = Label(self.window)
        self.connectionLabel.grid(row=1, column=0, sticky=W)
        self.set_connection_status(False)
        settingsLabel = Label(self.window, text="Settings", font=("", 20))
        settingsLabel.grid(row=5, column=0, sticky=W)

        connectButton = Button(self.window, text="Connect FX10", command=self.camera_connector.connect)
        connectButton.grid(row=0, column=0, sticky=W)
        quickInitButton = Button(self.window, text="Quick Init", command=self.camera_connector.quick_init_camera)
        quickInitButton.grid(row=2, column=0, sticky=W)

        self.window.mainloop()

    def message_box(self, text):
        messagebox.showinfo("Message", text)

    def set_connection_status(self, connected):
        if connected == True:
            self.connectionLabel.config(text="Connection status: Connected")
        else:
            self.connectionLabel.config(text="Connection status: Disconnected")
