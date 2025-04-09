from tkinter import *
from camera_connector import CameraConnector

class ConfigurationApp():
    def start(self):
        window = Tk()
        window.geometry("600x400")
        self.camera_connector = CameraConnector()

        connectButton = Button(window, text="Connect FX10", command=self.camera_connector.connect)
        connectButton.pack()

        quickInitButton = Button(window, text="Quick Init", command=self.camera_connector.quick_init_camera)
        quickInitButton.pack()

        window.title("FX10 Configuration App")

        window.mainloop()