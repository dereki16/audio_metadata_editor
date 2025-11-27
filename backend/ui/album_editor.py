from io import BytesIO
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, Signal
from PIL import Image, ImageDraw
from PIL.ImageQt import ImageQt

# ============================================================
#                   ALBUM COVER EDITOR DIALOG
# ============================================================
class AlbumCoverEditor(QWidget):
    finished_signal = Signal()
    
    def __init__(self, image_bytes, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Crop Album Cover")
        self.setGeometry(200, 200, 800, 600)
        
        self.original_image = Image.open(BytesIO(image_bytes))
        self.crop_size = 500
        self.crop_x = 0
        self.crop_y = 0
        self.zoom = 1.0
        self.result_bytes = None
        
        layout = QVBoxLayout(self)
        
        # Canvas for image display
        self.canvas = QLabel()
        self.canvas.setAlignment(Qt.AlignCenter)
        self.canvas.setMinimumSize(600, 600)
        self.canvas.setStyleSheet("border: 2px solid #555; background: #222;")
        layout.addWidget(self.canvas)
        
        # Controls
        controls = QHBoxLayout()
        
        # Zoom controls
        controls.addWidget(QLabel("Zoom:"))
        zoom_out = QPushButton("-")
        zoom_out.clicked.connect(lambda: self.adjust_zoom(-0.1))
        controls.addWidget(zoom_out)
        
        self.zoom_label = QLabel("1.0x")
        controls.addWidget(self.zoom_label)
        
        zoom_in = QPushButton("+")
        zoom_in.clicked.connect(lambda: self.adjust_zoom(0.1))
        controls.addWidget(zoom_in)
        
        controls.addStretch()
        
        # Position controls
        controls.addWidget(QLabel("Position:"))
        up_btn = QPushButton("↑")
        up_btn.clicked.connect(lambda: self.move_crop(0, -20))
        controls.addWidget(up_btn)
        
        down_btn = QPushButton("↓")
        down_btn.clicked.connect(lambda: self.move_crop(0, 20))
        controls.addWidget(down_btn)
        
        left_btn = QPushButton("←")
        left_btn.clicked.connect(lambda: self.move_crop(-20, 0))
        controls.addWidget(left_btn)
        
        right_btn = QPushButton("→")
        right_btn.clicked.connect(lambda: self.move_crop(20, 0))
        controls.addWidget(right_btn)
        
        controls.addStretch()
        
        # Save/Cancel
        save_btn = QPushButton("Save Crop")
        save_btn.clicked.connect(self.save_crop)
        controls.addWidget(save_btn)
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.close)
        controls.addWidget(cancel_btn)
        
        layout.addLayout(controls)
        
        self.update_preview()
    
    def adjust_zoom(self, delta):
        self.zoom = max(0.5, min(3.0, self.zoom + delta))
        self.zoom_label.setText(f"{self.zoom:.1f}x")
        self.update_preview()
    
    def move_crop(self, dx, dy):
        self.crop_x += dx
        self.crop_y += dy
        self.update_preview()
    
    def update_preview(self):
        # Calculate scaled dimensions
        scaled_w = int(self.original_image.width * self.zoom)
        scaled_h = int(self.original_image.height * self.zoom)
        
        # Resize image
        scaled_img = self.original_image.resize((scaled_w, scaled_h), Image.LANCZOS)
        
        # Clamp crop position
        max_x = max(0, scaled_w - self.crop_size)
        max_y = max(0, scaled_h - self.crop_size)
        self.crop_x = max(0, min(self.crop_x, max_x))
        self.crop_y = max(0, min(self.crop_y, max_y))
        
        # Create a display image showing the crop area
        display_img = scaled_img.copy()
        from PIL import ImageDraw
        draw = ImageDraw.Draw(display_img)
        
        # Draw crop square
        draw.rectangle(
            [self.crop_x, self.crop_y, 
             self.crop_x + self.crop_size, self.crop_y + self.crop_size],
            outline="red", width=3
        )
        
        # Convert to QPixmap
        qimg = ImageQt(display_img)
        pixmap = QPixmap.fromImage(qimg)
        
        # Scale to fit canvas
        pixmap = pixmap.scaled(self.canvas.size(), Qt.KeepAspectRatio, Qt.SmoothTransformation)
        self.canvas.setPixmap(pixmap)
    
    def save_crop(self):
        # Perform actual crop
        scaled_w = int(self.original_image.width * self.zoom)
        scaled_h = int(self.original_image.height * self.zoom)
        scaled_img = self.original_image.resize((scaled_w, scaled_h), Image.LANCZOS)
        
        cropped = scaled_img.crop((
            self.crop_x, self.crop_y,
            self.crop_x + self.crop_size, self.crop_y + self.crop_size
        ))
        
        # Convert to bytes
        buffer = BytesIO()
        cropped.save(buffer, format="JPEG", quality=95)
        self.result_bytes = buffer.getvalue()
        
        self.finished_signal.emit()
        self.close()
    
    def closeEvent(self, event):
        """Emit signal when window closes."""
        self.finished_signal.emit()
        super().closeEvent(event)
