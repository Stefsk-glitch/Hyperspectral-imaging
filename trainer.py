import os
import sys
import logging
import cv2
import numpy as np
import torch
import yaml
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QWidget, QVBoxLayout, 
                            QHBoxLayout, QLabel, QPushButton, QFileDialog, QSpinBox, 
                            QDoubleSpinBox, QLineEdit, QTextEdit, QProgressBar, QCheckBox,
                            QComboBox, QListWidget, QMessageBox, QScrollArea, QGridLayout)
from PyQt5.QtGui import QPixmap, QImage
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QSize

# Detectron2 imports
from detectron2 import model_zoo
from detectron2.engine import DefaultPredictor, DefaultTrainer
from detectron2.config import get_cfg
from detectron2.data import MetadataCatalog, DatasetCatalog
from detectron2.utils.visualizer import Visualizer, ColorMode
from detectron2.data.datasets import register_coco_instances
from detectron2.data import detection_utils as utils
from detectron2.data.transforms import RandomFlip, RandomBrightness, RandomContrast, RandomRotation

# Set up logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("ModelTrainingGUI")

# Default configuration path
DEFAULT_CONFIG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config")
os.makedirs(DEFAULT_CONFIG_DIR, exist_ok=True)

os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

# Define a simple config module if not available
class DefaultConfig:
    TRAIN_DIR = os.path.join(os.getcwd(), "train_data")
    TRAIN_OUTPUT_DIR = os.path.join(os.getcwd(), "model_output")
    detectron_classes = [
        'plant'
    ]

# Try to import the local config, otherwise use default
try:
    import config.config as config
except ImportError:
    logger.warning("Config module not found. Using default configuration.")
    config = DefaultConfig

# Ensure directories exist
os.makedirs(config.TRAIN_DIR, exist_ok=True)
os.makedirs(config.TRAIN_OUTPUT_DIR, exist_ok=True)

class TrainingThread(QThread):
    """Thread for running the model training process"""
    progress_update = pyqtSignal(str)
    finished_signal = pyqtSignal(bool, str)

    def __init__(self, params):
        super().__init__()
        self.params = params

    def run(self):
        try:
            self.progress_update.emit("Preparing training environment...")
            
            # Register the custom dataset
            dataset_name = "my_dataset_train"
            json_path = os.path.join(self.params['train_dir'], 'result.json')
            images_path = self.params['train_dir']
            
            # Check if paths exist
            if not os.path.exists(json_path):
                self.finished_signal.emit(False, f"Training data JSON file {json_path} does not exist.")
                return
                
            if not os.path.exists(images_path):
                self.finished_signal.emit(False, f"Images folder {images_path} does not exist.")
                return
            
            # Check if dataset already registered, if so, re-register it
            if dataset_name in DatasetCatalog.list():
                DatasetCatalog.remove(dataset_name)
                MetadataCatalog.remove(dataset_name)
                
            register_coco_instances(dataset_name, {}, json_path, images_path)
            
            # Set class names
            thing_classes = self.params.get('classes', config.detectron_classes)
            MetadataCatalog.get(dataset_name).thing_classes = thing_classes
            
            self.progress_update.emit(f"Registered dataset with {len(thing_classes)} classes")
                
            # Configure Detectron2
            cfg = get_cfg()
            cfg.OUTPUT_DIR = self.params['output_dir']
            cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
            
            # Set dataset
            cfg.DATASETS.TRAIN = (dataset_name,)
            cfg.DATASETS.TEST = ()
            cfg.DATALOADER.NUM_WORKERS = 4
            
            # Batch settings
            cfg.SOLVER.IMS_PER_BATCH = self.params['batch_size']
            cfg.SOLVER.BASE_LR = self.params['learning_rate']
            cfg.SOLVER.MAX_ITER = self.params['iterations']
            
            # Learning rate schedule
            cfg.SOLVER.WARMUP_ITERS = 1000
            cfg.SOLVER.WARMUP_FACTOR = 0.1
            cfg.SOLVER.STEPS = [int(0.50 * self.params['iterations']), int(0.75 * self.params['iterations'])]
            cfg.SOLVER.GAMMA = 0.2
            cfg.SOLVER.WEIGHT_DECAY = 0.0001
            
            # ROI settings
            cfg.MODEL.ROI_HEADS.BATCH_SIZE_PER_IMAGE = 256
            cfg.MODEL.ROI_HEADS.NUM_CLASSES = len(thing_classes)
            
            # Focal loss parameters
            cfg.MODEL.ROI_HEADS.FOCAL_LOSS_GAMMA = 2.0
            cfg.MODEL.ROI_HEADS.FOCAL_LOSS_ALPHA = 0.25
            
            # Confidence threshold
            cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.3
            
            # Device selection
            use_gpu = self.params.get('use_gpu', True) and torch.cuda.is_available()
            cfg.MODEL.DEVICE = "cuda" if use_gpu else "cpu"
            device_name = "GPU" if use_gpu else "CPU"
            self.progress_update.emit(f"Using {device_name} for training")
            
            # Create output directory if it doesn't exist
            os.makedirs(cfg.OUTPUT_DIR, exist_ok=True)
            
            # Initialize trainer
            trainer = DefaultTrainer(cfg)
            trainer.resume_or_load(resume=False)
            
            self.progress_update.emit("Training started. This may take a while...")
            trainer.train()
            
            # Save the config
            config_yaml_path = os.path.join(cfg.OUTPUT_DIR, "model_config.yaml")
            with open(config_yaml_path, 'w') as file:
                yaml.dump(cfg, file)
            
            self.progress_update.emit(f"Training completed successfully!")
            self.progress_update.emit(f"Model and configuration saved to {cfg.OUTPUT_DIR}")
            self.finished_signal.emit(True, f"Training completed successfully! Model saved to {cfg.OUTPUT_DIR}")
            
        except Exception as e:
            error_msg = f"Training failed: {str(e)}"
            logger.error(error_msg)
            self.finished_signal.emit(False, error_msg)


