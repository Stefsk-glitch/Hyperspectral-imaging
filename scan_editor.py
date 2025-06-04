import sys
import numpy as np
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QLabel, QPushButton,
    QFileDialog, QVBoxLayout, QWidget
)
from PyQt5.QtGui import QImage, QPixmap, QPainter, QPen
from PyQt5.QtCore import Qt, QRect

class CropLabel(QLabel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.start_point = None
        self.end_point = None
        self.rect = None
        self.drawing = False
        self.display_pixmap = None

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self.display_pixmap = pixmap

    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self.start_point = event.pos()
            self.end_point = event.pos()
            self.drawing = True
            self.update()

    def mouseMoveEvent(self, event):
        if self.drawing:
            self.end_point = event.pos()
            self.update()

    def mouseReleaseEvent(self, event):
        if event.button() == Qt.LeftButton and self.drawing:
            self.end_point = event.pos()
            self.drawing = False
            self.rect = QRect(self.start_point, self.end_point).normalized()
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.start_point and self.end_point:
            painter = QPainter(self)
            painter.setPen(QPen(Qt.red, 2, Qt.DashLine))
            rect = QRect(self.start_point, self.end_point).normalized()
            painter.drawRect(rect)

    def get_crop_rect(self):
        if self.rect:
            return self.rect
        return None

class ScanViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scan Editor")
        self.resize(900, 700)
        self.reshaped_data = None
        self.rgb = None

        self.label = CropLabel(self)
        self.label.setAlignment(Qt.AlignCenter)
        self.button = QPushButton("Open .npy file", self)
        self.button.clicked.connect(self.load_file)
        self.crop_button = QPushButton("Crop and Save", self)
        self.crop_button.clicked.connect(self.crop_and_save)
        self.crop_button.setEnabled(False)

        layout = QVBoxLayout()
        layout.addWidget(self.label)
        layout.addWidget(self.button)
        layout.addWidget(self.crop_button)

        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

    def load_file(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "Open .npy file", "", "NumPy Files (*.npy)")
        if file_path:
            try:
                data = np.load(file_path)
                if len(data.shape) == 3:
                    dim1, dim2, dim3 = data.shape
                    if dim1 < 500 and dim2 < 500 and dim3 > 100:
                        reshaped = data
                    elif 200 <= dim2 <= 250:
                        reshaped = np.transpose(data, (0, 2, 1))
                    elif 200 <= dim1 <= 250:
                        reshaped = np.transpose(data, (1, 2, 0))
                    elif 200 <= dim3 <= 250:
                        reshaped = data
                    else:
                        reshaped = data
                else:
                    self.label.setText("Unexpected shape: {}".format(data.shape))
                    return

                self.reshaped_data = reshaped
                bands = reshaped.shape[2]
                r = reshaped[:, :, min(120, bands-1)]
                g = reshaped[:, :, min(70, bands-1)]
                b = reshaped[:, :, min(40, bands-1)]

                def normalize(band):
                    min_val = np.percentile(band, 2)
                    max_val = np.percentile(band, 98)
                    if max_val > min_val:
                        norm = np.clip((band - min_val) / (max_val - min_val), 0, 1)
                        return (norm * 255).astype(np.uint8)
                    return np.zeros_like(band, dtype=np.uint8)

                rgb = np.dstack([normalize(r), normalize(g), normalize(b)])
                self.rgb = rgb

                h, w, _ = rgb.shape
                qimg = QImage(rgb.data, w, h, 3 * w, QImage.Format_RGB888)
                pixmap = QPixmap.fromImage(qimg).scaled(800, 600, aspectRatioMode=Qt.KeepAspectRatio)
                self.label.setPixmap(pixmap)
                self.crop_button.setEnabled(True)
            except Exception as e:
                self.label.setText(f"Fout bij laden: {e}")

    def crop_and_save(self):
        crop_rect = self.label.get_crop_rect()
        if crop_rect and self.rgb is not None:
            # Map crop_rect from displayed pixmap to original image coordinates
            pixmap = self.label.display_pixmap
            if pixmap is None:
                return
            pixmap_size = pixmap.size()
            img_h, img_w, _ = self.rgb.shape
            scale_x = img_w / pixmap_size.width()
            scale_y = img_h / pixmap_size.height()
            x1 = int(crop_rect.left() * scale_x)
            y1 = int(crop_rect.top() * scale_y)
            x2 = int(crop_rect.right() * scale_x)
            y2 = int(crop_rect.bottom() * scale_y)
            # Ensure bounds
            x1, x2 = max(0, min(x1, x2)), min(img_w, max(x1, x2))
            y1, y2 = max(0, min(y1, y2)), min(img_h, max(y1, y2))
            cropped = self.reshaped_data[y1:y2, x1:x2, :]
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Cropped Scan", "", "NumPy Files (*.npy)")
            if save_path:
                np.save(save_path, cropped)
                self.label.setText(f"Cropped scan saved: {save_path}")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ScanViewer()
    viewer.show()
    sys.exit(app.exec_())
