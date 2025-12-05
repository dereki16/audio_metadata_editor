"""
Album Cover Editor - Modern crop tool with drag & resize
"""
from io import BytesIO
from PySide6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QApplication
from PySide6.QtGui import QPixmap, QMouseEvent, QCursor, QPainter, QPen, QColor
from PySide6.QtCore import Qt, Signal, QPoint, QRect
from PIL import Image
from PIL.ImageQt import ImageQt


class AlbumCoverEditor(QWidget):
    """Interactive album cover crop editor with modern UI"""
    
    finished_signal = Signal()
    
    def __init__(self, image_bytes, parent=None):
        super().__init__(parent)
        
        self.setWindowTitle("Crop Album Cover")
        self.setWindowFlags(Qt.Window | Qt.WindowCloseButtonHint)
        
        # Load image
        self.original_image = Image.open(BytesIO(image_bytes)).convert("RGB")
        self.result_bytes = None
        
        # Fixed compact window size - optimized to fit everything
        self.setFixedSize(800, 650)
        
        # Center window
        self._center_window()
        
        # Apply styles
        self.setStyleSheet("""
            QWidget {
                background: #1a1a1a;
                color: #ffffff;
                font-family: 'Segoe UI', Arial, sans-serif;
            }
            QPushButton {
                background: #2d2d2d;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 6px 12px;
                min-width: 40px;
                font-size: 12px;
            }
            QPushButton:hover {
                background: #3d3d3d;
                border: 1px solid #666;
            }
            QPushButton:pressed {
                background: #1d1d1d;
            }
            QPushButton#saveButton {
                background: #0d7377;
                border: 1px solid #0a5c5f;
            }
            QPushButton#saveButton:hover {
                background: #0e8a8f;
            }
            QPushButton#cancelButton {
                background: #8b3a3a;
                border: 1px solid #702e2e;
            }
            QPushButton#cancelButton:hover {
                background: #a04545;
            }
            QLabel {
                color: #cccccc;
            }
        """)
        
        # Crop state
        self.crop_x = 0
        self.crop_y = 0
        self.crop_size = min(self.original_image.width, self.original_image.height) // 2
        
        # Mouse state
        self.dragging = False
        self.resizing = None
        self.drag_start = QPoint()
        self.drag_offset = QPoint()
        self.resize_start_size = 0
        self.resize_start_crop = QPoint()
        
        # Handle size for corners
        self.handle_size = 25
        
        self._setup_ui()
        self._center_crop()
        self.update_preview()
    
    def _center_window(self):
        """Center the window on screen"""
        screen = QApplication.primaryScreen().geometry()
        if self.parent():
            parent_geo = self.parent().geometry()
            x = parent_geo.x() + (parent_geo.width() - 800) // 2
            y = parent_geo.y() + (parent_geo.height() - 650) // 2
        else:
            x = (screen.width() - 800) // 2
            y = (screen.height() - 650) // 2
        self.move(x, y)
    
    def _setup_ui(self):
        """Setup compact UI layout"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        
        # Title with size info
        header = QHBoxLayout()
        title = QLabel("Crop Album Cover")
        title.setStyleSheet("font-size: 14px; font-weight: bold; color: #ffffff;")
        header.addWidget(title)
        
        header.addStretch()
        
        self.size_label = QLabel(f"{self.crop_size}px")
        self.size_label.setStyleSheet("font-size: 12px; color: #00C8FF; font-weight: bold;")
        header.addWidget(self.size_label)
        
        layout.addLayout(header)
        
        # Canvas - fixed size to fit in window
        self.canvas = CropCanvas(self)
        self.canvas.setFixedSize(760, 400)  # Reduced height to fit buttons
        self.canvas.setStyleSheet("""
            background: #0a0a0a;
            border: 2px solid #333;
            border-radius: 4px;
        """)
        layout.addWidget(self.canvas, alignment=Qt.AlignCenter)
        
        # Compact controls
        self._setup_controls(layout)
    
    def _setup_controls(self, layout):
        """Setup compact control buttons"""
        # Size controls row
        size_controls = QHBoxLayout()
        size_controls.addStretch()
        
        size_controls.addWidget(QLabel("Size:"))
        
        # Compact size buttons
        size_buttons = [
            ("−−", -50, 35, 25),
            ("−", -10, 30, 25),
            ("+", 10, 30, 25),
            ("++", 50, 35, 25)
        ]
        
        for text, delta, width, height in size_buttons:
            btn = QPushButton(text)
            btn.setFixedSize(width, height)
            btn.clicked.connect(lambda checked=False, d=delta: self.adjust_size(d))
            size_controls.addWidget(btn)
        
        size_controls.addStretch()
        layout.addLayout(size_controls)
        
        # Action buttons row - centered and compact
        action_controls = QHBoxLayout()
        action_controls.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.setObjectName("cancelButton")
        cancel_btn.setFixedSize(80, 32)
        cancel_btn.clicked.connect(self.close)
        action_controls.addWidget(cancel_btn)
        
        save_btn = QPushButton("Save Crop")
        save_btn.setObjectName("saveButton")
        save_btn.setFixedSize(90, 32)
        save_btn.clicked.connect(self.save_crop)
        action_controls.addWidget(save_btn)
        
        action_controls.addStretch()
        layout.addLayout(action_controls)
    
    def _center_crop(self):
        """Center the crop box on the image"""
        self.crop_x = (self.original_image.width - self.crop_size) // 2
        self.crop_y = (self.original_image.height - self.crop_size) // 2
        self._clamp_crop()
    
    def _clamp_crop(self):
        """Ensure crop stays within image bounds"""
        # Clamp size
        max_size = min(self.original_image.width, self.original_image.height)
        self.crop_size = max(50, min(self.crop_size, max_size))
        
        # Clamp position
        self.crop_x = max(0, min(self.crop_x, self.original_image.width - self.crop_size))
        self.crop_y = max(0, min(self.crop_y, self.original_image.height - self.crop_size))
    
    def adjust_size(self, delta):
        """Adjust crop size"""
        old_size = self.crop_size
        self.crop_size += delta
        self._clamp_crop()
        
        # Keep centered when resizing
        size_diff = self.crop_size - old_size
        self.crop_x -= size_diff // 2
        self.crop_y -= size_diff // 2
        self._clamp_crop()
        
        self.size_label.setText(f"{self.crop_size}px")
        self.update_preview()
    
    def update_preview(self):
        """Update canvas display"""
        self.canvas.update()
    
    def get_scaled_image_size(self):
        """Get current image dimensions"""
        return (self.original_image.width, self.original_image.height)
    
    def save_crop(self):
        """Save cropped image"""
        # Crop directly from original image
        cropped = self.original_image.crop((
            self.crop_x,
            self.crop_y,
            self.crop_x + self.crop_size,
            self.crop_y + self.crop_size
        ))
        
        # Save to bytes
        buffer = BytesIO()
        cropped.save(buffer, format="JPEG", quality=95)
        self.result_bytes = buffer.getvalue()
        
        self.finished_signal.emit()
        self.close()
    
    def closeEvent(self, event):
        """Handle window close"""
        self.finished_signal.emit()
        super().closeEvent(event)


class CropCanvas(QLabel):
    """Custom canvas for rendering crop overlay with mouse interaction"""
    
    def __init__(self, editor):
        super().__init__()
        self.editor = editor
        self.setMouseTracking(True)
        self.setAlignment(Qt.AlignCenter)
    
    def paintEvent(self, event):
        """Custom paint with crop overlay"""
        super().paintEvent(event)
        
        if not hasattr(self.editor, 'original_image'):
            return
        
        # Use original image size
        img_w, img_h = self.editor.get_scaled_image_size()
        
        # Convert to QPixmap
        qimg = ImageQt(self.editor.original_image)
        pixmap = QPixmap.fromImage(qimg)
        
        # Scale to fit canvas
        canvas_w = self.width()
        canvas_h = self.height()
        pixmap = pixmap.scaled(canvas_w, canvas_h, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
        # Calculate display offset
        display_w = pixmap.width()
        display_h = pixmap.height()
        offset_x = (canvas_w - display_w) // 2
        offset_y = (canvas_h - display_h) // 2
        
        # Store scale for mouse mapping
        self.scale_x = display_w / img_w if img_w > 0 else 1
        self.scale_y = display_h / img_h if img_h > 0 else 1
        self.offset_x = offset_x
        self.offset_y = offset_y
        
        # Draw image
        painter = QPainter(self)
        painter.drawPixmap(offset_x, offset_y, pixmap)
        
        # Draw crop overlay
        crop_x = int(self.editor.crop_x * self.scale_x) + offset_x
        crop_y = int(self.editor.crop_y * self.scale_y) + offset_y
        crop_size = int(self.editor.crop_size * min(self.scale_x, self.scale_y))
        
        # Semi-transparent overlay outside crop area
        painter.fillRect(0, 0, canvas_w, canvas_h, QColor(0, 0, 0, 40))
        painter.setCompositionMode(QPainter.CompositionMode_DestinationOver)
        painter.fillRect(crop_x, crop_y, crop_size, crop_size, QColor(255, 255, 255, 0))
        painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
        
        # Crop border
        pen = QPen(QColor(0, 200, 255), 3)
        painter.setPen(pen)
        painter.drawRect(crop_x, crop_y, crop_size, crop_size)
        
        # Inner border
        pen2 = QPen(QColor(255, 255, 255, 180), 1)
        painter.setPen(pen2)
        painter.drawRect(crop_x + 1, crop_y + 1, crop_size - 2, crop_size - 2)
        
        # Corner handles
        handle_size = 20
        handle_color = QColor(0, 200, 255)
        handle_border = QColor(255, 255, 255, 200)
        
        handles = [
            (crop_x, crop_y),  # TL
            (crop_x + crop_size - handle_size, crop_y),  # TR
            (crop_x, crop_y + crop_size - handle_size),  # BL
            (crop_x + crop_size - handle_size, crop_y + crop_size - handle_size)  # BR
        ]
        
        for hx, hy in handles:
            painter.fillRect(hx, hy, handle_size, handle_size, handle_color)
            painter.setPen(QPen(handle_border, 1))
            painter.drawRect(hx, hy, handle_size, handle_size)
        
        painter.end()
    
    def _map_to_image(self, pos):
        """Map canvas position to image coordinates"""
        if not hasattr(self, 'scale_x'):
            return None
        
        x = (pos.x() - self.offset_x) / self.scale_x
        y = (pos.y() - self.offset_y) / self.scale_y
        
        if x < 0 or y < 0:
            return None
        
        return QPoint(int(x), int(y))
    
    def _get_handle_at(self, img_pos):
        """Check if position is on a resize handle"""
        if img_pos is None:
            return None
        
        hs = self.editor.handle_size
        cx = self.editor.crop_x
        cy = self.editor.crop_y
        cs = self.editor.crop_size
        x, y = img_pos.x(), img_pos.y()
        
        # Check each corner
        if cx <= x <= cx + hs and cy <= y <= cy + hs:
            return "tl"
        if cx + cs - hs <= x <= cx + cs and cy <= y <= cy + hs:
            return "tr"
        if cx <= x <= cx + hs and cy + cs - hs <= y <= cy + cs:
            return "bl"
        if cx + cs - hs <= x <= cx + cs and cy + cs - hs <= y <= cy + cs:
            return "br"
        
        return None
    
    def _is_inside_crop(self, img_pos):
        """Check if position is inside crop area"""
        if img_pos is None:
            return False
        
        x, y = img_pos.x(), img_pos.y()
        return (self.editor.crop_x <= x <= self.editor.crop_x + self.editor.crop_size and
                self.editor.crop_y <= y <= self.editor.crop_y + self.editor.crop_size)
    
    def mousePressEvent(self, event):
        """Handle mouse press"""
        img_pos = self._map_to_image(event.pos())
        
        # Check for handle click
        handle = self._get_handle_at(img_pos)
        if handle:
            self.editor.resizing = handle
            self.editor.drag_start = img_pos
            self.editor.resize_start_size = self.editor.crop_size
            self.editor.resize_start_crop = QPoint(self.editor.crop_x, self.editor.crop_y)
            return
        
        # Check for drag click
        if self._is_inside_crop(img_pos):
            self.editor.dragging = True
            self.editor.drag_offset = QPoint(
                img_pos.x() - self.editor.crop_x,
                img_pos.y() - self.editor.crop_y
            )
    
    def mouseMoveEvent(self, event):
        """Handle mouse move"""
        img_pos = self._map_to_image(event.pos())
        
        # Update cursor
        if self._get_handle_at(img_pos):
            self.setCursor(Qt.SizeFDiagCursor)
        elif self._is_inside_crop(img_pos):
            self.setCursor(Qt.SizeAllCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        
        # Handle dragging
        if self.editor.dragging and img_pos:
            self.editor.crop_x = img_pos.x() - self.editor.drag_offset.x()
            self.editor.crop_y = img_pos.y() - self.editor.drag_offset.y()
            self.editor._clamp_crop()
            self.update()
        
        # Handle resizing
        elif self.editor.resizing and img_pos:
            dx = img_pos.x() - self.editor.drag_start.x()
            dy = img_pos.y() - self.editor.drag_start.y()
            
            if self.editor.resizing == "tl":
                delta = max(dx, dy)
                self.editor.crop_size = max(50, self.editor.resize_start_size - delta)
                self.editor.crop_x = self.editor.resize_start_crop.x() + (self.editor.resize_start_size - self.editor.crop_size)
                self.editor.crop_y = self.editor.resize_start_crop.y() + (self.editor.resize_start_size - self.editor.crop_size)
            elif self.editor.resizing == "tr":
                delta = max(-dx, dy)
                self.editor.crop_size = max(50, self.editor.resize_start_size - delta)
                self.editor.crop_y = self.editor.resize_start_crop.y() + (self.editor.resize_start_size - self.editor.crop_size)
            elif self.editor.resizing == "bl":
                delta = max(dx, -dy)
                self.editor.crop_size = max(50, self.editor.resize_start_size - delta)
                self.editor.crop_x = self.editor.resize_start_crop.x() + (self.editor.resize_start_size - self.editor.crop_size)
            elif self.editor.resizing == "br":
                delta = max(dx, dy)
                self.editor.crop_size = max(50, self.editor.resize_start_size + delta)
            
            self.editor._clamp_crop()
            self.editor.size_label.setText(f"{self.editor.crop_size}px")
            self.update()
    
    def mouseReleaseEvent(self, event):
        """Handle mouse release"""
        self.editor.dragging = False
        self.editor.resizing = None
        self.setCursor(Qt.ArrowCursor)