class PredictionThread(QThread):
    """Thread for running model prediction on images"""
    result_ready = pyqtSignal(np.ndarray, dict)
    error_signal = pyqtSignal(str)
    
    def __init__(self, model_path, image_path, processing_unit="cpu"):
        super().__init__()
        self.model_path = model_path
        self.image_path = image_path
        self.processing_unit = processing_unit
        
    def run(self):
        try:
            # Find the model config file
            model_dir = os.path.dirname(self.model_path)
            config_path = os.path.join(model_dir, "model_config.yaml")
            
            if not os.path.exists(config_path):
                # Try alternate name
                config_path = os.path.join(model_dir, "balise_config.yaml")
                
            if not os.path.exists(config_path):
                self.error_signal.emit(f"Could not find config file in {model_dir}")
                return
                
            # Register dataset if needed to get metadata
            dataset_name = "my_dataset_train"
            if dataset_name not in DatasetCatalog.list():
                # Try to find training data in relative location
                possible_json = os.path.join(os.path.dirname(model_dir), "train_data", "result.json")
                possible_images = os.path.join(os.path.dirname(model_dir), "train_data", "images")
                
                if os.path.exists(possible_json) and os.path.exists(possible_images):
                    register_coco_instances(dataset_name, {}, possible_json, possible_images)
                    MetadataCatalog.get(dataset_name).thing_classes = config.detectron_classes
                else:
                    # Create a dummy registration just to have the class names
                    if dataset_name not in DatasetCatalog.list():
                        DatasetCatalog.register(dataset_name, lambda: [])
                        MetadataCatalog.get(dataset_name).thing_classes = config.detectron_classes
            
            # Set up configuration
            cfg = get_cfg()
            
            # Load from existing config file if possible
            try:
                with open(config_path, 'r') as f:
                    cfg_dict = yaml.safe_load(f)
                    cfg = cfg_dict
            except:
                # Otherwise set up manually
                cfg.merge_from_file(model_zoo.get_config_file("COCO-InstanceSegmentation/mask_rcnn_R_50_FPN_3x.yaml"))
                cfg.MODEL.ROI_HEADS.NUM_CLASSES = len(config.detectron_classes)
            
            # Set model weights
            cfg.MODEL.WEIGHTS = self.model_path
            
            # Set confidence threshold
            cfg.MODEL.ROI_HEADS.SCORE_THRESH_TEST = 0.6
            
            # Set device
            use_gpu = self.processing_unit == "gpu" and torch.cuda.is_available()
            cfg.MODEL.DEVICE = "cuda" if use_gpu else "cpu"
            
            # Create predictor
            predictor = DefaultPredictor(cfg)
            
            # Load and process image
            image = cv2.imread(self.image_path)
            if image is None:
                self.error_signal.emit(f"Could not read image: {self.image_path}")
                return
                
            # Run prediction
            outputs = predictor(image)
            
            # Emit results
            self.result_ready.emit(image, outputs)
            
        except Exception as e:
            error_msg = f"Prediction failed: {str(e)}"
            logger.error(error_msg)
            self.error_signal.emit(error_msg)


