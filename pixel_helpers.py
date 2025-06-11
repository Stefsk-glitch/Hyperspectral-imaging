from sklearn.utils import resample
import numpy as np

def load_hyperspectral_samples(file_path, label):
    data = np.load(file_path)

    if data.ndim == 3:
        # Vorm: (H, W, B) => herschikken naar (H*W, B)
        samples = data.reshape(-1, data.shape[2])
    elif data.ndim == 2:
        # Vorm is al (N, B)
        samples = data
    else:
        raise ValueError(f"Unexpected array shape: {data.shape}")

    labels = np.full((samples.shape[0],), label)
    return samples, labels

def load_file(file_path):
    array = np.load(file_path)
    if array.shape[2] == 224:
        H, W, B = array.shape  # Opslaan van originele hoogte, breedte en aantal banden
        array = array.reshape(-1, B)  # Shape: (H*W, B)
    elif array.shape[1] == 224:
        array = np.load(file_path)
        H, B, W = array.shape  # Voor array met vorm (H, B, W)
        
        # Transpose om van (H, B, W) naar (H, W, B) te gaan
        array = array.transpose(0, 2, 1)  # Nu vorm (H, W, B)
        
        array = array.reshape(-1, B)  # Shape: (H*W, B)
    
    return array, H, W, B

from sklearn.utils import resample


def balance_classes(X, y, n_samples_per_class=None):
    unique_classes = np.unique(y)

    # If not specified, default to the minimum class size
    if n_samples_per_class is None:
        n_samples_per_class = min([np.sum(y == cls) for cls in unique_classes])

    X_balanced = []
    y_balanced = []

    for cls in unique_classes:
        idx = np.where(y == cls)[0]
        X_cls = X[idx]
        y_cls = y[idx]

        # If not enough samples in this class, skip or warn
        if len(X_cls) < n_samples_per_class:
            print(f"⚠️ Warning: Class '{cls}' only has {len(X_cls)} samples. Skipping.")
            continue

        X_resampled, y_resampled = resample(
            X_cls, y_cls, 
            replace=False, 
            n_samples=n_samples_per_class, 
            random_state=42
        )

        X_balanced.append(X_resampled)
        y_balanced.append(y_resampled)

    if len(X_balanced) == 0:
        raise ValueError("No classes had enough samples for the requested number per class.")

    X_out = np.vstack(X_balanced)
    y_out = np.concatenate(y_balanced)

    return X_out, y_out

import os

def collect_folder_with_labels(folder_path, label):
    """Zoekt alle .npy bestanden in een map (behalve macOS metadata ._ bestanden) en labelt ze."""
    labeled_data = []
    for filename in os.listdir(folder_path):
        # Sla bestanden over die beginnen met '._' (macOS metadata)
        if filename.endswith('.npy') and not filename.startswith("._"):
            full_path = os.path.join(folder_path, filename)
            labeled_data.append([full_path, label])
    return labeled_data

def normalize_input(array):
    """
    Converteer input array naar H, W, B formaat (waarbij B = 224)
    """
    print(f"Array shape: {array.shape}")
    print(f"Number of dimensions: {len(array.shape)}")
    
    if len(array.shape) == 2:
        # 2D array - mogelijk H, W zonder B dimensie
        h, w = array.shape
        if w == 224:
            # Het is waarschijnlijk H, B - voeg W dimensie toe
            # Of reshape naar wat je verwacht
            raise ValueError(f"2D array gevonden {array.shape}. Verwacht 3D array.")
        else:
            raise ValueError(f"2D array met onverwachte vorm: {array.shape}")
    
    elif len(array.shape) == 3:
        if array.shape[2] == 224:  # H, W, B formaat
            return array
        elif array.shape[1] == 224:  # H, B, W formaat  
            return np.transpose(array, (0, 2, 1))  # H, B, W -> H, W, B
        else:
            raise ValueError(f"Geen dimensie met waarde 224 gevonden. Array vorm: {array.shape}")
    
    else:
        raise ValueError(f"Verwacht 2D of 3D array, kreeg {len(array.shape)}D array")