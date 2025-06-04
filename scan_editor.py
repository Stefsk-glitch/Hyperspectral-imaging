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
        self.img_height = 1
        self.img_width = 1
        self.display_pixmap = None
        self.top_line = 50
        self.bottom_line = 150
        self.dragging = None
        self.line_margin = 8

        self.x_offset = 0
        self.y_offset = 0
        self.scaled_pixmap_height = 1
        self.scaled_pixmap_width = 1

    def setPixmap(self, pixmap):
        super().setPixmap(pixmap)
        self.display_pixmap = pixmap
        if pixmap:
            self.scaled_pixmap_width = pixmap.width()
            self.scaled_pixmap_height = pixmap.height()
            self.img_width = pixmap.width()
            self.img_height = pixmap.height()
            self.top_line = int(self.img_height * 0.1)
            self.bottom_line = int(self.img_height * 0.9)
            self.update()

    def paintEvent(self, event):
        super().paintEvent(event)
        if self.display_pixmap:
            label_w = self.width()
            label_h = self.height()
            pix_w = self.display_pixmap.width()
            pix_h = self.display_pixmap.height()
            self.x_offset = (label_w - pix_w) // 2
            self.y_offset = (label_h - pix_h) // 2

            painter = QPainter(self)
            painter.fillRect(self.x_offset, self.y_offset, pix_w, self.top_line, Qt.darkGray)
            painter.fillRect(self.x_offset, self.y_offset + self.bottom_line, pix_w, pix_h - self.bottom_line, Qt.darkGray)
            pen = QPen(Qt.gray, 4)
            painter.setPen(pen)
            painter.drawLine(self.x_offset, self.y_offset + self.top_line, self.x_offset + pix_w, self.y_offset + self.top_line)
            painter.drawLine(self.x_offset, self.y_offset + self.bottom_line, self.x_offset + pix_w, self.y_offset + self.bottom_line)

    def mousePressEvent(self, event):
        y = event.y() - self.y_offset
        if 0 <= y <= self.scaled_pixmap_height:
            if abs(y - self.top_line) < self.line_margin:
                self.dragging = 'top'
            elif abs(y - self.bottom_line) < self.line_margin:
                self.dragging = 'bottom'
            else:
                self.dragging = None

    def mouseMoveEvent(self, event):
        if self.dragging:
            y = event.y() - self.y_offset
            y = max(0, min(y, self.scaled_pixmap_height))
            if self.dragging == 'top':
                self.top_line = max(0, min(y, self.bottom_line - 10))
            elif self.dragging == 'bottom':
                self.bottom_line = min(self.scaled_pixmap_height, max(y, self.top_line + 10))
            self.update()

    def mouseReleaseEvent(self, event):
        self.dragging = None

    def get_crop_rect(self):
        return QRect(0, self.top_line, self.img_width, self.bottom_line - self.top_line)


class ScanViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Scan Editor")
        self.resize(900, 800)
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
                print(e)
                self.label.setText(f"Error loading: {e}")

    def crop_and_save(self):
        crop_rect = self.label.get_crop_rect()
        if crop_rect and self.rgb is not None:
            pixmap = self.label.display_pixmap
            if pixmap is None:
                return
            pixmap_size = pixmap.size()
            img_h, img_w, _ = self.rgb.shape
            scale_y = img_h / pixmap_size.height()
            y1 = int(crop_rect.top() * scale_y)
            y2 = int((crop_rect.top() + crop_rect.height()) * scale_y)
            x1 = 0
            x2 = img_w
            y1, y2 = max(0, min(y1, y2)), min(img_h, max(y1, y2))
            if y2 - y1 == 0:
                self.label.setText("Invalid crop region selected.")
                return
            cropped = self.reshaped_data[y1:y2, x1:x2, :]
            if cropped.size == 0:
                self.label.setText("Cropped region is empty.")
                return
            save_path, _ = QFileDialog.getSaveFileName(self, "Save Cropped Scan", "", "NumPy Files (*.npy)")
            if save_path:
                np.save(save_path, cropped)
                self.label.setText(f"Cropped scan saved: {save_path}")


if __name__ == "__main__":
    app = QApplication(sys.argv)
    viewer = ScanViewer()
    viewer.show()
    sys.exit(app.exec_())