class MainWindow(QMainWindow):
    """Main GUI window for training and prediction"""
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Detectron2 Model Training and Prediction GUI")
        self.setMinimumSize(800, 600)
        
        # Initialize UI
        self.init_ui()
        
    def init_ui(self):
        # Create tab widget
        self.tabs = QTabWidget()
        self.setCentralWidget(self.tabs)
        
        # Create tabs
        self.training_tab = QWidget()
        self.prediction_tab = QWidget()
        
        self.tabs.addTab(self.training_tab, "Train Model")
        self.tabs.addTab(self.prediction_tab, "Run Prediction")
        
        # Set up training tab
        self.setup_training_tab()
        
        # Set up prediction tab
        self.setup_prediction_tab()
        
    def setup_training_tab(self):
        """Set up the training tab layout and widgets"""
        layout = QVBoxLayout()
        
        # Training Data Selection
        data_group_layout = QGridLayout()
        
        # Training data directory
        data_group_layout.addWidget(QLabel("Training Data Directory:"), 0, 0)
        self.train_dir_edit = QLineEdit(config.TRAIN_DIR)
        data_group_layout.addWidget(self.train_dir_edit, 0, 1)
        self.train_dir_btn = QPushButton("Browse...")
        self.train_dir_btn.clicked.connect(self.select_train_dir)
        data_group_layout.addWidget(self.train_dir_btn, 0, 2)
        
        # Output directory
        data_group_layout.addWidget(QLabel("Output Directory:"), 1, 0)
        self.output_dir_edit = QLineEdit(config.TRAIN_OUTPUT_DIR)
        data_group_layout.addWidget(self.output_dir_edit, 1, 1)
        self.output_dir_btn = QPushButton("Browse...")
        self.output_dir_btn.clicked.connect(self.select_output_dir)
        data_group_layout.addWidget(self.output_dir_btn, 1, 2)
        
        # Add to layout
        layout.addLayout(data_group_layout)
        
        # Training Parameters
        params_layout = QGridLayout()
        
        # Number of iterations
        params_layout.addWidget(QLabel("Iterations:"), 0, 0)
        self.iterations_spin = QSpinBox()
        self.iterations_spin.setRange(100, 50000)
        self.iterations_spin.setSingleStep(100)
        self.iterations_spin.setValue(9000)
        params_layout.addWidget(self.iterations_spin, 0, 1)
        
        # Batch size
        params_layout.addWidget(QLabel("Batch Size:"), 1, 0)
        self.batch_size_spin = QSpinBox()
        self.batch_size_spin.setRange(1, 8)
        self.batch_size_spin.setValue(3)
        params_layout.addWidget(self.batch_size_spin, 1, 1)
        
        # Learning rate
        params_layout.addWidget(QLabel("Learning Rate:"), 2, 0)
        self.lr_spin = QDoubleSpinBox()
        self.lr_spin.setRange(0.00001, 0.01)
        self.lr_spin.setSingleStep(0.00001)
        self.lr_spin.setDecimals(5)
        self.lr_spin.setValue(0.00025)
        params_layout.addWidget(self.lr_spin, 2, 1)
        
        # Use GPU
        params_layout.addWidget(QLabel("Use GPU:"), 3, 0)
        self.use_gpu_check = QCheckBox("Use GPU if available")
        self.use_gpu_check.setChecked(True)
        params_layout.addWidget(self.use_gpu_check, 3, 1)
        
        # Show if GPU is available
        gpu_available = torch.cuda.is_available()
        gpu_info = f"GPU {'available' if gpu_available else 'not available'}"
        params_layout.addWidget(QLabel(gpu_info), 3, 2)
        
        # Class names
        params_layout.addWidget(QLabel("Classes:"), 4, 0)
        self.classes_edit = QLineEdit()
        self.classes_edit.setText(", ".join(config.detectron_classes))
        params_layout.addWidget(self.classes_edit, 4, 1, 1, 2)
        
        layout.addLayout(params_layout)
        
        # Progress and control
        control_layout = QVBoxLayout()
        
        # Log output
        control_layout.addWidget(QLabel("Training Log:"))
        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        control_layout.addWidget(self.log_text)
        
        # Buttons
        buttons_layout = QHBoxLayout()
        self.start_btn = QPushButton("Start Training")
        self.start_btn.clicked.connect(self.start_training)
        buttons_layout.addWidget(self.start_btn)
        
        self.cancel_btn = QPushButton("Cancel")
        self.cancel_btn.clicked.connect(self.cancel_training)
        self.cancel_btn.setEnabled(False)
        buttons_layout.addWidget(self.cancel_btn)
        
        control_layout.addLayout(buttons_layout)
        
        layout.addLayout(control_layout)
        
        self.training_tab.setLayout(layout)
        
    def setup_prediction_tab(self):
        """Set up the prediction tab layout and widgets"""
        layout = QVBoxLayout()
        
        # Model selection
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("Model File:"))
        self.model_path_edit = QLineEdit()
        default_model = os.path.join(config.TRAIN_OUTPUT_DIR, "model_final.pth")
        if os.path.exists(default_model):
            self.model_path_edit.setText(default_model)
        model_layout.addWidget(self.model_path_edit)
        
        self.model_btn = QPushButton("Browse...")
        self.model_btn.clicked.connect(self.select_model_file)
        model_layout.addWidget(self.model_btn)
        
        layout.addLayout(model_layout)
        
        # Device selection
        device_layout = QHBoxLayout()
        device_layout.addWidget(QLabel("Processing Device:"))
        self.device_combo = QComboBox()
        self.device_combo.addItems(["CPU", "GPU"])
        device_layout.addWidget(self.device_combo)
        
        if not torch.cuda.is_available():
            self.device_combo.setCurrentText("CPU")
            self.device_combo.setEnabled(False)
            device_layout.addWidget(QLabel("(GPU not available)"))
        
        layout.addLayout(device_layout)
        
        # Image selection
        image_layout = QHBoxLayout()
        image_layout.addWidget(QLabel("Image File:"))
        self.image_path_edit = QLineEdit()
        image_layout.addWidget(self.image_path_edit)
        
        self.image_btn = QPushButton("Browse...")
        self.image_btn.clicked.connect(self.select_image_file)
        image_layout.addWidget(self.image_btn)
        
        layout.addLayout(image_layout)
        
        # Run prediction button
        run_layout = QHBoxLayout()
        self.run_btn = QPushButton("Run Prediction")
        self.run_btn.clicked.connect(self.run_prediction)
        run_layout.addWidget(self.run_btn)
        
        layout.addLayout(run_layout)
        
        # Image display
        image_display_layout = QVBoxLayout()
        image_display_layout.addWidget(QLabel("Prediction Results:"))
        
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        
        self.image_label = QLabel("No prediction results yet")
        self.image_label.setAlignment(Qt.AlignCenter)
        
        scroll_area.setWidget(self.image_label)
        image_display_layout.addWidget(scroll_area)
        
        layout.addLayout(image_display_layout)
        
        self.prediction_tab.setLayout(layout)
        
    def select_train_dir(self):
        """Select training data directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Training Data Directory", self.train_dir_edit.text())
        if dir_path:
            self.train_dir_edit.setText(dir_path)
            
    def select_output_dir(self):
        """Select model output directory"""
        dir_path = QFileDialog.getExistingDirectory(self, "Select Output Directory", self.output_dir_edit.text())
        if dir_path:
            self.output_dir_edit.setText(dir_path)
            
    def select_model_file(self):
        """Select model file for prediction"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Model File", self.model_path_edit.text(), "PyTorch Model (*.pth)")
        if file_path:
            self.model_path_edit.setText(file_path)
            
    def select_image_file(self):
        """Select image file for prediction"""
        file_path, _ = QFileDialog.getOpenFileName(self, "Select Image File", self.image_path_edit.text(), "Images (*.jpg *.jpeg *.png)")
        if file_path:
            self.image_path_edit.setText(file_path)
            
    def start_training(self):
        """Start the training process"""
        # Parse class names
        class_names = [name.strip() for name in self.classes_edit.text().split(",")]
        
        # Create parameters dictionary
        params = {
            'train_dir': self.train_dir_edit.text(),
            'output_dir': self.output_dir_edit.text(),
            'iterations': self.iterations_spin.value(),
            'batch_size': self.batch_size_spin.value(),
            'learning_rate': self.lr_spin.value(),
            'use_gpu': self.use_gpu_check.isChecked(),
            'classes': class_names
        }
        
        # Verify training data exists
        json_path = os.path.join(params['train_dir'], 'result.json')
        images_path = os.path.join(params['train_dir'], 'images')
        
        if not os.path.exists(json_path):
            QMessageBox.warning(self, "Warning", f"Training data JSON file not found at:\n{json_path}\n\nPlease ensure your training data follows the structure:\n- train_data/\n  - images/\n  - result.json")
            return
            
        if not os.path.exists(images_path):
            QMessageBox.warning(self, "Warning", f"Images folder not found at:\n{images_path}\n\nPlease ensure your training data follows the structure:\n- train_data/\n  - images/\n  - result.json")
            return
        
        # Create output directory if it doesn't exist
        os.makedirs(params['output_dir'], exist_ok=True)
        
        # Clear log
        self.log_text.clear()
        self.log("Starting training with the following parameters:")
        self.log(f"Training data: {params['train_dir']}")
        self.log(f"Output directory: {params['output_dir']}")
        self.log(f"Iterations: {params['iterations']}")
        self.log(f"Batch size: {params['batch_size']}")
        self.log(f"Learning rate: {params['learning_rate']}")
        self.log(f"Use GPU: {params['use_gpu']}")
        self.log(f"Classes: {', '.join(params['classes'])}")
        
        # Create and start training thread
        self.training_thread = TrainingThread(params)
        self.training_thread.progress_update.connect(self.log)
        self.training_thread.finished_signal.connect(self.training_finished)
        self.training_thread.start()
        
        # Update UI
        self.start_btn.setEnabled(False)
        self.cancel_btn.setEnabled(True)
        
    def cancel_training(self):
        """Cancel the training process"""
        if hasattr(self, 'training_thread') and self.training_thread.isRunning():
            self.training_thread.terminate()
            self.log("Training cancelled by user")
            
            # Update UI
            self.start_btn.setEnabled(True)
            self.cancel_btn.setEnabled(False)
            
    def training_finished(self, success, message):
        """Handle training completion"""
        if success:
            self.log(message)
            QMessageBox.information(self, "Training Complete", message)
        else:
            self.log(f"ERROR: {message}")
            QMessageBox.warning(self, "Training Failed", message)
            
        # Update UI
        self.start_btn.setEnabled(True)
        self.cancel_btn.setEnabled(False)
        
        # Update model path in prediction tab
        if success:
            model_path = os.path.join(self.output_dir_edit.text(), "model_final.pth")
            if os.path.exists(model_path):
                self.model_path_edit.setText(model_path)
                
    def run_prediction(self):
        """Run prediction on selected image"""
        model_path = self.model_path_edit.text()
        image_path = self.image_path_edit.text()
        
        # Validate inputs
        if not model_path or not os.path.exists(model_path):
            QMessageBox.warning(self, "Error", "Please select a valid model file")
            return
            
        if not image_path or not os.path.exists(image_path):
            QMessageBox.warning(self, "Error", "Please select a valid image file")
            return
            
        # Get processing device
        device = "gpu" if self.device_combo.currentText() == "GPU" else "cpu"
        
        # Create and start prediction thread
        self.prediction_thread = PredictionThread(model_path, image_path, device)
        self.prediction_thread.result_ready.connect(self.display_prediction)
        self.prediction_thread.error_signal.connect(self.prediction_error)
        self.prediction_thread.start()
        
        # Update UI
        self.run_btn.setEnabled(False)
        self.image_label.setText("Running prediction...")
        
    def display_prediction(self, image, outputs):
        """Display prediction results"""
        # Create visualization
        dataset_name = "my_dataset_train"
        if dataset_name in MetadataCatalog.list():
            metadata = MetadataCatalog.get(dataset_name)
        else:
            # Create temporary metadata if needed
            metadata = MetadataCatalog.get(dataset_name)
            if not hasattr(metadata, "thing_classes"):
                metadata.thing_classes = config.detectron_classes
                
        # Create visualization
        v = Visualizer(
            image[:, :, ::-1],
            metadata=metadata,
            scale=1.2,
            instance_mode=ColorMode.IMAGE
        )
        vis_output = v.draw_instance_predictions(outputs["instances"].to("cpu"))
        vis_image = vis_output.get_image()[:, :, ::-1]
        
        # Convert to QImage and display
        h, w, c = vis_image.shape
        bytes_per_line = 3 * w
        q_img = QImage(vis_image.tobytes(), w, h, bytes_per_line, QImage.Format_RGB888)
        pixmap = QPixmap.fromImage(q_img)
        
        # Scale if needed
        max_width = self.width() - 40
        if pixmap.width() > max_width:
            pixmap = pixmap.scaledToWidth(max_width)
            
        self.image_label.setPixmap(pixmap)
        
        # Display detection info
        num_detections = len(outputs["instances"])
        classes = outputs["instances"].pred_classes.cpu().numpy()
        scores = outputs["instances"].scores.cpu().numpy()
        
        class_info = {}
        for i, class_id in enumerate(classes):
            class_name = metadata.thing_classes[class_id]
            score = scores[i]
            
            if class_name in class_info:
                class_info[class_name].append(score)
            else:
                class_info[class_name] = [score]
                
        # Create summary text
        info_text = f"Detected {num_detections} objects:\n"
        for class_name, scores in class_info.items():
            avg_score = sum(scores) / len(scores)
            info_text += f"- {class_name}: {len(scores)} instances (avg conf: {avg_score:.2f})\n"
            
        QMessageBox.information(self, "Detection Results", info_text)
        
        # Re-enable run button
        self.run_btn.setEnabled(True)
        
    def prediction_error(self, error_msg):
        """Handle prediction errors"""
        QMessageBox.warning(self, "Prediction Failed", error_msg)
        self.image_label.setText("Prediction failed")
        self.run_btn.setEnabled(True)
        
    def log(self, message):
        """Add message to log text area"""
        self.log_text.append(message)
        # Scroll to the bottom
        cursor = self.log_text.textCursor()
        cursor.movePosition(cursor.End)
        self.log_text.setTextCursor(cursor)
        

if __name__ == "__main__":
    # Enable high DPI support
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
        
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())