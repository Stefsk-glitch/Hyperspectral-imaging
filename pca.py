import sys
import numpy as np
from PyQt5.QtWidgets import (QApplication, QMainWindow, QLabel, QPushButton, 
                            QVBoxLayout, QHBoxLayout, QFileDialog, QSlider, 
                            QWidget, QSpinBox, QGroupBox, QMessageBox,
                            QCheckBox, QComboBox, QScrollArea)
from PyQt5.QtCore import Qt, QRectF, QTimer
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg
from matplotlib.patches import Rectangle
from matplotlib.widgets import RectangleSelector
from PIL import Image
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler

class HyperspectralViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Hyperspectrale Beeldviewer")
        self.setGeometry(100, 100, 1200, 800)  # Nog grotere standaard venstergrootte
        
        # Databeheer
        self.hyperspectral_data = None
        self.reshaped_data = None
        self.bands_count = 0
        self.height = 0
        self.width = 0
        self.current_file_path = ""  # Store the path of the loaded file
        
        # RGB kanalen
        # Aangepaste standaard banden voor gras vs. ui detectie
        self.red_band = 120  # NIR band
        self.green_band = 70  # Rood band
        self.blue_band = 40   # Groen band
        
        # Zoom variabelen
        self.zoom_active = False
        self.rect_selector = None
        self.current_image = None
        self.zoom_coords = None
        self.export_dpi = 300  # Hoge DPI voor export
        
        # Maak timer eenmalig aan voor debouncing
        self.update_timer = QTimer()
        self.update_timer.setSingleShot(True)
        self.update_timer.timeout.connect(self.update_image)
        
        # UI opzetten
        self.setup_ui()
        
    def setup_ui(self):
        # Hoofdwidget en layout
        central_widget = QWidget()
        main_layout = QHBoxLayout(central_widget)  # Horizontale layout voor links/rechts verdeling
        
        # Linker paneel voor controls
        left_panel = QWidget()
        left_layout = QVBoxLayout(left_panel)
        left_panel.setMaximumWidth(400)  # Beperk breedte van control panel
        left_layout.setContentsMargins(0, 0, 0, 0)  # Reduce margins to save space
        
        # Maak een scrollgebied voor het linkerpaneel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)  # Explicitly disable horizontal scrollbar
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # Maak een container widget voor alle controls
        scroll_content = QWidget()
        scroll_layout = QVBoxLayout(scroll_content)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # Set fixed width for the scroll content to match the view's available width
        scroll_content.setMinimumWidth(370)  # Slightly less than the left_panel max width
        scroll_content.setMaximumWidth(370)  # Force content to this width
        
        # Bestand selectie
        file_group = QGroupBox("Bestand selectie")
        file_layout = QVBoxLayout()  # Changed to vertical layout
        
        self.file_label = QLabel("Geen bestand geselecteerd")
        self.file_label.setWordWrap(True)
        self.file_button = QPushButton("Selecteer .npy bestand")
        self.file_button.clicked.connect(self.load_file)
        
        file_layout.addWidget(self.file_label)
        file_layout.addWidget(self.file_button)
        file_group.setLayout(file_layout)
        file_layout.setContentsMargins(5, 5, 5, 5) 
        
        # Sliders voor bandkeuze
        bands_group = QGroupBox("Bandkeuze")
        bands_layout = QVBoxLayout()
        
        # Presets voor vegetatie analyse
        preset_layout = QHBoxLayout()
        preset_label = QLabel("Presets:")
        preset_label.setMaximumWidth(70)  # Limit label width
        self.preset_combo = QComboBox()
        self.preset_combo.addItem("Standaard RGB")
        self.preset_combo.addItem("Vegetatie Detectie (NIR-R-G)")
        self.preset_combo.addItem("NDVI-achtig (NIR-R-B)")
        self.preset_combo.addItem("Chlorofyl focus (NIR-R-RE)")
        self.preset_combo.setEnabled(False)
        self.preset_combo.currentIndexChanged.connect(self.apply_preset)
        
        preset_layout.addWidget(preset_label)
        preset_layout.addWidget(self.preset_combo)
        
        # Rood kanaal
        red_layout = QHBoxLayout()
        red_label = QLabel("Rood:")
        red_label.setFixedWidth(50)  # Fixed width for all channel labels
        self.red_slider = QSlider(Qt.Horizontal)
        self.red_slider.setEnabled(False)
        self.red_slider.valueChanged.connect(self.update_red_band)
        
        self.red_spinbox = QSpinBox()
        self.red_spinbox.setEnabled(False)
        self.red_spinbox.valueChanged.connect(self.update_red_band_from_spinbox)
        self.red_spinbox.setFixedWidth(60)  # Fixed width for all spinboxes
        
        red_layout.addWidget(red_label)
        red_layout.addWidget(self.red_slider)
        red_layout.addWidget(self.red_spinbox)
        
        # Groen kanaal
        green_layout = QHBoxLayout()
        green_label = QLabel("Groen:")
        green_label.setFixedWidth(50)  # Fixed width
        self.green_slider = QSlider(Qt.Horizontal)
        self.green_slider.setEnabled(False)
        self.green_slider.valueChanged.connect(self.update_green_band)
        
        self.green_spinbox = QSpinBox()
        self.green_spinbox.setEnabled(False)
        self.green_spinbox.valueChanged.connect(self.update_green_band_from_spinbox)
        self.green_spinbox.setFixedWidth(60)  # Fixed width
        
        green_layout.addWidget(green_label)
        green_layout.addWidget(self.green_slider)
        green_layout.addWidget(self.green_spinbox)
        
        # Blauw kanaal
        blue_layout = QHBoxLayout()
        blue_label = QLabel("Blauw:")
        blue_label.setFixedWidth(50)  # Fixed width
        self.blue_slider = QSlider(Qt.Horizontal)
        self.blue_slider.setEnabled(False)
        self.blue_slider.valueChanged.connect(self.update_blue_band)
        
        self.blue_spinbox = QSpinBox()
        self.blue_spinbox.setEnabled(False)
        self.blue_spinbox.valueChanged.connect(self.update_blue_band_from_spinbox)
        self.blue_spinbox.setFixedWidth(60)  # Fixed width
        
        blue_layout.addWidget(blue_label)
        blue_layout.addWidget(self.blue_slider)
        blue_layout.addWidget(self.blue_spinbox)
        
        bands_layout.addLayout(preset_layout)
        bands_layout.addLayout(red_layout)
        bands_layout.addLayout(green_layout)
        bands_layout.addLayout(blue_layout)
        bands_group.setLayout(bands_layout)
        bands_layout.setContentsMargins(5, 5, 5, 5)
        
        # Zoom en Export controls
        tools_group = QGroupBox("Tools")
        tools_layout = QVBoxLayout()  # Verticale layout voor tools
        
        # Add PCA section
        pca_group = QGroupBox("PCA Visualisatie voor Ui vs. Gras Detectie")
        pca_layout = QVBoxLayout()
        
        # Number of components selection
        pca_components_layout = QHBoxLayout()
        pca_components_label = QLabel("Aantal componenten:")
        pca_components_label.setFixedWidth(120)  # Fixed width
        self.pca_components_spinbox = QSpinBox()
        self.pca_components_spinbox.setRange(3, 10)
        self.pca_components_spinbox.setValue(4)  # 4 componenten is optimaal voor vegetatie
        self.pca_components_spinbox.setEnabled(False)
        self.pca_components_spinbox.setFixedWidth(60)  # Fixed width
        
        pca_components_layout.addWidget(pca_components_label)
        pca_components_layout.addWidget(self.pca_components_spinbox)
        pca_components_layout.addStretch(1)  # Add stretch to prevent expanding
        
        pca_components_tip = QLabel("Tip: 4 componenten vaak optimaal voor vegetatie")
        pca_components_tip.setStyleSheet("color: gray; font-size: 10pt;")
        pca_components_tip.setWordWrap(True)
        
        # Vegetatie preset buttons
        veg_preset_layout = QVBoxLayout()  # Changed to vertical for more space
        self.ui_gras_preset_button = QPushButton("Ui vs. Gras Optimale Instellingen")
        self.ui_gras_preset_button.setEnabled(False)
        self.ui_gras_preset_button.clicked.connect(self.apply_onion_grass_preset)
        veg_preset_layout.addWidget(self.ui_gras_preset_button)
        
        # PCA button
        self.apply_pca_button = QPushButton("Bereken en toon PCA")
        self.apply_pca_button.setEnabled(False)
        self.apply_pca_button.clicked.connect(self.apply_pca)
        
        # PCA type selection - Full vs Region
        pca_type_layout = QHBoxLayout()
        pca_type_label = QLabel("PCA berekenen op:")
        pca_type_label.setFixedWidth(120)  # Fixed width
        self.pca_type_combo = QComboBox()
        self.pca_type_combo.addItem("Volledige afbeelding")
        self.pca_type_combo.addItem("Alleen geselecteerde regio")
        self.pca_type_combo.setEnabled(False)
        
        pca_type_layout.addWidget(pca_type_label)
        pca_type_layout.addWidget(self.pca_type_combo)
        
        # PCA component selection for RGB display
        pca_rgb_group = QGroupBox("PCA componenten voor RGB")
        pca_rgb_layout = QVBoxLayout()
        
        # R component
        pca_r_layout = QHBoxLayout()
        pca_r_label = QLabel("R component:")
        pca_r_label.setFixedWidth(90)  # Fixed width
        self.pca_r_spinbox = QSpinBox()
        self.pca_r_spinbox.setRange(1, 10)
        self.pca_r_spinbox.setValue(1)  # PC1 voor Red (algemene structuur)
        self.pca_r_spinbox.setEnabled(False)
        self.pca_r_spinbox.setFixedWidth(60)  # Fixed width
        
        pca_r_layout.addWidget(pca_r_label)
        pca_r_layout.addWidget(self.pca_r_spinbox)
        pca_r_layout.addStretch(1)  # Add stretch to prevent expanding
        
        # G component
        pca_g_layout = QHBoxLayout()
        pca_g_label = QLabel("G component:")
        pca_g_label.setFixedWidth(90)  # Fixed width
        self.pca_g_spinbox = QSpinBox()
        self.pca_g_spinbox.setRange(1, 10)
        self.pca_g_spinbox.setValue(2)  # PC2 voor Green (vegetatie verschillen)
        self.pca_g_spinbox.setEnabled(False)
        self.pca_g_spinbox.setFixedWidth(60)  # Fixed width
        
        pca_g_layout.addWidget(pca_g_label)
        pca_g_layout.addWidget(self.pca_g_spinbox)
        pca_g_layout.addStretch(1)  # Add stretch to prevent expanding
        
        # B component
        pca_b_layout = QHBoxLayout()
        pca_b_label = QLabel("B component:")
        pca_b_label.setFixedWidth(90)  # Fixed width
        self.pca_b_spinbox = QSpinBox()
        self.pca_b_spinbox.setRange(1, 10)
        self.pca_b_spinbox.setValue(3)  # PC3 voor Blue (subtiele verschillen)
        self.pca_b_spinbox.setEnabled(False)
        self.pca_b_spinbox.setFixedWidth(60)  # Fixed width
        
        pca_b_layout.addWidget(pca_b_label)
        pca_b_layout.addWidget(self.pca_b_spinbox)
        pca_b_layout.addStretch(1)  # Add stretch to prevent expanding
        
        # Uitleg voor componenten
        pca_tips_label = QLabel("PC1: algemene helderheid, PC2/PC3: vegetatiestructuur, PC4: subtiele verschillen")
        pca_tips_label.setStyleSheet("color: gray; font-size: 10pt;")
        pca_tips_label.setWordWrap(True)
        
        pca_rgb_layout.addLayout(pca_r_layout)
        pca_rgb_layout.addLayout(pca_g_layout)
        pca_rgb_layout.addLayout(pca_b_layout)
        pca_rgb_layout.addWidget(pca_tips_label)
        pca_rgb_group.setLayout(pca_rgb_layout)
        pca_rgb_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add all PCA controls to layout
        pca_layout.addLayout(pca_components_layout)
        pca_layout.addWidget(pca_components_tip)
        pca_layout.addLayout(veg_preset_layout)
        pca_layout.addLayout(pca_type_layout)
        pca_layout.addWidget(pca_rgb_group)
        pca_layout.addWidget(self.apply_pca_button)
        
        pca_group.setLayout(pca_layout)
        pca_layout.setContentsMargins(5, 5, 5, 5)
        
        # Add PCA group to tools layout
        tools_layout.addWidget(pca_group)
        
        # Zoom controls
        zoom_layout = QVBoxLayout()  # Changed to vertical layout
        self.zoom_checkbox = QCheckBox("Zoom modus")
        self.zoom_checkbox.setEnabled(False)
        self.zoom_checkbox.stateChanged.connect(self.toggle_zoom_mode)
        
        self.reset_zoom_button = QPushButton("Reset zoom")
        self.reset_zoom_button.setEnabled(False)
        self.reset_zoom_button.clicked.connect(self.reset_zoom)
        
        zoom_layout.addWidget(self.zoom_checkbox)
        zoom_layout.addWidget(self.reset_zoom_button)
        
        # Export controls
        export_layout = QVBoxLayout()  # Changed to vertical for better fit
        
        dpi_layout = QHBoxLayout()
        dpi_label = QLabel("Export DPI:")
        dpi_label.setFixedWidth(80)  # Fixed width
        self.dpi_spinbox = QSpinBox()
        self.dpi_spinbox.setRange(72, 1200)
        self.dpi_spinbox.setValue(300)
        self.dpi_spinbox.setSingleStep(100)
        self.dpi_spinbox.setFixedWidth(80)  # Fixed width
        
        dpi_layout.addWidget(dpi_label)
        dpi_layout.addWidget(self.dpi_spinbox)
        dpi_layout.addStretch(1)  # Add stretch to prevent expanding
        
        self.export_button = QPushButton("Exporteer selectie (RGB afbeelding)")
        self.export_button.setEnabled(False)
        self.export_button.clicked.connect(self.export_selection)
        
        # Nieuwe knop voor het exporteren van de hyperspectrale data
        self.export_data_button = QPushButton("Exporteer selectie (hyperspectrale data)")
        self.export_data_button.setEnabled(False)
        self.export_data_button.clicked.connect(self.export_hyperspectral_data)
        
        export_layout.addLayout(dpi_layout)
        export_layout.addWidget(self.export_button)
        export_layout.addWidget(self.export_data_button)
        
        tools_layout.addLayout(zoom_layout)
        tools_layout.addLayout(export_layout)
        tools_group.setLayout(tools_layout)
        tools_layout.setContentsMargins(5, 5, 5, 5)
        
        # Info label
        self.info_label = QLabel("")
        self.info_label.setWordWrap(True)
        
        # Voeg alle groepen toe aan het scroll content
        scroll_layout.addWidget(file_group)
        scroll_layout.addWidget(bands_group)
        scroll_layout.addWidget(tools_group)
        scroll_layout.addWidget(self.info_label)
        scroll_layout.addStretch()  # Voeg stretch toe om controls bovenaan te houden
        
        # Stel het scroll content widget in voor het scrollgebied
        scroll_content.setLayout(scroll_layout)
        scroll_area.setWidget(scroll_content)
        
        # Voeg scrollgebied toe aan left_layout
        left_layout.addWidget(scroll_area)
        
        # Rechter paneel voor figuur
        right_panel = QWidget()
        right_layout = QVBoxLayout(right_panel)
        
        # Beeld weergave
        self.figure = plt.figure(figsize=(10, 8))
        self.canvas = FigureCanvasQTAgg(self.figure)
        right_layout.addWidget(self.canvas)
        
        # Voeg beide panelen toe aan hoofdlayout
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)  # Geef rechter paneel proportioneel meer ruimte
        
        self.setCentralWidget(central_widget)
        
    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open .npy bestand", "", "NumPy Files (*.npy)")
        if file_path:
            try:
                # Reset any existing state
                self.zoom_coords = None
                self.current_zoom_indices = None
                
                # Load the .npy file
                self.hyperspectral_data = np.load(file_path)
                self.current_file_path = file_path  # Save the file path
                
                # Log the original shape
                print(f"Originele data vorm: {self.hyperspectral_data.shape}")
                
                # Process the data, considering known dimensions
                self.process_data()
                
                # Update UI
                self.file_label.setText(f"Geladen: {file_path}")
                self.info_label.setText(f"Dimensies: {self.height} × {self.width} × {self.bands_count} banden")
                
                # Set sliders based on number of bands
                self.update_sliders()
                
                # Update image
                self.update_image()
                
                # Activate zoom and export controls
                self.zoom_checkbox.setEnabled(True)
                self.reset_zoom_button.setEnabled(True)
                self.export_button.setEnabled(True)
                self.export_data_button.setEnabled(True)  # Activate the new button
                self.preset_combo.setEnabled(True)
                
                self.pca_components_spinbox.setEnabled(True)
                self.apply_pca_button.setEnabled(True)
                self.pca_type_combo.setEnabled(True)
                self.pca_r_spinbox.setEnabled(True)
                self.pca_g_spinbox.setEnabled(True)
                self.pca_b_spinbox.setEnabled(True)
                self.ui_gras_preset_button.setEnabled(True)  # Enable the UI vs Grass preset button

                
            except Exception as e:
                self.show_error(f"Fout bij het laden van het bestand: {str(e)}")
                import traceback
                traceback.print_exc()
                    
    def process_data(self):
        """Verwerk de data naar het juiste formaat, rekening houdend met de bekende dimensies"""
        data = self.hyperspectral_data
        
        # Probeer de data structuur te bepalen
        if len(data.shape) == 3:
            # Bekijk de dimensies
            dim1, dim2, dim3 = data.shape
            
            # Als dit een klein uitgesneden bestand is (zoomed export), gebruik direct
            if dim1 < 500 and dim2 < 500 and dim3 > 100:  # Typische uitgesneden afmetingen
                print("Gedetecteerd als uitgesneden data, wordt direct gebruikt")
                self.reshaped_data = data
                self.height, self.width, self.bands_count = data.shape
                return

            # Controleer of één van de dimensies dicht bij 224 is (aantal kanalen/banden)
            if dim2 >= 200 and dim2 <= 250:
                # Waarschijnlijk (hoogte, kanalen, breedte) formaat
                print("Data heeft waarschijnlijk formaat (hoogte, kanalen, breedte)")
                # Herorden naar (hoogte, breedte, kanalen)
                self.reshaped_data = np.transpose(data, (0, 2, 1))
                self.height, self.width, self.bands_count = self.reshaped_data.shape
            elif dim1 >= 200 and dim1 <= 250:
                # Waarschijnlijk (kanalen, hoogte, breedte) formaat
                print("Data heeft waarschijnlijk formaat (kanalen, hoogte, breedte)")
                self.reshaped_data = np.transpose(data, (1, 2, 0))
                self.height, self.width, self.bands_count = self.reshaped_data.shape
            elif dim3 >= 200 and dim3 <= 250:
                # Waarschijnlijk (hoogte, breedte, kanalen) formaat - al goed
                print("Data heeft waarschijnlijk formaat (hoogte, breedte, kanalen)")
                self.reshaped_data = data
                self.height, self.width, self.bands_count = data.shape
            else:
                # Als geen dimensie dicht bij 224 is, ga uit van standaard formaat (hoogte, breedte, kanalen)
                print(f"Kon geen kanaalsdimensie vinden, gebruik standaard formaat (hoogte, breedte, kanalen)")
                self.reshaped_data = data
                self.height, self.width, self.bands_count = data.shape
                
            print(f"Verwerkte data vorm: {self.reshaped_data.shape}")
        else:
            self.show_error(f"Onverwachte data vorm: {data.shape}. Verwacht een 3D array.")
            return
        
        # Controleer of we genoeg banden hebben voor RGB
        if self.bands_count < 3:
            self.show_error(f"Minimaal 3 banden nodig, maar slechts {self.bands_count} gevonden")
            return
    
    def update_sliders(self):
        max_band = self.bands_count - 1
        
        # Standaard bandkeuzes aangepast voor vegetatie detectie
        default_red = min(120, max_band)   # NIR band
        default_green = min(70, max_band)  # Rood band
        default_blue = min(40, max_band)   # Groen band
        
        # Werk sliders bij
        for slider, spinbox, default_value in [
            (self.red_slider, self.red_spinbox, default_red),
            (self.green_slider, self.green_spinbox, default_green),
            (self.blue_slider, self.blue_spinbox, default_blue)
        ]:
            slider.setMinimum(0)
            slider.setMaximum(max_band)
            slider.setValue(default_value)
            slider.setEnabled(True)
            
            spinbox.setMinimum(0)
            spinbox.setMaximum(max_band)
            spinbox.setValue(default_value)
            spinbox.setEnabled(True)
        
        # Zet de initiële waarden
        self.red_band = default_red
        self.green_band = default_green
        self.blue_band = default_blue
        
        # Selecteer standaard de vegetatie detectie preset
        self.preset_combo.setCurrentIndex(1)  # Vegetatie Detectie preset
    
    def apply_preset(self, index):
        """Past voorgedefinieerde bandcombinaties toe"""
        max_band = self.bands_count - 1
        
        if index == 0:  # Standaard RGB
            r, g, b = min(20, max_band), min(80, max_band), min(150, max_band)
        elif index == 1:  # Vegetatie Detectie (NIR-R-G)
            r, g, b = min(120, max_band), min(70, max_band), min(40, max_band)
        elif index == 2:  # NDVI-achtig (NIR-R-B)
            r, g, b = min(120, max_band), min(70, max_band), min(20, max_band)
        elif index == 3:  # Chlorofyl focus (NIR-R-RE)
            r, g, b = min(120, max_band), min(70, max_band), min(90, max_band)
        
        # Update sliders without triggering signals
        self.red_slider.blockSignals(True)
        self.green_slider.blockSignals(True)
        self.blue_slider.blockSignals(True)
        self.red_spinbox.blockSignals(True)
        self.green_spinbox.blockSignals(True)
        self.blue_spinbox.blockSignals(True)
        
        self.red_slider.setValue(r)
        self.green_slider.setValue(g)
        self.blue_slider.setValue(b)
        self.red_spinbox.setValue(r)
        self.green_spinbox.setValue(g)
        self.blue_spinbox.setValue(b)
        
        self.red_band = r
        self.green_band = g
        self.blue_band = b
        
        self.red_slider.blockSignals(False)
        self.green_slider.blockSignals(False)
        self.blue_slider.blockSignals(False)
        self.red_spinbox.blockSignals(False)
        self.green_spinbox.blockSignals(False)
        self.blue_spinbox.blockSignals(False)
        
        # Update beeld direct
        self.update_image()
    
    def update_red_band(self):
        self.red_band = self.red_slider.value()
        self.red_spinbox.blockSignals(True)
        self.red_spinbox.setValue(self.red_band)
        self.red_spinbox.blockSignals(False)
        # Verbeterde debouncing met korte tijd
        self.delayed_update_image(10)  # Verlaagd naar 10ms voor snellere respons
    
    def update_green_band(self):
        self.green_band = self.green_slider.value()
        self.green_spinbox.blockSignals(True)
        self.green_spinbox.setValue(self.green_band)
        self.green_spinbox.blockSignals(False)
        # Verbeterde debouncing met korte tijd
        self.delayed_update_image(10)  # Verlaagd naar 10ms voor snellere respons
    
    def update_blue_band(self):
        self.blue_band = self.blue_slider.value()
        self.blue_spinbox.blockSignals(True)
        self.blue_spinbox.setValue(self.blue_band)
        self.blue_spinbox.blockSignals(False)
        # Verbeterde debouncing met korte tijd
        self.delayed_update_image(10)  # Verlaagd naar 10ms voor snellere respons
    
    def delayed_update_image(self, delay=50):
        # Stop eerder geplande updates
        self.update_timer.stop()
        # Start een nieuwe timer met de gegeven vertraging
        self.update_timer.start(delay)
    
    def update_red_band_from_spinbox(self):
        self.red_band = self.red_spinbox.value()
        self.red_slider.blockSignals(True)
        self.red_slider.setValue(self.red_band)
        self.red_slider.blockSignals(False)
        self.update_image()
    
    def update_green_band_from_spinbox(self):
        self.green_band = self.green_spinbox.value()
        self.green_slider.blockSignals(True)
        self.green_slider.setValue(self.green_band)
        self.green_slider.blockSignals(False)
        self.update_image()
    
    def update_blue_band_from_spinbox(self):
        self.blue_band = self.blue_spinbox.value()
        self.blue_slider.blockSignals(True)
        self.blue_slider.setValue(self.blue_band)
        self.blue_slider.blockSignals(False)
        self.update_image()
        
    def update_image(self):
        if self.reshaped_data is None:
            return
        
        try:
            # Block slider signals temporarily
            self.red_slider.blockSignals(True)
            self.green_slider.blockSignals(True)
            self.blue_slider.blockSignals(True)
            
            # Prepare data
            if self.zoom_coords is not None:
                x1, y1, x2, y2 = self.zoom_coords
                
                # Convert to integer indices but ensure proper ordering
                ix1, ix2 = int(min(x1, x2)), int(max(x1, x2))
                iy1, iy2 = int(min(y1, y2)), int(max(y1, y2))
                
                # Make sure the indices are within bounds
                ix1 = max(0, min(ix1, self.width-1))
                ix2 = max(0, min(ix2, self.width-1))
                iy1 = max(0, min(iy1, self.height-1))
                iy2 = max(0, min(iy2, self.height-1))
                
                # Ensure minimum size of 1 pixel
                if ix1 == ix2:
                    ix2 = min(ix1 + 1, self.width-1)
                if iy1 == iy2:
                    iy2 = min(iy1 + 1, self.height-1)
                
                # Get the bands
                try:
                    r_band = self.reshaped_data[iy1:iy2+1, ix1:ix2+1, self.red_band].copy()
                    g_band = self.reshaped_data[iy1:iy2+1, ix1:ix2+1, self.green_band].copy()
                    b_band = self.reshaped_data[iy1:iy2+1, ix1:ix2+1, self.blue_band].copy()
                    
                    # Store the actual used coordinates for export
                    self.current_zoom_indices = (ix1, iy1, ix2, iy2)
                except IndexError as e:
                    print(f"IndexError during slice: {e}")
                    print(f"Attempted slice: [{iy1}:{iy2+1}, {ix1}:{ix2+1}, {self.red_band}]")
                    print(f"Data shape: {self.reshaped_data.shape}")
                    # Reset zoom if we got an index error
                    self.zoom_coords = None
                    self.info_label.setText("Zoom reset vanwege index fout")
                    return self.update_image()
            else:
                r_band = self.reshaped_data[:, :, self.red_band].copy()
                g_band = self.reshaped_data[:, :, self.green_band].copy()
                b_band = self.reshaped_data[:, :, self.blue_band].copy()
                self.current_zoom_indices = None
            # Rest van de functie blijft hetzelfde...
            
            # Normaliseer de banden (voor elke band afzonderlijk)
            def normalize(band):
                min_val = np.percentile(band, 2)  # Gebruik percentiel voor minder gevoeligheid voor uitschieters
                max_val = np.percentile(band, 98)
                if max_val > min_val:
                    norm = np.clip((band - min_val) / (max_val - min_val), 0, 1)
                    return norm
                return np.zeros_like(band)
            
            r_norm = normalize(r_band)
            g_norm = normalize(g_band)
            b_norm = normalize(b_band)
            
            # Maak RGB beeld
            rgb_image = np.stack([r_norm, g_norm, b_norm], axis=2)
            self.current_image = rgb_image  # Bewaar huidige beeld voor export
            
            # Toon de afbeelding
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            # Bij zoom, stel figuurgrootte in om pixelatie te voorkomen
            if self.zoom_coords is not None:
                # Bereken aspect ratio voor juiste weergave
                height, width = rgb_image.shape[:2]
                aspect_ratio = height / width if width > 0 else 1
                
                # Pas de figuurgrootte aan voor betere resolutie bij zoom
                fig_width = 10  # Grotere breedte
                fig_height = fig_width * aspect_ratio
                self.figure.set_size_inches(fig_width, fig_height)
                
                # Gebruik hoge DPI en bicubic interpolatie voor betere kwaliteit
                ax.imshow(rgb_image, interpolation='bicubic')
                ax.set_title(f"RGB beeld (R:{self.red_band}, G:{self.green_band}, B:{self.blue_band})\nZoom: ({x1},{y1}) - ({x2},{y2})")
            else:
                # Standaard figuurgrootte voor volledig beeld
                self.figure.set_size_inches(10, 8)
                ax.imshow(rgb_image, interpolation='bicubic')
                ax.set_title(f"RGB beeld (R:{self.red_band}, G:{self.green_band}, B:{self.blue_band})")
            
            ax.axis('off')
            
            # Configureer de rectangle selector voor zoom als deze actief is
            if self.zoom_active:
                self.setup_rectangle_selector(ax)
            
            self.canvas.draw()
            
            # Herstel slider signalen
            self.red_slider.blockSignals(False)
            self.green_slider.blockSignals(False)
            self.blue_slider.blockSignals(False)
        except Exception as e:
            self.show_error(f"Fout bij beeldverwerking: {str(e)}")
            import traceback
            traceback.print_exc()
                
    def apply_onion_grass_preset(self):
        """Past de optimale instellingen toe voor ui vs. gras detectie"""
        # Optimale aantal componenten voor vegetatie detectie
        self.pca_components_spinbox.setValue(4)
        
        # Optimale PCA componenten voor vegetatie contrast
        self.pca_r_spinbox.setValue(1)  # PC1 toont algemene helderheid/structuur
        self.pca_g_spinbox.setValue(2)  # PC2 toont vaak belangrijke vegetatie-kenmerken
        self.pca_b_spinbox.setValue(4)  # PC4 toont subtielere verschillen (beter dan PC3 voor ui vs. gras)
        
        # Toon uitleg
        self.info_label.setText("Optimale instellingen toegepast voor ui vs. gras detectie. "
                            "PC1=R toont algemene structuur, PC2=G toont vegetatieverschillen, "
                            "PC4=B benadrukt subtiele verschillen tussen ui en gras. "
                            "Klik op 'Bereken en toon PCA' om te analyseren.")
        
    def apply_pca(self):
        """Bereken PCA op de hyperspectrale data en toon de resultaten, geoptimaliseerd voor ui vs. gras detectie"""
        if self.reshaped_data is None:
            self.show_error("Geen data beschikbaar voor PCA")
            return
        
        try:
            # Toon voortgangsinformatie
            self.info_label.setText("PCA berekenen voor ui vs. gras detectie, even geduld...")
            QApplication.processEvents()  # Ververs UI tijdens berekening
            
            # Aantal componenten ophalen - standaard 4 voor vegetatie-onderscheiding
            n_components = self.pca_components_spinbox.value()
            
            # Controleer of we op de hele afbeelding of alleen op de regio werken
            full_image = (self.pca_type_combo.currentIndex() == 0)
            
            if not full_image and self.current_zoom_indices is None:
                self.show_error("Geen regio geselecteerd. Selecteer een regio of kies 'Volledige afbeelding'.")
                return
            
            # Data voorbereiden
            if full_image:
                # Hele afbeelding
                data_shape = self.reshaped_data.shape
                # Hervormen naar 2D array: (pixels, bands)
                data_2d = self.reshaped_data.reshape(-1, data_shape[2])
                original_shape = data_shape[:2]  # (height, width)
            else:
                # Alleen geselecteerde regio
                ix1, iy1, ix2, iy2 = self.current_zoom_indices
                region_data = self.reshaped_data[iy1:iy2+1, ix1:ix2+1, :]
                data_shape = region_data.shape
                # Hervormen naar 2D array: (pixels, bands)
                data_2d = region_data.reshape(-1, data_shape[2])
                original_shape = data_shape[:2]  # (height, width)
            
            # Verwijder NaN waarden (als die er zijn)
            data_2d = np.nan_to_num(data_2d)
            
            # OPTIMALISATIE 1: Focus op RED-EDGE en NIR banden voor vegetatie
            # Typisch belangrijke banden voor vegetatie-onderscheid
            # Selecteer alleen relevante banden als er veel zijn
            if data_shape[2] > 50:  # Als er veel banden zijn
                # Bepaal geschatte indices voor rode rand en NIR banden
                # Dit zijn typisch belangrijke delen van het spectrum voor vegetatie-analyse
                red_edge_start = max(0, min(int(data_shape[2] * 0.3), data_shape[2]-1))  # ~650nm
                nir_end = max(0, min(int(data_shape[2] * 0.7), data_shape[2]-1))         # ~1000nm
                
                # Selecteer subset van banden die relevant zijn voor vegetatie-onderscheid
                # Focus op rode, rode rand, en NIR banden die gras vs. ui onderscheid verbeteren
                # Dit kan aangepast worden op basis van kennis over de specifieke sensor
                vegetation_band_subset = np.arange(red_edge_start, nir_end)
                
                # Uitleg toevoegen aan info-label
                band_info = f"Focus op banden {red_edge_start}-{nir_end} (rode rand tot NIR) voor vegetatie-analyse. "
                
                # Pas alleen de geselecteerde banden toe
                data_2d_veg = data_2d[:, vegetation_band_subset]
            else:
                # Als er weinig banden zijn, gebruik alles
                data_2d_veg = data_2d
                band_info = "Alle beschikbare banden gebruikt voor analyse. "
            
            # OPTIMALISATIE 2: Verbeterde pre-processing
            # Standaardiseer de data (belangrijk voor PCA)
            scaler = StandardScaler()
            data_2d_scaled = scaler.fit_transform(data_2d_veg)
            
            # OPTIMALISATIE 3: Robuustere PCA met whitening
            # Whitening is belangrijk om componenten echt onafhankelijk te maken
            # Dit verbetert de scheiding van subtiele verschillen in vegetatie
            pca = PCA(n_components=n_components, whiten=True)
            principal_components = pca.fit_transform(data_2d_scaled)
            
            # Verkrijg de optimale componenten voor ui vs. gras onderscheid
            # Standaard de eerste 3 componenten gebruiken met mogelijk betere mapping
            r_idx = self.pca_r_spinbox.value() - 1  # -1 omdat gebruikers tellen vanaf 1
            g_idx = self.pca_g_spinbox.value() - 1
            b_idx = self.pca_b_spinbox.value() - 1
            
            # Controleer of indices geldig zijn
            if max(r_idx, g_idx, b_idx) >= n_components:
                self.show_error(f"Component index te hoog. Maximum is {n_components}.")
                return
            
            # Haal RGB componenten
            r_comp = principal_components[:, r_idx].reshape(original_shape)
            g_comp = principal_components[:, g_idx].reshape(original_shape)
            b_comp = principal_components[:, b_idx].reshape(original_shape)
            
            # OPTIMALISATIE 4: Verbeterde normalisering voor beter contrast tussen vegetatietypes
            def enhance_vegetation_contrast(band, percentile_min=2, percentile_max=98):
                """Verbeterde normalisatie voor vegetatiecontrast"""
                min_val = np.percentile(band, percentile_min)
                max_val = np.percentile(band, percentile_max)
                
                if max_val > min_val:
                    # Lineaire stretch met clip
                    normalized = np.clip((band - min_val) / (max_val - min_val), 0, 1)
                    
                    # Optioneel: Gamma correctie om middenwaarden te versterken (waar vegetatie onderscheid vaak zit)
                    # gamma = 0.85  # Waarde < 1 verbetert contrast in middenwaarden
                    # normalized = np.power(normalized, gamma)
                    
                    return normalized
                return np.zeros_like(band)
            
            # Pas verbeterde normalisatie toe
            r_norm = enhance_vegetation_contrast(r_comp)
            g_norm = enhance_vegetation_contrast(g_comp)
            b_norm = enhance_vegetation_contrast(b_comp)
            
            # Maak RGB beeld van PCA componenten
            pca_rgb = np.stack([r_norm, g_norm, b_norm], axis=2)
            
            # Bewaar het PCA beeld voor export
            self.current_image = pca_rgb
            
            # OPTIMALISATIE 5: Duidelijke visualisatie
            # Toon de afbeelding
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            ax.imshow(pca_rgb, interpolation='bicubic')
            
            # Variance verklaard door elke component
            variance_explained = pca.explained_variance_ratio_
            
            # Bereken specifiek hoeveel van de totale variantie wordt verklaard
            total_explained = sum(variance_explained)
            rgb_explained = variance_explained[r_idx] + variance_explained[g_idx] + variance_explained[b_idx]
            
            title = f"PCA Vegetatie Detectie (R:PC{r_idx+1}, G:PC{g_idx+1}, B:PC{b_idx+1})\n"
            title += f"Verklaarde variantie: R:{variance_explained[r_idx]:.2%}, "
            title += f"G:{variance_explained[g_idx]:.2%}, "
            title += f"B:{variance_explained[b_idx]:.2%}"
            
            ax.set_title(title)
            ax.axis('off')
            
            # Als zoom actief is, behoud rectangle selector
            if self.zoom_active:
                self.setup_rectangle_selector(ax)
            
            self.canvas.draw()
            
            # OPTIMALISATIE 6: Betere uitleg
            # Informatie tonen met vegetatie-specifieke details
            info_text = f"PCA voor ui vs. gras detectie: {band_info}"
            info_text += f"Berekend op {data_2d_veg.shape[0]} pixels met {data_2d_veg.shape[1]} relevante banden. "
            info_text += f"Totale verklaarde variantie: {total_explained:.2%}. "
            info_text += f"\nTip: PC1 toont meestal algemene helderheid, PC2/PC3 tonen vaak vegetatieverschillen."
            self.info_label.setText(info_text)
            
        except Exception as e:
            self.show_error(f"Fout bij PCA berekening: {str(e)}")
            import traceback
            traceback.print_exc()        
            # Normaliseer elke component voor weergave
            def normalize(band):
                min_val = np.percentile(band, 2)
                max_val = np.percentile(band, 98)
                if max_val > min_val:
                    return np.clip((band - min_val) / (max_val - min_val), 0, 1)
                return np.zeros_like(band)
            
            r_norm = normalize(r_comp)
            g_norm = normalize(g_comp)
            b_norm = normalize(b_comp)
            
            # Maak RGB beeld van PCA componenten
            pca_rgb = np.stack([r_norm, g_norm, b_norm], axis=2)
            
            # Bewaar het PCA beeld voor export
            self.current_image = pca_rgb
            
            # Toon de afbeelding
            self.figure.clear()
            ax = self.figure.add_subplot(111)
            
            ax.imshow(pca_rgb, interpolation='bicubic')
            
            # Variance verklaard door elke component
            variance_explained = pca.explained_variance_ratio_
            total_variance = variance_explained[:3].sum()
            
            title = f"PCA RGB (R:PC{r_idx+1}, G:PC{g_idx+1}, B:PC{b_idx+1})\n"
            title += f"Verklaarde variantie: R:{variance_explained[r_idx]:.2%}, "
            title += f"G:{variance_explained[g_idx]:.2%}, "
            title += f"B:{variance_explained[b_idx]:.2%}"
            
            ax.set_title(title)
            ax.axis('off')
            
            # Als zoom actief is, behoud rectangle selector
            if self.zoom_active:
                self.setup_rectangle_selector(ax)
            
            self.canvas.draw()
            
            # Informatie tonen
            info_text = f"PCA berekend op {data_2d.shape[0]} pixels met {data_2d.shape[1]} banden. "
            info_text += f"Totale verklaarde variantie (top {n_components}): {sum(variance_explained):.2%}"
            self.info_label.setText(info_text)
            
        except Exception as e:
            self.show_error(f"Fout bij PCA berekening: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def toggle_zoom_mode(self, state):
        self.zoom_active = (state == Qt.Checked)
        if self.zoom_active:
            self.info_label.setText("Zoom modus: Selecteer een gebied om in te zoomen")
            # Herstel al bestaande zoom voor betere selectie
            self.zoom_coords = None
            self.update_image()
        else:
            if self.rect_selector:
                self.rect_selector.set_active(False)
            self.info_label.setText("")
    
    def setup_rectangle_selector(self, ax):
        # Maak of hergebruik rectangle selector
        self.rect_selector = RectangleSelector(
            ax, self.on_select,
            useblit=True,
            button=[1],  # Alleen linker muisknop
            minspanx=5, minspany=5,
            spancoords='pixels',
            interactive=True
        )
        self.rect_selector.set_active(True)
    
    def on_select(self, eclick, erelease):
        if not self.zoom_active:
            return
        
        # Get the coordinates in display/figure space
        x1, y1 = eclick.xdata, eclick.ydata
        x2, y2 = erelease.xdata, erelease.ydata
        
        # Check if any coordinates are None (happens if click is outside image)
        if any(v is None for v in [x1, y1, x2, y2]):
            self.info_label.setText("Selectie buiten afbeelding. Probeer opnieuw.")
            return
        
        # Convert to integers but preserve fractional values for proper rounding
        x1, y1 = float(x1), float(y1)
        x2, y2 = float(x2), float(y2)
        
        # Save the coordinates as floats for zoom
        self.zoom_coords = (x1, y1, x2, y2)
        
        # Update the image with the zoom
        self.zoom_checkbox.setChecked(False)  # Turn off zoom mode
        self.update_image()
        
        # Update info label with rounded coordinates for display
        self.info_label.setText(f"Zoom gebied: ({int(x1)},{int(y1)}) tot ({int(x2)},{int(y2)})")
        
    def reset_zoom(self):
        self.zoom_coords = None
        self.update_image()
        self.info_label.setText("Zoom gereset")
    
    def export_selection(self):
        """Exporteer het huidige RGB beeld"""
        if self.current_image is None:
            self.show_error("Geen beeld om te exporteren")
            return
        
        # Vraag waar het bestand opgeslagen moet worden
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporteer RGB beeld", "", "JPEG Files (*.jpg);;PNG Files (*.png);;TIFF Files (*.tif);;All Files (*)")
        
        if file_path:
            try:
                # Zorg dat er een extensie is
                if not (file_path.endswith('.jpg') or file_path.endswith('.png') or file_path.endswith('.tif')):
                    file_path += '.jpg'
                
                # Haal dpi waarde op
                dpi = self.dpi_spinbox.value()
                
                # Bereken het aantal pixels nodig voor een goed grote afbeelding
                height, width = self.current_image.shape[:2]
                
                # Maak een nieuwe figuur met de juiste afmetingen om pixelatie te voorkomen
                fig = plt.figure(figsize=(width/dpi, height/dpi), dpi=dpi)
                ax = fig.add_subplot(111)
                ax.imshow(self.current_image, interpolation='bicubic')
                ax.axis('off')
                
                # Verwijder padding/margin rond de afbeelding
                fig.tight_layout(pad=0)
                plt.subplots_adjust(left=0, right=1, top=1, bottom=0)
                
                # Sla de afbeelding op in hoge kwaliteit
                if file_path.endswith('.jpg'):
                    fig.savefig(file_path, dpi=dpi, bbox_inches='tight', pad_inches=0)
                else:  # png of tif
                    fig.savefig(file_path, dpi=dpi, bbox_inches='tight', pad_inches=0)
                
                plt.close(fig)  # Sluit de figuur om geheugen vrij te maken
                
                self.info_label.setText(f"Hoge resolutie RGB beeld ({dpi} DPI) geëxporteerd naar: {file_path}")
            except Exception as e:
                self.show_error(f"Fout bij exporteren: {str(e)}")
                import traceback
                traceback.print_exc()
    def export_hyperspectral_data(self):
        """Exporteer de geselecteerde hyperspectrale data naar een nieuw .npy bestand"""
        if self.reshaped_data is None:
            self.show_error("Geen hyperspectrale data om te exporteren")
            return
        
        # Vraag waar het bestand opgeslagen moet worden
        file_path, _ = QFileDialog.getSaveFileName(self, "Exporteer hyperspectrale data", "", "NumPy Files (*.npy);;All Files (*)")
        
        if file_path:
            try:
                # Zorg dat er een extensie is
                if not file_path.endswith('.npy'):
                    file_path += '.npy'
                    
                # Haal het juiste deel van de data op basis van de zoom coördinaten
                if self.zoom_coords is not None and hasattr(self, 'current_zoom_indices'):
                    # Use the actual indices that were computed in update_image
                    ix1, iy1, ix2, iy2 = self.current_zoom_indices
                    
                    # Extract the correct part of the hyperspectral data
                    # Keep all bands (the third dimension)
                    cropped_data = self.reshaped_data[iy1:iy2+1, ix1:ix2+1, :]
                    
                    # Save the cropped data
                    np.save(file_path, cropped_data)
                    
                    self.info_label.setText(f"Uitgesneden hyperspectrale data ({iy2-iy1+1}×{ix2-ix1+1}×{self.bands_count} banden) geëxporteerd naar: {file_path}")
                else:
                    # If there's no zoom, export the full dataset
                    np.save(file_path, self.reshaped_data)
                    self.info_label.setText(f"Volledige hyperspectrale data ({self.height}×{self.width}×{self.bands_count} banden) geëxporteerd naar: {file_path}")
                    
            except Exception as e:
                self.show_error(f"Fout bij exporteren: {str(e)}")
                import traceback
                traceback.print_exc()

    def show_error(self, message):
        """Toon een foutmelding"""
        error_box = QMessageBox()
        error_box.setIcon(QMessageBox.Critical)
        error_box.setText(message)
        error_box.setWindowTitle("Fout")
        error_box.exec_()

# Main functie om de applicatie te starten
def main():
    app = QApplication(sys.argv)
    window = HyperspectralViewer()
    window.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()