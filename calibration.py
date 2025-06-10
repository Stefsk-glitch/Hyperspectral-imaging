from tkinter import Toplevel, Button
from lib.spectralcam.specim.fx10 import FX10
from models import app_context
import time
import numpy as np
import os

def calculate_reference_average(input_file, output_file=None, num_pixels=500):
        """
        Berekent het gemiddelde van pixels uit het midden van een hyperspectraal beeld.
        
        Parameters:
        input_file (str): Pad naar het .npy bestand (vorm: x, y, 512)
        output_file (str): Pad voor output bestand (optioneel)
        num_pixels (int): Aantal pixels om te middelen (default: 500)
        """
        
        # Laad het hyperspectrale beeld
        try:
            data = np.load(input_file)
            print(f"Bestand geladen: {data.shape}")
        except Exception as e:
            print(f"Fout bij laden bestand: {e}")
            return None
        
        # Controleer dimensies
        if len(data.shape) != 3:
            print(f"Fout: Verwacht 3D array (x, y, spectral), maar kreeg {len(data.shape)}D")
            return None
        
        if data.shape[2] != 512:
            print(f"Waarschuwing: Verwacht 512 spectrale banden, maar kreeg {data.shape[2]}")
        
        height, width, spectral_bands = data.shape
        
        # Bereken centrum
        center_y = height // 2
        center_x = width // 2
        
        # Bereken hoeveel pixels we in elke richting kunnen pakken
        max_radius = min(center_x, center_y, width - center_x, height - center_y)
        pixels_per_side = int(np.sqrt(num_pixels))
        
        # Pas aan als we niet genoeg pixels hebben
        if pixels_per_side > max_radius * 2:
            pixels_per_side = max_radius * 2
            actual_num_pixels = pixels_per_side ** 2
            print(f"Waarschuwing: Aantal pixels aangepast naar {actual_num_pixels} (beperkt door beeldgrootte)")
        else:
            actual_num_pixels = num_pixels
        
        # Selecteer pixels uit het centrum
        half_size = pixels_per_side // 2
        start_y = center_y - half_size
        end_y = center_y + half_size
        start_x = center_x - half_size  
        end_x = center_x + half_size
        
        # Extraheer de centrale pixels
        central_pixels = data[start_y:end_y, start_x:end_x, :]
        
        print(f"Geselecteerd gebied: [{start_y}:{end_y}, {start_x}:{end_x}]")
        print(f"Aantal pixels gebruikt: {central_pixels.shape[0] * central_pixels.shape[1]}")
        
        # Bereken gemiddelde over alle geselecteerde pixels
        # Reshape naar (num_pixels, spectral_bands) en bereken gemiddelde
        reshaped_pixels = central_pixels.reshape(-1, spectral_bands)
        average_spectrum = np.mean(reshaped_pixels, axis=0)
        
        print(f"Gemiddelde spectrum berekend: {average_spectrum.shape}")
        print(f"Spectrale waarden bereik: {np.min(average_spectrum):.2f} - {np.max(average_spectrum):.2f}")
        
        # Bepaal output bestandsnaam
        if output_file is None:
            base_name = os.path.splitext(input_file)[0]
            output_file = f"{base_name}_gemiddelde.npy"
        
        # Sla het gemiddelde spectrum op
        try:
            np.save(output_file, average_spectrum)
            print(f"Gemiddelde spectrum opgeslagen als: {output_file}")
        except Exception as e:
            print(f"Fout bij opslaan: {e}")
            return None
        
        return average_spectrum

def calibrate_black():
        cam: FX10 = app_context["camera_data"]["cam"]
        cam.set_defaults()
        cam.open_stream()
        cam.start_acquire(True)
        time.sleep(1)
        data = cam.stop_acquire()
        np.save("calibration/black.npy", data)
        calculate_reference_average("calibration/black.npy")
        app_context["message_box"]("Calibrated black reference")
    
def calibrate_white():
    cam: FX10 = app_context["camera_data"]["cam"]
    cam.set_defaults()
    cam.open_stream()
    cam.start_acquire(True)
    time.sleep(1)
    data = cam.stop_acquire()
    np.save("calibration/white.npy", data)
    calculate_reference_average("calibration/white.npy")
    app_context["message_box"]("Calibrated white reference")

def open_calibration_window(master):
    win = Toplevel(master)
    win.title("Calibrate Camera")

    Button(win, text="Start black calibration", command=lambda:calibrate_black()).pack(padx="5")
    Button(win, text="Start white calibration", command=lambda:calibrate_white()).pack(pady="5")
        
    