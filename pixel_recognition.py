import numpy as np
from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import Dense
from tensorflow.keras.utils import to_categorical
from tensorflow.keras.models import load_model
from tensorflow.keras.callbacks import EarlyStopping
from sklearn.utils.class_weight import compute_class_weight
from tensorflow.keras.layers import BatchNormalization, Dropout, LeakyReLU
from sklearn.preprocessing import LabelEncoder, StandardScaler
from sklearn.metrics import classification_report
from tensorflow.keras.callbacks import EarlyStopping, ReduceLROnPlateau
from tensorflow.keras.layers import BatchNormalization, Dropout, LeakyReLU
import matplotlib.patches as mpatches

import matplotlib.pyplot as plt
from scipy.ndimage import label
import os

from pixel_helpers import load_hyperspectral_samples, balance_classes, collect_folder_with_labels, normalize_input

class Pixel_recogniser:
    def __init__(self, 
                 pixel_data_folders = [
                     ('model3/Cloth_2', 'cloth'),
                     ('model3/Grass_2', 'grass'),
                     ('model3/union_2', 'onion'),
                    ],
                 pre_loaded=False):

        if not pre_loaded:
            pixel_data = []
            for folder_path, label in pixel_data_folders:
                pixel_data.extend(collect_folder_with_labels(folder_path, label))
            self.load_model(pixel_data)
        else:
            self.load_premade_model()

    #data should consist of a array of type [[file_path, object_name], [file_path, object_name]]
    # Inside class Pixel_recogniser:
    def load_model(self, data): 
        # 1. Load and stack data
        X_list = []
        Y_list = []
        
        for obj in data:
            X_object, Y_object = load_hyperspectral_samples(obj[0], obj[1])
            print(f"{obj[1]} shape: {X_object.shape}")
            X_list.append(X_object)
            Y_list.append(Y_object)

        X = np.vstack(X_list)
        y = np.concatenate(Y_list)

        # 2. Balance classes
        X, y = balance_classes(X, y, n_samples_per_class=300)

        # 3. Normalize data
        self.scaler = StandardScaler()
        X = self.scaler.fit_transform(X)

        # 4. Encode labels
        self.encoder = LabelEncoder()
        y_encoded = self.encoder.fit_transform(y)
        y_categorical = to_categorical(y_encoded)

        # 5. Train/test split
        X_train, X_test, y_train, y_test = train_test_split(X, y_categorical, test_size=0.33, random_state=42)

        # 6. Define improved model
        self.model = Sequential()
        self.model.add(Dense(256, input_shape=(224,)))
        self.model.add(BatchNormalization())
        self.model.add(LeakyReLU())
        self.model.add(Dropout(0.3))

        self.model.add(Dense(128))
        self.model.add(BatchNormalization())
        self.model.add(LeakyReLU())
        self.model.add(Dropout(0.3))

        self.model.add(Dense(y_categorical.shape[1], activation='softmax'))

        # 7. Compile model
        self.model.compile(optimizer='adam', loss='categorical_crossentropy', metrics=['accuracy'])

        # 8. Compute class weights
        class_weights = compute_class_weight('balanced', classes=np.unique(y_encoded), y=y_encoded)
        class_weight_dict = dict(enumerate(class_weights))

        # 9. Callbacks
        early_stop = EarlyStopping(monitor='val_loss', patience=10, restore_best_weights=True)
        reduce_lr = ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=5, min_lr=1e-6, verbose=1)

        # 10. Train model
        self.model.fit(
            X_train, y_train,
            validation_split=0.2,
            epochs=25,
            verbose=1,
            callbacks=[early_stop, reduce_lr],
            class_weight=class_weight_dict
        )

        # 11. Evaluate and print classification report
        y_pred = self.model.predict(X_test)
        y_pred_labels = np.argmax(y_pred, axis=1)
        y_true_labels = np.argmax(y_test, axis=1)
        print("\n📊 Classification Report:\n")
        print(classification_report(y_true_labels, y_pred_labels, target_names=self.encoder.classes_))

        # 12. Save model + encoder
        self.model.save("model3/pixel_model.h5")
        np.save("model3/label_classes.npy", self.encoder.classes_)
        np.save("model3/pixel_scaler.npy", self.scaler.mean_)  # Optional: save mean if needed

    
    # Updated prediction method to apply scaling
    def predict_pixel(self, array, index=1):
        if index == 0:
            raise ValueError("Index must be greater than 0")
        array_scaled = self.scaler.transform(array[:index])
        prediction = self.model.predict(array_scaled)
        prediction_index = np.argmax(prediction[0])
        prediction_class = self.encoder.inverse_transform([prediction_index])
        
        return prediction_class

    def predict_multiple_pixels(self, array, amount=0):
        if amount > 0:
            array = array[:amount]
        array_scaled = self.scaler.transform(array)
        prediction = self.model.predict(array_scaled)
        predicted_indices = np.argmax(prediction, axis=1)
        predicted_classes = self.encoder.inverse_transform(predicted_indices)
        return predicted_classes
    
    def visualize_predictions(self, predicted_classes, H, W, B, confidences=None, confidence_threshold=0.9):
        unique_labels = self.encoder.classes_
        label_to_int = {label: idx + 1 for idx, label in enumerate(unique_labels)}  # Start from 1, so 0 = background
        int_labels = np.zeros(len(predicted_classes), dtype=int)  # All 0 by default = background

        for i, label in enumerate(predicted_classes):
            if confidences is None or confidences[i] >= confidence_threshold:
                int_labels[i] = label_to_int.get(label, 0)  # Unknown labels stay 0

        # Reshape into image
        label_image = int_labels.reshape(H, W)

        # Create colormap with first color = black (for 0)
        from matplotlib.colors import ListedColormap
        cmap = plt.get_cmap('tab10')
        colors = [(0, 0, 0)] + [cmap(i) for i in range(len(unique_labels))]
        custom_cmap = ListedColormap(colors)

        plt.figure(figsize=(8, 6))
        plt.imshow(label_image, cmap=custom_cmap)
        cbar = plt.colorbar(ticks=range(len(colors)))
        cbar.ax.set_yticklabels(['unlabeled'] + list(unique_labels))
        plt.title("Voorspelde classificatie per pixel")
        plt.axis('off')
        plt.show()
        
    import matplotlib.patches as mpatches

    def visualize_labeled_regions(self, hyperspectral_array, H, W, min_region_size=100):
        predicted_labels = self.predict_multiple_pixels(hyperspectral_array)
        label_image = predicted_labels.reshape(H, W)

        unique_classes = np.unique(predicted_labels)

        # Maak een lege RGB-afbeelding met zwarte achtergrond
        overlay = np.zeros((H, W, 3), dtype=np.uint8)

        # Unieke kleuren voor klassen
        cmap = plt.get_cmap('tab10')
        class_colors = {cls: np.array(cmap(i % 10)[:3]) * 255 for i, cls in enumerate(unique_classes)}

        plt.figure(figsize=(10, 8))
        ax = plt.gca()

        for class_label in unique_classes:
            class_mask = (label_image == class_label)
            labeled_array, num_features = label(class_mask)

            for region_id in range(1, num_features + 1):
                region_mask = (labeled_array == region_id)
                region_size = np.sum(region_mask)

                if region_size >= min_region_size:
                    # Kleur de regio in
                    overlay[region_mask] = class_colors[class_label]

                    # Vind het middelpunt van de regio
                    coords = np.argwhere(region_mask)
                    y_mean, x_mean = coords.mean(axis=0).astype(int)

                    # Tekst toevoegen: klasse + ID
                    ax.text(x_mean, y_mean, f"{class_label[:6]} #{region_id}", color='white',
                            fontsize=7, ha='center', va='center', bbox=dict(facecolor='black', alpha=0.5, boxstyle='round'))

        ax.imshow(overlay)
        ax.set_title("Regio's met labels per klasse en ID")
        ax.axis('off')

        # Legenda
        patches = [mpatches.Patch(color=class_colors[cls]/255, label=cls) for cls in unique_classes]
        plt.legend(handles=patches, loc='lower right')
        plt.tight_layout()
        plt.show()
    
    def visualize_labeled_regions_from_map(self, region_map_path, class_name):
        region_map = np.load(region_map_path)
        
        from matplotlib.colors import ListedColormap
        max_val = np.max(region_map)
        cmap = plt.get_cmap('tab20')
        colors = [(0, 0, 0)] + [cmap(i % 20) for i in range(1, max_val + 1)]
        custom_cmap = ListedColormap(colors)

        plt.figure(figsize=(10, 8))
        plt.imshow(region_map, cmap=custom_cmap)
        plt.colorbar(ticks=range(max_val + 1), label='Blob ID')
        plt.title(f"Regio's voor klasse: {class_name}")
        plt.axis('off')
        plt.show()
        
    def export_specific_regions(self, hyperspectral_array, H, W, B, target_class='grass', min_region_size=50, output_dir='grass_regions'):
        # Stap 1: Voorspel labels
        predicted_labels = self.predict_multiple_pixels(hyperspectral_array)

        # Stap 2: Maak masker
        label_image = predicted_labels.reshape(H, W)
        grass_mask = (label_image == target_class)

        # Stap 3: Connected component labeling
        labeled_array, num_features = label(grass_mask)

        # Stap 4: Regio's opslaan
        os.makedirs(output_dir, exist_ok=True)
        region_count = 0

        for region_id in range(1, num_features + 1):
            region_mask = (labeled_array == region_id)
            region_size = np.sum(region_mask)

            if region_size >= min_region_size:
                coords = np.argwhere(region_mask)
                pixels = np.array([hyperspectral_array[x * W + y] for x, y in coords])  # let op: flat index!

                output_path = os.path.join(output_dir, f'grass_region_{region_count}.npy')
                np.save(output_path, pixels)
                print(f"✅ Saved region {region_count} (size: {region_size}) to {output_path}")
                region_count += 1

        if region_count == 0:
            print("⚠️ Geen regio's groter dan de drempel gevonden.")

    def export_all_regions(self, hyperspectral_array, H, W, target_classes=None, min_region_size=100, output_base_dir='region_exports'):
        predicted_labels = self.predict_multiple_pixels(hyperspectral_array)
        label_image = predicted_labels.reshape(H, W)

        if target_classes is None:
            target_classes = np.unique(predicted_labels)

        for target_class in target_classes:
            mask = (label_image == target_class)
            labeled_array, num_features = label(mask)

            os.makedirs(f"{output_base_dir}/{target_class}_regions", exist_ok=True)
            region_id_map = np.zeros_like(mask, dtype=int)
            region_count = 0

            for region_id in range(1, num_features + 1):
                region_mask = (labeled_array == region_id)
                region_size = np.sum(region_mask)

                if region_size >= min_region_size:
                    coords = np.argwhere(region_mask)
                    pixels = np.array([hyperspectral_array[x * W + y] for x, y in coords])

                    output_path = os.path.join(output_base_dir, f"{target_class}_regions/{target_class}_region_{region_count}.npy")
                    np.save(output_path, pixels)

                    for x, y in coords:
                        region_id_map[x, y] = region_count + 1  # +1 so 0 = background

                    print(f"✅ [{target_class}] Blob {region_count} (size: {region_size}) saved to {output_path}")
                    region_count += 1
                # else: skip small regions

            # Save the filtered region map per class
            np.save(f"{output_base_dir}/{target_class}_regions/{target_class}_region_map.npy", region_id_map)


    def load_premade_model(self):
        # Load the trained model
        self.model = load_model("model3/pixel_model.h5")

        # Load label classes and recreate LabelEncoder
        label_classes = np.load("model3/label_classes.npy", allow_pickle=True)
        self.encoder = LabelEncoder()
        self.encoder.classes_ = label_classes

        # Load scaler mean and create a dummy StandardScaler
        scaler_mean = np.load("model3/pixel_scaler.npy")
        self.scaler = StandardScaler()
        self.scaler.mean_ = scaler_mean
        self.scaler.scale_ = np.ones_like(scaler_mean)
        self.scaler.var_ = np.ones_like(scaler_mean)
