import numpy as np
import sys
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

def calibrate_hyperspectral_scan(scan_file, white_ref_file, black_ref_file, output_file=None):
    """
    Calibreert een hyperspectrale scan met white en black referenties.
    
    Parameters:
    scan_file (str): Pad naar het te calibreren .npy bestand (vorm: x, y, spectral_bands)
    white_ref_file (str): Pad naar white reference .npy bestand (vorm: spectral_bands,)
    black_ref_file (str): Pad naar black reference .npy bestand (vorm: spectral_bands,)
    output_file (str): Pad voor gecalibreerd bestand (optioneel)
    """
    
    try:
        # Laad de scan data
        scan_data = np.load(scan_file)
        print(f"Scan geladen: {scan_data.shape}")
        
        # Laad referenties
        white_ref = np.load(white_ref_file)
        black_ref = np.load(black_ref_file)
        print(f"White reference: {white_ref.shape}")
        print(f"Black reference: {black_ref.shape}")
        
    except Exception as e:
        print(f"Fout bij laden bestanden: {e}")
        return None
    
    # Controleer dimensies
    if len(scan_data.shape) != 3:
        print(f"Fout: Scan moet 3D zijn (x, y, spectral), maar is {len(scan_data.shape)}D")
        return None
    
    height, width, spectral_bands = scan_data.shape
    
    # Controleer of referenties juiste grootte hebben
    if white_ref.shape[0] != spectral_bands or black_ref.shape[0] != spectral_bands:
        print(f"Fout: Referenties hebben {white_ref.shape[0]} banden, scan heeft {spectral_bands}")
        return None
    
    print(f"Calibratie wordt toegepast op {height}x{width} pixels met {spectral_bands} spectrale banden...")
    
    # Bereken de calibratie: (scan - black) / (white - black)
    denominator = white_ref - black_ref
    
    # Controleer voor zeer kleine verschillen tussen white en black
    min_diff = np.min(denominator)
    if min_diff < 1e-6:
        print("Waarschuwing: Zeer kleine verschillen tussen white en black reference gedetecteerd")
    
    # Pas calibratie toe op elke pixel met broadcasting
    calibrated_data = (scan_data - black_ref[np.newaxis, np.newaxis, :]) / denominator[np.newaxis, np.newaxis, :]
    
    print(f"Calibratie voltooid!")
    print(f"Reflectie bereik: {np.min(calibrated_data):.4f} - {np.max(calibrated_data):.4f}")
    
    # Statistieken
    mean_reflectance = np.mean(calibrated_data)
    std_reflectance = np.std(calibrated_data)
    print(f"Gemiddelde reflectie: {mean_reflectance:.4f} ± {std_reflectance:.4f}")
    
    # Bepaal output bestandsnaam
    if output_file is None:
        base_name = os.path.splitext(scan_file)[0]
        output_file = f"{base_name}_calibrated.npy"
    
    # Sla gecalibreerde data op
    try:
        np.save(output_file, calibrated_data)
        print(f"Gecalibreerde scan opgeslagen als: {output_file}")
    except Exception as e:
        print(f"Fout bij opslaan: {e}")
        return None
    
    return calibrated_data
