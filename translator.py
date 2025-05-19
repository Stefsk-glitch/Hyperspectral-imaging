import numpy as np
import os
import matplotlib.pyplot as plt

# Load the pre-parsed NumPy array
cube = np.load("data.npy")

print("Cube shape:", cube.shape)

# Create output directory
output_dir = "bands_output"
os.makedirs(output_dir, exist_ok=True)

# Extract number of bands (assumes shape: [samples, bands, width] or similar)
num_bands = cube.shape[1]

# Save each band as grayscale image
for i in range(num_bands):
    band = cube[:, i, :]  # Adjust if your dimension ordering is different
    
    # Normalize to 0–255 range
    norm = 255 * (band - band.min()) / (band.max() - band.min())
    norm = norm.astype(np.uint8)

    plt.imsave(f"{output_dir}/band_{i:03d}.png", norm, cmap='gray')

print(f"Saved {num_bands} bands to folder: {output_dir}/")
