"""
Left Panel - Album art and metadata editing
"""
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QComboBox
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QPixmap

class LeftPanel(QWidget):
    """Left panel with album art and metadata fields"""   

    # Signals
    change_cover_clicked = Signal()
    crop_cover_clicked = Signal()
    cleanup_clicked = Signal()
    clean_filename_clicked = Signal()
    field_changed = Signal(str, str)  # field_name, new_value
    
    def __init__(self, album_size=400):
        super().__init__()
        self.album_size = album_size
        self._current_file_path = None
        self._setup_ui()
        self._connect_field_signals()
    
    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(4)
        
        self._setup_album_art(layout)
        self._setup_metadata_fields(layout)
        self._setup_action_buttons(layout)
    
    def _setup_album_art(self, layout):
        """Setup album art section"""
        self.cover_label = QLabel("No Album Art")
        self.cover_label.setObjectName("albumCover")
        self.cover_label.setFixedSize(400, 400)
        self.cover_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.cover_label)
        
        # Album art buttons
        btn_row = QHBoxLayout()
        self.change_cover_btn = QPushButton("📁 Change Cover")
        self.change_cover_btn.clicked.connect(self.change_cover_clicked.emit)
        self.crop_cover_btn = QPushButton("✂️ Crop Cover")
        self.crop_cover_btn.clicked.connect(self.crop_cover_clicked.emit)
        btn_row.addWidget(self.change_cover_btn)
        btn_row.addWidget(self.crop_cover_btn)
        layout.addLayout(btn_row)
    
    def _setup_metadata_fields(self, layout):
        """Setup metadata input fields"""
        # Title, Artist, Album
        self.title_input = self._add_field(layout, "Title:", QLineEdit(), "Title")
        self.artist_input = self._add_field(layout, "Artist:", QLineEdit(), "Artist")
        self.album_input = self._add_field(layout, "Album:", QLineEdit(), "Album")
        
        # Year, Track, Genre row
        row = QHBoxLayout()
        self.year_input = self._add_inline_field(row, "Year:", QLineEdit(), "2025")
        self.track_input = self._add_inline_field(row, "Track:", QLineEdit(), "1")
        self.genre_input = self._add_genre_field(row, "Genre:")
        layout.addLayout(row)
        
        # Other fields
        self.comment_input = self._add_field(layout, "Comment:", QLineEdit(), "Add a comment...")
        self.album_artist_input = self._add_field(layout, "Album Artist:", QLineEdit(), "Album Artist")
        self.composer_input = self._add_field(layout, "Composer / Featured:", QLineEdit(), "Composer or featured")
        self.discnumber_input = self._add_field(layout, "Disc Number:", QLineEdit(), "1")
    
    def _setup_action_buttons(self, layout):
        """Setup action buttons"""
        layout.addSpacing(10)
        
        # Cleanup buttons row
        cleanup_row = QHBoxLayout()
        
        self.cleanup_btn = QPushButton("🧹 Clean Metadata")
        self.cleanup_btn.setObjectName("cleanupButton")
        self.cleanup_btn.clicked.connect(self.cleanup_clicked.emit)
        self.cleanup_btn.setEnabled(False)
        
        self.clean_filename_btn = QPushButton("📝 Clean Filenames")
        self.clean_filename_btn.setObjectName("cleanFilenameButton")
        self.clean_filename_btn.clicked.connect(self.clean_filename_clicked.emit)
        self.clean_filename_btn.setEnabled(False)
        
        cleanup_row.addWidget(self.cleanup_btn)
        cleanup_row.addWidget(self.clean_filename_btn)
        layout.addLayout(cleanup_row)
        
        layout.addStretch()
    
    def _add_field(self, layout, label_text, widget, placeholder=""):
        """Helper to add labeled field"""
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        if placeholder and hasattr(widget, 'setPlaceholderText'):
            widget.setPlaceholderText(placeholder)
        layout.addWidget(label)
        layout.addWidget(widget)
        return widget
    
    def _add_inline_field(self, layout, label_text, widget, placeholder=""):
        """Helper to add inline field"""
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        if placeholder and hasattr(widget, 'setPlaceholderText'):
            widget.setPlaceholderText(placeholder)
        col.addWidget(label)
        col.addWidget(widget)
        layout.addLayout(col)
        return widget
    
    def _add_genre_field(self, layout, label_text):
        """Helper to add genre combo box"""
        from PySide6.QtWidgets import QComboBox
        
        self.genre_input = QComboBox()
        self.genre_input.setEditable(True)
        self.genre_input.setInsertPolicy(QComboBox.NoInsert)
        self.genre_input.lineEdit().setPlaceholderText("Genre")
        
        # Use the GenreManager to populate the combo box
        from ui.genre_manager import GenreManager
        GenreManager.populate_combobox(self.genre_input)
        
        col = QVBoxLayout()
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        col.addWidget(label)
        col.addWidget(self.genre_input, stretch=1)
        layout.addLayout(col, stretch=1)
        return self.genre_input
    
    def _connect_field_signals(self):
        """Connect signals for auto-save on field changes"""
        # Connect editingFinished for QLineEdit fields
        line_edits = [
            (self.title_input, 'title'),
            (self.artist_input, 'artist'),
            (self.album_input, 'album'),
            (self.album_artist_input, 'album_artist'),
            (self.track_input, 'track'),
            (self.discnumber_input, 'disc'),
            (self.year_input, 'year'),
            (self.comment_input, 'comment'),
            (self.composer_input, 'composer')
        ]
        
        for widget, field_name in line_edits:
            widget.editingFinished.connect(
                lambda w=widget, f=field_name: self._on_field_edited(f, w.text())
            )
        
        # Connect currentTextChanged for genre combo box
        self.genre_input.currentTextChanged.connect(
            lambda text: self._on_field_edited('genre', text)
        )
    
    def _on_field_edited(self, field_name, new_value):
        """Handle field edits and emit change signal"""
        new_value = new_value.strip()
        print(f"Left panel field edited: {field_name} = '{new_value}'")
        self.field_changed.emit(field_name, new_value)
    
    def set_current_file(self, file_path):
        """Set the current file being edited"""
        self._current_file_path = file_path
    
    def get_metadata(self):
        """Get all metadata from UI fields"""
        return {
            'title': self.title_input.text().strip(),
            'artist': self.artist_input.text().strip(),
            'album': self.album_input.text().strip(),
            'album_artist': self.album_artist_input.text().strip(),
            'track': self.track_input.text().strip(),
            'disc': self.discnumber_input.text().strip(),
            'year': self.year_input.text().strip(),
            'genre': self.genre_input.currentText().strip(),
            'comment': self.comment_input.text().strip(),
            'composer': self.composer_input.text().strip()
        }
    
    def set_metadata(self, metadata):
        """Set metadata fields"""
        self.title_input.setText(metadata.get('title', ''))
        self.artist_input.setText(metadata.get('artist', ''))
        self.album_input.setText(metadata.get('album', ''))
        self.album_artist_input.setText(metadata.get('album_artist', ''))
        self.track_input.setText(metadata.get('track', ''))
        self.discnumber_input.setText(metadata.get('disc', ''))
        self.year_input.setText(metadata.get('year', ''))
        self.genre_input.setCurrentText(metadata.get('genre', ''))
        self.comment_input.setText(metadata.get('comment', ''))
        self.composer_input.setText(metadata.get('composer', ''))
    
    def set_field(self, field_name, value):
        """Set a specific field by name"""
        field_map = {
            'title': self.title_input,
            'artist': self.artist_input,
            'album': self.album_input,
            'album_artist': self.album_artist_input,
            'track': self.track_input,
            'disc': self.discnumber_input,
            'year': self.year_input,
            'genre': self.genre_input,
            'comment': self.comment_input,
            'composer': self.composer_input
        }
        
        widget = field_map.get(field_name)
        if widget:
            if isinstance(widget, QLineEdit):
                widget.setText(value)
            elif isinstance(widget, QComboBox):
                widget.setCurrentText(value)
    
    def clear_metadata(self):
        """Clear all metadata fields"""
        self.title_input.clear()
        self.artist_input.clear()
        self.album_input.clear()
        self.album_artist_input.clear()
        self.track_input.clear()
        self.discnumber_input.clear()
        self.year_input.clear()
        self.genre_input.setCurrentText("")
        self.comment_input.clear()
        self.composer_input.clear()
    
    def set_cover_pixmap(self, pixmap):
        """Set album art pixmap"""
        self.cover_label.setPixmap(pixmap)
        self.cover_label.setText("")
    
    def set_cover_text(self, text):
        """Set album art text"""
        self.cover_label.setText(text)
        self.cover_label.setPixmap(QPixmap())
    
    def set_cover_tooltip(self, text):
        """Set tooltip for cover label"""
        self.cover_label.setToolTip(text)
    
    def enable_buttons(self, cleanup_enabled, clean_filename_enabled):
        """Enable/disable action buttons"""
        self.cleanup_btn.setEnabled(cleanup_enabled)
        self.clean_filename_btn.setEnabled(clean_filename_enabled)