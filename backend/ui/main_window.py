import sys
import os
import re
from io import BytesIO

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QFileDialog, QMessageBox, QListWidget, QCheckBox, QComboBox
)
from PySide6.QtGui import QPixmap
from PySide6.QtCore import Qt, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput

from mutagen import File as MutagenFile
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.flac import Picture

from PIL import Image
from PIL.ImageQt import ImageQt
from pydub import AudioSegment
import numpy as np
import pyqtgraph as pg

from core import AudioManager
from utils import UNWANTED_PATTERNS
from .album_editor import AlbumCoverEditor

# ============================================================
#                       AUDIO EDITOR UI
# ============================================================
class AudioEditor(QWidget):
    def get_album_size(self):
        return 400
    
    def set_album_size(self, value):
        self.album_size = value
      
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Sound Simulation")
        self.setGeometry(100, 100, 1400, 800)

        # Enable keyboard focus for spacebar control
        self.setFocusPolicy(Qt.StrongFocus)

        # State
        self.file_path = None
        self.audio_files = []
        self.new_cover_bytes = None
        self.audioMgr = AudioManager()
        self.waveform_enabled = False
        self.waveform_smoothing = 10
        self.waveform_amplitude = 1.0

        # Load stylesheet
        self._load_stylesheet()

        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)

        # ==================== LEFT PANEL ====================
        left_panel = QVBoxLayout()
        left_panel.setSpacing(4)

        # Album Art
        self.album_size = self.get_album_size()
        self.set_album_size(self.album_size)

        self.cover_label = QLabel("No Album Art")
        self.cover_label.setObjectName("albumCover")
        self.cover_label.setFixedSize(self.album_size, self.album_size)
        self.cover_label.setAlignment(Qt.AlignCenter)
        left_panel.addWidget(self.cover_label)

        # Album art buttons
        btn_row = QHBoxLayout()
        btn_row.setSpacing(8)
        self.change_cover_btn = QPushButton("📁 Change Cover")
        self.change_cover_btn.clicked.connect(self.change_album_art)
        btn_row.addWidget(self.change_cover_btn)

        self.crop_cover_btn = QPushButton("✂️ Crop Cover")
        self.crop_cover_btn.clicked.connect(self.crop_album_art)
        btn_row.addWidget(self.crop_cover_btn)
        left_panel.addLayout(btn_row)

        # Metadata fields
        self.title_input = QLineEdit()
        self.title_input.setPlaceholderText("Title")
        self._add_field(left_panel, "Title:", self.title_input)

        self.artist_input = QLineEdit()
        self.artist_input.setPlaceholderText("Artist")
        self._add_field(left_panel, "Artist:", self.artist_input)

        self.album_input = QLineEdit()
        self.album_input.setPlaceholderText("Album")
        self._add_field(left_panel, "Album:", self.album_input)

        # Row: Year, Track, Genre
        row = QHBoxLayout()
        row.setSpacing(8)

        # Year
        year_col = QVBoxLayout()
        year_label = QLabel("Year:")
        year_label.setObjectName("fieldLabel")
        self.year_input = QLineEdit()
        self.year_input.setPlaceholderText("2025")
        year_col.addWidget(year_label)
        year_col.addWidget(self.year_input, stretch = 1)
        row.addLayout(year_col)

        # Track
        track_col = QVBoxLayout()
        track_label = QLabel("Track:")
        track_label.setObjectName("fieldLabel")
        self.track_input = QLineEdit()
        self.track_input.setPlaceholderText("1")
        self.track_input.setFixedWidth(70)
        track_col.addWidget(track_label)
        track_col.addWidget(self.track_input)
        row.addLayout(track_col)

        # Genre
        genre_col = QVBoxLayout()
        genre_label = QLabel("Genre:")
        genre_label.setObjectName("fieldLabel")
        self.genre_input = QComboBox()
        self.genre_input.setEditable(True)
        self.genre_input.setInsertPolicy(QComboBox.NoInsert)
        self.genre_input.lineEdit().setPlaceholderText("Genre")
        self.genre_list = [
            "Acid Rock", "Acid Techno", "Acoustic", "Afrobeat", "Alternative", 
            "Alternative Dance", "Alternative Metal", "Alternative R&B", "Alternative Rock", 
            "Ambient", "Americana", "Anime", "Arena Rock", "Art Pop", "Art Rock", 
            "Atmospheric", "Bachata", "Balada", "Baroque Pop", "Bass House", "Bass Music", 
            "Beat Music", "Bedroom Pop", "Big Beat", "Big Room House", "Blackgaze", 
            "Bluegrass", "Blues", "Blues Rock", "Bossa Nova", "Breakbeat", "Britpop", 
            "British Invasion", "Brostep", "Canción", "Cantautor", "Chamber Pop", 
            "Chillhop", "Chillout", "Chillwave", "Classic Rock", "Classical", "Country", 
            "Country Pop", "Cumbia", "Dance", "Dance-Pop", "Dancehall", "Deep House", 
            "Disco", "Downtempo", "Dream Pop", "Drone", "Dub", "Dubstep", "EDM", 
            "Electro", "Electronica", "Electronic", "Emo", "Emo Pop", "Emo Rock", 
            "Experimental", "Flamenco", "Folk", "Folk Rock", "Folktronica", "Freestyle", 
            "Funk", "Future Bass", "Garage Rock", "Glam Punk", "Glitch", "Gospel", 
            "Gothic", "Grunge", "Hard Rock", "Hardcore", "Hardstyle", "Hip-Hop", 
            "House", "Indie", "Indie Folk", "Indie Pop", "Indie Rock", "Indietronica", 
            "Industrial", "Jangle Pop", "Jazz", "Jazz Fusion", "Jazz/Chill Lofi", 
            "K-Pop", "Latin", "Latin Pop", "Latin Rock", "Lo-Fi", "Lo-Fi Hip Hop", 
            "Mariachi", "Math Rock", "Metal", "Microhouse", "Minimal", "Música Popular Brasileira", 
            "New Age", "New Wave", "Noise Rock", "Nu-Disco", "Opera", "Orchestral Pop", 
            "Pop", "Pop Metal", "Pop Rap", "Pop Rock", "Pop-Punk", "Post-Rock", 
            "Post-Punk", "Power Pop", "Progressive", "Progressive House", "Progressive Rock", 
            "Psychedelic", "Psychedelic Pop", "Punk", "Punk Rock", "R&B", "Ranchera", 
            "Rap", "Reggae", "Reggaeton", "Rock", "Rock & Roll", "Rock En Español", 
            "Salsa", "Shoegaze", "Ska", "Soft Rock", "Soul", "Soundtrack", "Spanish Pop", 
            "Synthpop", "Synthwave", "Techno", "Teen Pop", "Trance", "Trap", "Trap Music", 
            "Tropical", "Tropical House", "Vallenato", "Vaporwave", "Vocaloid", "World"
        ]
        self.genre_input.addItems([""] + sorted(self.genre_list))
        genre_col.addWidget(genre_label)
        genre_col.addWidget(self.genre_input, stretch=1)
        row.addLayout(genre_col, stretch=1)

        row.addStretch()
        left_panel.addLayout(row)

        # Other fields
        self.comment_input = QLineEdit()
        self.comment_input.setPlaceholderText("Add a comment...")
        self._add_field(left_panel, "Comment:", self.comment_input)

        self.album_artist_input = QLineEdit()
        self.album_artist_input.setPlaceholderText("Album Artist")
        self._add_field(left_panel, "Album Artist:", self.album_artist_input)

        self.composer_input = QLineEdit()
        self.composer_input.setPlaceholderText("Composer or featured")
        self._add_field(left_panel, "Composer / Featured:", self.composer_input)

        self.discnumber_input = QLineEdit()
        self.discnumber_input.setPlaceholderText("1")
        self._add_field(left_panel, "Disc Number:", self.discnumber_input)

        # Action buttons
        left_panel.addSpacing(10)

        save_row = QHBoxLayout()
        save_row.setSpacing(8)
        self.cleanup_btn = QPushButton("🧹 Auto Clean Titles")
        self.cleanup_btn.setObjectName("cleanupButton")
        self.cleanup_btn.clicked.connect(self.auto_cleanup)
        self.cleanup_btn.setEnabled(False)  # disabled until a folder is loaded
        save_row.addWidget(self.cleanup_btn)


        self.save_btn = QPushButton("💾 Save Metadata")
        self.save_btn.setObjectName("saveButton")
        self.save_btn.clicked.connect(self.save_metadata)
        self.save_btn.setEnabled(False)
        save_row.addWidget(self.save_btn)
        left_panel.addLayout(save_row)
        left_panel.addStretch()

        main_layout.addLayout(left_panel)

        # ==================== RIGHT PANEL ====================
        right_panel = QVBoxLayout()
        right_panel.setSpacing(10)

        # Top controls
        top_controls = QHBoxLayout()
        
        self.load_folder_btn = QPushButton("📂 Load Folder")
        self.load_folder_btn.clicked.connect(self.load_folder)
        top_controls.addWidget(self.load_folder_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh_folder)
        top_controls.addWidget(self.refresh_btn)


        self.waveform_toggle = QCheckBox("Show Waveform")
        self.waveform_toggle.setChecked(False)
        self.waveform_toggle.stateChanged.connect(self.toggle_waveform)
        top_controls.addWidget(self.waveform_toggle)

        top_controls.addWidget(QLabel("Smooth:"))
        self.smooth_input = QLineEdit("10")
        self.smooth_input.setFixedWidth(50)
        self.smooth_input.editingFinished.connect(self.update_waveform_settings)
        top_controls.addWidget(self.smooth_input)

        top_controls.addWidget(QLabel("Height:"))
        self.amplitude_input = QLineEdit("1.0")
        self.amplitude_input.setFixedWidth(50)
        self.amplitude_input.editingFinished.connect(self.update_waveform_settings)
        top_controls.addWidget(self.amplitude_input)

        top_controls.addStretch()
        right_panel.addLayout(top_controls)

        # File list
        list_label = QLabel("Audio Files:")
        right_panel.addWidget(list_label)

        self.listWidget = QListWidget()
        self.listWidget.setSelectionMode(QListWidget.ExtendedSelection)
        self.listWidget.itemSelectionChanged.connect(self.on_selection_changed)
        self.listWidget.setAlternatingRowColors(True)
        right_panel.addWidget(self.listWidget, stretch=3)

        # Waveform
        self.waveformPlot = pg.PlotWidget()
        self.waveformPlot.setMenuEnabled(False)
        self.waveformPlot.hideButtons()
        self.waveformPlot.showGrid(x=True, y=True, alpha=0.2)
        self.waveformPlot.setBackground("#111")
        self.waveformPlot.setFocusPolicy(Qt.StrongFocus)
        right_panel.addWidget(self.waveformPlot, stretch=2)

        # Audio player
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)

        self.playCursor = pg.InfiniteLine(pos=0, angle=90, movable=False, 
                                        pen=pg.mkPen('#44f', width=2))
        self.waveformPlot.addItem(self.playCursor)
        self.playCursor.hide()

        self.player.positionChanged.connect(self.update_play_cursor)
        self.player.playbackStateChanged.connect(self.update_play_button)

        # Trimming
        self.trim_start = 0
        self.trim_end = 0
        self.trim_enabled = False

        self.trimLineStart = pg.InfiniteLine(pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#00ff00', width=3, style=Qt.DashLine))
        self.trimLineEnd = pg.InfiniteLine(pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#ff0000', width=3, style=Qt.DashLine))

        self.waveformPlot.addItem(self.trimLineStart)
        self.waveformPlot.addItem(self.trimLineEnd)
        self.trimLineStart.hide()
        self.trimLineEnd.hide()

        self.trimLineStart.sigPositionChanged.connect(self.update_trim)
        self.trimLineEnd.sigPositionChanged.connect(self.update_trim)

        # Playback controls
        playback_frame = QWidget()
        playback_frame.setObjectName("controlFrame")
        playback_layout = QHBoxLayout(playback_frame)
        
        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.setObjectName("playButton")
        self.play_pause_btn.setEnabled(False)
        self.play_pause_btn.clicked.connect(self.toggle_play_pause)
        playback_layout.addWidget(self.play_pause_btn)
        
        right_panel.addWidget(playback_frame)

        # Trim controls
        trim_frame = QWidget()
        trim_frame.setObjectName("controlFrame")
        trim_layout = QVBoxLayout(trim_frame)

        trim_row = QHBoxLayout()
        self.trim_toggle = QCheckBox("Enable Audio Trimming")
        self.trim_toggle.stateChanged.connect(self.toggle_trim)
        trim_row.addWidget(self.trim_toggle)

        self.trim_btn = QPushButton("✂️ Crop Audio")
        self.trim_btn.setObjectName("cropButton")
        self.trim_btn.clicked.connect(self.crop_audio)
        trim_row.addWidget(self.trim_btn)
        trim_layout.addLayout(trim_row)

        # Start controls
        start_row = QHBoxLayout()
        start_label = QLabel("Start:")
        start_label.setObjectName("startLabel")
        start_row.addWidget(start_label)

        dec_start = QPushButton("−")
        dec_start.setObjectName("decStart")    
        dec_start.setFixedWidth(35)
        dec_start.clicked.connect(lambda: self.bump_start(-1))
        start_row.addWidget(dec_start)

        self.start_input = QLineEdit("0.0")
        self.start_input.setObjectName("startInput")
        self.start_input.setFixedWidth(80)
        self.start_input.setAlignment(Qt.AlignCenter)
        self.start_input.editingFinished.connect(self.manual_start_input)
        start_row.addWidget(self.start_input)

        inc_start = QPushButton("+")
        inc_start.setObjectName("incStart")
        inc_start.setFixedWidth(35)
        inc_start.clicked.connect(lambda: self.bump_start(1))
        start_row.addWidget(inc_start)
        start_row.addStretch()
        trim_layout.addLayout(start_row)

        # End controls
        end_row = QHBoxLayout()
        end_label = QLabel("End:")
        end_label.setObjectName("endLabel")
        end_row.addWidget(end_label)

        dec_end = QPushButton("−")
        dec_end.setObjectName("decEnd")
        dec_end.setFixedWidth(35)
        dec_end.clicked.connect(lambda: self.bump_end(-1))
        end_row.addWidget(dec_end)

        self.end_input = QLineEdit("0.0")
        self.end_input.setObjectName("endInput")
        self.end_input.setFixedWidth(80)
        self.end_input.setAlignment(Qt.AlignCenter)
        self.end_input.editingFinished.connect(self.manual_end_input)
        end_row.addWidget(self.end_input)

        inc_end = QPushButton("+")
        inc_end.setObjectName("incEnd")
        inc_end.setFixedWidth(35)
        inc_end.clicked.connect(lambda: self.bump_end(1))
        end_row.addWidget(inc_end)
        end_row.addStretch()
        trim_layout.addLayout(end_row)

        right_panel.addWidget(trim_frame)
        main_layout.addLayout(right_panel, stretch=1)

    def _load_stylesheet(self):
        """Load external QSS stylesheet"""
        try:
            style_path = os.path.join(os.path.dirname(__file__), '..', 'styles.qss')
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())
        except FileNotFoundError:
            print("Warning: styles.qss not found, using default styles")

    def _add_field(self, layout, label_text, widget):
        """Helper to add labeled field"""
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        # Labels
        layout.addWidget(label)
        layout.addWidget(widget)

    # # ========== SORT GENRES ==========
    def sort_genres(self):
        items = sorted(self.genre_input.itemText(i) for i in range(self.genre_input.count()))
        self.genre_input.clear()
        self.genre_input.addItems(items)

    # # ========== TOGGLE WAVEFORM ==========
    def toggle_waveform(self, checked):
        self.waveform_enabled = checked

    def update_waveform_settings(self):
        """Update waveform appearance settings and refresh display."""
        try:
            self.waveform_smoothing = max(1, int(self.smooth_input.text()))
            self.waveform_amplitude = max(0.1, float(self.amplitude_input.text()))
            
            # Refresh waveform if one is loaded
            if self.waveform_enabled and self.audioMgr.samples is not None:
                factor = max(1, int(len(self.audioMgr.samples) / 20000))
                self.display_waveform(self.audioMgr.samples, downsample_factor=factor)
        except ValueError:
            pass

    def keyPressEvent(self, event):
        """Handle keyboard shortcuts."""
        if event.key() == Qt.Key_Space and self.waveformPlot.hasFocus():
            self.toggle_play_pause()
            event.accept()
        else:
            super().keyPressEvent(event)

    # # ========== TRIM MARKERS ==========
    def toggle_trim(self, checked):
        self.trim_enabled = checked
        
        # Show/hide trim lines
        if checked:
            self.trimLineStart.show()
            self.trimLineEnd.show()
            
            if self.audioMgr.samples is not None:
                self.trim_start = 0
                self.trim_end = len(self.audioMgr.samples)
                self.trimLineStart.setPos(0)
                self.trimLineEnd.setPos(self.trim_end)
                self.start_input.setText("0.0")
                self.end_input.setText(f"{self.trim_end / self.audioMgr.sample_rate:.2f}")
        else:
            self.trimLineStart.hide()
            self.trimLineEnd.hide()


    def update_trim(self):
        if not self.trim_enabled:
            return

        self.trim_start = int(self.trimLineStart.value())
        self.trim_end = int(self.trimLineEnd.value())

        # Update inputs
        self.start_input.setText(f"{self.trim_start / self.audioMgr.sample_rate:.2f}")
        self.end_input.setText(f"{self.trim_end / self.audioMgr.sample_rate:.2f}")

        # Safety clamps
        if self.trim_start < 0: self.trim_start = 0
        if self.trim_end > len(self.audioMgr.samples): self.trim_end = len(self.audioMgr.samples)
        if self.trim_start >= self.trim_end: self.trim_end = self.trim_start + 1

    # ========== CROP AUDIO ==========
    def crop_audio(self):
        if self.audioMgr.samples is None or not self.trim_enabled:
            return

        start_ms = int((self.trim_start / self.audioMgr.sample_rate) * 1000)
        end_ms = int((self.trim_end / self.audioMgr.sample_rate) * 1000)

        # Load and trim audio
        audio = AudioSegment.from_file(self.file_path)
        trimmed = audio[start_ms:end_ms]

        # Generate save path
        save_path = self.file_path.replace(".", "_trimmed.")
        file_ext = os.path.splitext(self.file_path)[1].lower()
        
        # Export trimmed audio
        trimmed.export(save_path, format=file_ext[1:])  # Remove the '.' from extension

        # Copy metadata from original file
        try:
            # Load original metadata
            original_audio = MutagenFile(self.file_path, easy=True)
            original_raw = MutagenFile(self.file_path, easy=False)
            
            # Extract album art from original
            cover_data = self.audioMgr.extract_cover(original_raw) if original_raw else None
            
            # Apply metadata to trimmed file
            if file_ext == ".mp3":
                # MP3 handling
                try:
                    id3 = ID3(save_path)
                except ID3NoHeaderError:
                    id3 = ID3()
                
                easy = EasyID3(save_path)
                
                # Copy all standard tags
                for key in ["title", "artist", "album", "composer", "genre", "date"]:
                    if original_audio and key in original_audio:
                        easy[key] = original_audio[key][0]
                
                easy.save()
                
                # Add album art
                if cover_data:
                    id3 = ID3(save_path)
                    # Clear existing covers
                    for key in list(id3.keys()):
                        if key.startswith("APIC"):
                            del id3[key]
                    
                    id3.add(APIC(
                        encoding=3,
                        mime="image/jpeg",
                        type=3,
                        desc="Cover",
                        data=cover_data
                    ))
                    id3.save(v2_version=3)
            
            elif file_ext == ".flac":
                # FLAC handling
                new_audio = MutagenFile(save_path)
                
                # Copy all tags
                for key in ["title", "artist", "album", "composer", "genre", "date"]:
                    if original_audio and key in original_audio:
                        new_audio[key] = original_audio[key]
                
                # Add album art
                if cover_data:
                    new_audio.clear_pictures()
                    pic = Picture()
                    pic.data = cover_data
                    pic.type = 3
                    pic.mime = "image/jpeg"
                    new_audio.add_picture(pic)
                
                new_audio.save()
            
            QMessageBox.information(self, "Saved", f"Trimmed audio with metadata saved to:\n{save_path}")
        
        except Exception as e:
            QMessageBox.warning(self, "Metadata Error", 
                f"Audio trimmed successfully but metadata copy failed:\n{e}\n\nSaved to: {save_path}")
        
    # ========== PLAYBACK ==========
    def toggle_play_pause(self):
        if not self.file_path:
            return
        
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
        else:
            if self.player.source().isEmpty():
                self.player.setSource(QUrl.fromLocalFile(self.file_path))
            self.player.play()
            self.playCursor.show()

    def update_play_button(self, state):
        if state == QMediaPlayer.PlaybackState.PlayingState:
            self.play_pause_btn.setText("⏸ Pause")
        else:
            self.play_pause_btn.setText("▶ Play")

    def update_play_cursor(self, pos_ms):
        if self.audioMgr.sample_rate is None:
            return
        # convert ms → sample index
        sample_index = int((pos_ms / 1000) * self.audioMgr.sample_rate)
        self.playCursor.setPos(sample_index)
        
    # ========== TRIM INPUTS / BUTTONS ==========
    def manual_start_input(self):
        try:
            seconds = float(self.start_input.text())
            self.trim_start = int(seconds * self.audioMgr.sample_rate)
            self.trimLineStart.setPos(self.trim_start)
        except:
            pass

    def manual_end_input(self):
        try:
            seconds = float(self.end_input.text())
            self.trim_end = int(seconds * self.audioMgr.sample_rate)
            self.trimLineEnd.setPos(self.trim_end)
        except:
            pass

    def bump_start(self, val):
        self.trim_start += val * self.audioMgr.sample_rate  # val = +/- 1 sec
        if self.trim_start < 0: self.trim_start = 0
        self.trimLineStart.setPos(self.trim_start)
        self.start_input.setText(f"{self.trim_start / self.audioMgr.sample_rate:.2f}")

    def bump_end(self, val):
        self.trim_end += val * self.audioMgr.sample_rate
        if self.trim_end > len(self.audioMgr.samples):
            self.trim_end = len(self.audioMgr.samples)
        self.trimLineEnd.setPos(self.trim_end)
        self.end_input.setText(f"{self.trim_end / self.audioMgr.sample_rate:.2f}")

    # ========== WAVEFORM ==========
    def display_waveform(self, samples, downsample_factor=1):
        if samples is None:
            self.waveformPlot.clear()
            return
        
        # Downsample for performance
        plot_samples = samples[::downsample_factor] if downsample_factor > 1 else samples
        x_data = np.arange(len(samples))[::downsample_factor]
        
        # Apply smoothing by averaging blocks of samples
        if self.waveform_smoothing > 1:
            smooth_size = self.waveform_smoothing
            # Reshape and average
            trim_len = len(plot_samples) - (len(plot_samples) % smooth_size)
            smoothed = plot_samples[:trim_len].reshape(-1, smooth_size).mean(axis=1)
            x_smoothed = x_data[:trim_len:smooth_size]
            plot_samples = smoothed
            x_data = x_smoothed
        
        # Apply amplitude multiplier
        plot_samples = plot_samples * self.waveform_amplitude
        
        self.waveformPlot.clear()
        pen = pg.mkPen(color=(0, 200, 200), width=1)
        self.waveformPlot.plot(x_data, plot_samples, pen=pen, antialias=True)
        
        # Re-add the cursor and trim lines to plot
        self.waveformPlot.addItem(self.playCursor)
        self.waveformPlot.addItem(self.trimLineStart)
        self.waveformPlot.addItem(self.trimLineEnd)

    # ========== LOAD FOLDER ==========
    def load_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        
        self.audio_files = [
            os.path.join(folder, f) for f in os.listdir(folder)
            if f.lower().endswith((".mp3", ".flac", ".m4a", ".wav", ".ogg"))
        ]
        self.current_folder = folder  # store it
        self.refresh_btn.setEnabled(True)

        self.listWidget.clear()
        for f in self.audio_files:
            self.listWidget.addItem(os.path.basename(f))

    # ========== REFRESH FOLDER ==========
    def refresh_folder(self):
      print(f"Refreshing: {self.current_folder}")

      if hasattr(self, "current_folder") and self.current_folder:
          self.audio_files = [
              os.path.join(self.current_folder, f)
              for f in os.listdir(self.current_folder)
              if f.lower().endswith((".mp3", ".flac", ".m4a", ".wav", ".ogg"))
          ]

          self.listWidget.clear()
          for f in self.audio_files:
              self.listWidget.addItem(os.path.basename(f))

          # Auto-load first file (prevents sample_rate = None errors)
          if self.audio_files:
            self.listWidget.setCurrentRow(0)
            self.file_path = self.audio_files[0]
            self.load_audio(self.file_path)


    # ========== SELECTION CHANGED ==========
    def on_selection_changed(self):
        selected = self.listWidget.selectedItems()
        if not selected:
            return
        
        if len(selected) == 1:
            # Single file: load and display
            idx = self.listWidget.currentRow()
            self.file_path = self.audio_files[idx]
            self.load_single_file(self.file_path)
        else:
            # Multiple files: check if they share the same album art
            if self.waveform_enabled:
                self.waveformPlot.clear()
            self.title_input.setText("")
            self.composer_input.setText("")
            
            # Check for shared album art
            try:
                first_file = self.audio_files[self.listWidget.row(selected[0])]
                first_audio = MutagenFile(first_file, easy=False)
                first_cover = self.audioMgr.extract_cover(first_audio) if first_audio else None
                
                shared_cover = True
                if first_cover:
                    for item in selected[1:]:
                        idx = self.listWidget.row(item)
                        path = self.audio_files[idx]
                        audio = MutagenFile(path, easy=False)
                        cover = self.audioMgr.extract_cover(audio) if audio else None
                        if cover != first_cover:
                            shared_cover = False
                            break
                
                if shared_cover and first_cover:
                    # Display shared album art
                    img = Image.open(BytesIO(first_cover)).resize((self.album_size, self.album_size))
                    qimg = ImageQt(img)
                    self.cover_label.setPixmap(QPixmap.fromImage(qimg))
                    self.cover_label.setText("")
                else:
                    self.cover_label.setText(f"{len(selected)} Files Selected\n(Different Album Art)")
                    self.cover_label.setPixmap(QPixmap())
            except:
                self.cover_label.setText(f"{len(selected)} Files Selected")
                self.cover_label.setPixmap(QPixmap())
        
        self.cleanup_btn.setEnabled(True)
        self.save_btn.setEnabled(True)
        self.play_pause_btn.setEnabled(True)

    # ========== LOAD SINGLE FILE ==========
    def load_single_file(self, path):
        # Stop any playing audio when switching files
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.stop()
        self.player.setSource("")  # Clear the source
        self.playCursor.hide()

        # Load waveform only if enabled
        if self.waveform_enabled:
            info = self.audioMgr.load_audio(path)
            if info and self.audioMgr.samples is not None:
                factor = max(1, int(len(self.audioMgr.samples) / 20000))
                self.display_waveform(self.audioMgr.samples, downsample_factor=factor)
            else:
                self.waveformPlot.clear()
        else:
            # Waveform disabled → do NOT load audio samples at all
            self.waveformPlot.clear()

        # Load metadata
        try:
            easy_tags = MutagenFile(path, easy=True)
            raw_audio = MutagenFile(path, easy=False)
        except:
            easy_tags = None
            raw_audio = None

        def safe_get(key):
            if easy_tags is None:
                return ""
            try:
                return easy_tags.get(key, [""])[0]
            except:
                return ""

        self.title_input.setText(safe_get("title"))
        self.artist_input.setText(safe_get("artist"))
        self.album_input.setText(safe_get("album"))
        self.composer_input.setText(safe_get("composer"))

        # Add new fields
        self.year_input.setText(safe_get("date"))
        self.track_input.setText(safe_get("tracknumber"))
        self.genre_input.setCurrentText(safe_get("genre"))
        self.comment_input.setText(safe_get("description"))
        self.album_artist_input.setText(safe_get("albumartist"))
        self.discnumber_input.setText(safe_get("discnumber"))

        # Load album art
        cover_data = self.audioMgr.extract_cover(raw_audio) if raw_audio else None
        if cover_data:
            try:
                img = Image.open(BytesIO(cover_data)).resize((self.album_size, self.album_size))
                qimg = ImageQt(img)
                self.cover_label.setPixmap(QPixmap.fromImage(qimg))
            except:
                self.cover_label.setText("No Album Art")
                self.cover_label.setPixmap(QPixmap())
        else:
            self.cover_label.setText("No Album Art")
            self.cover_label.setPixmap(QPixmap())

    # ========== CHANGE ALBUM ART ==========
    def change_album_art(self):
        selected = self.listWidget.selectedItems()
        if not selected:
            return

        img_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Album Art", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not img_path:
            return

        try:
            img = Image.open(img_path).resize((self.album_size, self.album_size))
            qimg = ImageQt(img)
            self.cover_label.setPixmap(QPixmap.fromImage(qimg))
            
            with open(img_path, "rb") as f:
                self.new_cover_bytes = f.read()
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load image: {e}")
                            
    def crop_album_art(self):
        """Open the album art crop editor for the currently loaded cover."""
        selected = self.listWidget.selectedItems()
        if not selected:
            QMessageBox.information(self, "Info", "Please select at least one file to crop album art.")
            return
        
        # Get album art from first selected file
        try:
            first_file = self.audio_files[self.listWidget.row(selected[0])]
            raw_audio = MutagenFile(first_file, easy=False)
            cover_data = self.audioMgr.extract_cover(raw_audio) if raw_audio else None
            
            if not cover_data:
                QMessageBox.information(self, "No Album Art", "The selected file(s) have no album art to crop.")
                return
            
            # Check if multiple files selected - verify they share same album art
            if len(selected) > 1:
                shared_cover = True
                for item in selected[1:]:
                    idx = self.listWidget.row(item)
                    path = self.audio_files[idx]
                    audio = MutagenFile(path, easy=False)
                    other_cover = self.audioMgr.extract_cover(audio) if audio else None
                    if other_cover != cover_data:
                        shared_cover = False
                        break
                
                if not shared_cover:
                    reply = QMessageBox.question(self, "Different Album Arts", 
                        "Selected files have different album art. Use the first file's cover for all?",
                        QMessageBox.Yes | QMessageBox.No)
                    if reply == QMessageBox.No:
                        return
            
            # Open editor - store as instance variable so it persists
            self.album_editor = AlbumCoverEditor(cover_data, self)
            self.album_editor.finished_signal.connect(self.on_album_crop_finished)
            self.album_editor.show()
            
        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not crop album art: {e}")

    def on_album_crop_finished(self):
        """Handle when album crop editor is closed."""
        if hasattr(self.album_editor, 'result_bytes') and self.album_editor.result_bytes:
            self.new_cover_bytes = self.album_editor.result_bytes
            
            # Display preview
            img = Image.open(BytesIO(self.new_cover_bytes)).resize((self.album_size, self.album_size))
            qimg = ImageQt(img)
            self.cover_label.setPixmap(QPixmap.fromImage(qimg))
            
            selected = self.listWidget.selectedItems()
            if len(selected) > 1:
                QMessageBox.information(self, "Success", 
                    f"Album art cropped! Click 'Save Metadata' to apply to all {len(selected)} selected files.")
            else:
                QMessageBox.information(self, "Success", 
                    "Album art cropped! Click 'Save Metadata' to apply to the file.")
                
    # ========== CLEAN TITLE HELPER ==========
    def clean_title(self, title, artist, composer=""):
        """Clean a single title and extract featured artists."""
        if not title:
            return title, composer

        ft_artists = []

        # Extract featured artists from (ft. X), [feat. X]
        ft_matches = re.findall(r'[\(\[](?:ft\.?|feat\.?)\s+(.*?)[\)\]]', title, flags=re.IGNORECASE)
        for match in ft_matches:
            # Split on common separators
            parts = re.split(r',|&| and ', match, flags=re.IGNORECASE)
            ft_artists.extend([p.strip() for p in parts if p.strip()])

        # Extract from: Artist, FeaturedArtist - Title
        if artist and ' - ' in title:
            before_dash = title.split(' - ')[0]
            if ',' in before_dash:
                parts = before_dash.split(',')[1:]
                ft_artists.extend([p.strip() for p in parts if p.strip()])

        # Extract from: Artist & FeaturedArtist or Artist and FeaturedArtist
        if artist:
            and_matches = re.findall(rf'{re.escape(artist)}\s*(?:&|and)\s+([^-\(\[\|]+)', title, flags=re.IGNORECASE)
            ft_artists.extend([m.strip() for m in and_matches])

        # Remove unwanted phrases
        for pattern in UNWANTED_PATTERNS:
            title = re.sub(pattern, '', title, flags=re.IGNORECASE)

        # Remove artist name patterns
        if artist:
            # Remove "Artist, " or "Artist. " or "Artist - " at beginning
            title = re.sub(rf'^{re.escape(artist)}\s*[,\.\-–—]\s*', '', title, flags=re.IGNORECASE)
            # Remove "Artist &/and Someone"
            title = re.sub(rf'{re.escape(artist)}\s*(?:&|and)\s+[^-\(\[]+', '', title, flags=re.IGNORECASE)
            # Remove remaining artist name
            title = re.sub(rf'\b{re.escape(artist)}\b', '', title, flags=re.IGNORECASE)

        # Clean whitespace and punctuation
        title = re.sub(r'\s+', ' ', title).strip(" -_,;:.()[]")

        # Update composer with featured artists (deduplicated)
        existing = [c.strip() for c in composer.split(',') if c.strip()] if composer else []
        ft_artists = list(dict.fromkeys(ft_artists))  # Remove duplicates
        for ft in ft_artists:
            if ft and not any(ft.lower() == e.lower() for e in existing):
                existing.append(ft)

        return title, ", ".join(existing) if existing else ""

    # ========== AUTO CLEANUP ==========
    def auto_cleanup(self):
        """Clean titles for all selected files and show preview."""
        selected = self.listWidget.selectedItems()
        if not selected:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return

        preview = []
        cleaned_data = {}  # Store cleaned data temporarily

        for item in selected:
            idx = self.listWidget.row(item)
            path = self.audio_files[idx]

            try:
                audio = MutagenFile(path, easy=True)
                if not audio:
                    continue

                title = audio.get("title", [""])[0]
                artist = audio.get("artist", [""])[0]
                composer = audio.get("composer", [""])[0]

                # Use UI artist if provided (for batch mode)
                ui_artist = self.artist_input.text().strip()
                artist_for_clean = ui_artist if ui_artist else artist


                cleaned_title, updated_composer = self.clean_title(title, artist_for_clean, composer)
                
                cleaned_data[path] = {
                    "title": cleaned_title,
                    "composer": updated_composer
                }
                
                ft_preview = f" (ft: {updated_composer})" if updated_composer else ""
                preview.append(f"{os.path.basename(path)}\n  → {cleaned_title}{ft_preview}")

            except Exception as e:
                print(f"Error cleaning {os.path.basename(path)}: {e}")

        # Show preview
        preview_text = "\n\n".join(preview[:50])
        if len(preview) > 50:
            preview_text += f"\n\n...and {len(preview)-50} more"

        msg = QMessageBox(self)
        msg.setWindowTitle("Cleanup Preview")
        msg.setText(f"Preview of cleaned titles for {len(preview)} files:")
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)

        if msg.exec() == QMessageBox.Ok:
            # Apply cleaned data to files
            for path, data in cleaned_data.items():
                try:
                    audio = MutagenFile(path, easy=True)
                    audio["title"] = data["title"]
                    if data["composer"]:
                        audio["composer"] = data["composer"]
                    audio.save()
                except Exception as e:
                    print(f"Error saving {os.path.basename(path)}: {e}")

            QMessageBox.information(self, "Complete", f"Cleaned {len(cleaned_data)} files.")
            
            # Refresh display if single file
            if len(selected) == 1:
                self.load_single_file(self.file_path)

    # ========== SAVE METADATA ==========
    def save_metadata(self):
        """Save metadata to all selected files."""
        selected = self.listWidget.selectedItems()
        if not selected:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return

        # Get UI values
        title = self.title_input.text().strip()
        artist = self.artist_input.text().strip()
        album = self.album_input.text().strip()
        composer = self.composer_input.text().strip()
        year = self.year_input.text().strip()
        track = self.track_input.text().strip()
        genre = self.genre_input.currentText().strip()
        comment = self.comment_input.text().strip()
        album_artist = self.album_artist_input.text().strip()
        discnumber = self.discnumber_input.text().strip()

        # Confirm batch operation
        if len(selected) > 1:
            details = []
            if artist:
                details.append(f"• Artist: '{artist}'")
            if album:
                details.append(f"• Album: '{album}'")
            if composer:
                details.append(f"• Composer: '{composer}'")
            if self.new_cover_bytes:
                details.append("• Album Art")

            msg = QMessageBox(self)
            msg.setWindowTitle("Batch Save")
            msg.setText(f"Save to {len(selected)} files?")
            msg.setInformativeText("\n".join(details) if details else "No changes detected")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
            
            if msg.exec() != QMessageBox.Save:
                return

        errors = []
        saved = 0

        for item in selected:
            idx = self.listWidget.row(item)
            path = self.audio_files[idx]
            ext = os.path.splitext(path)[1].lower()

            try:
                if ext == ".mp3":
                    # MP3 handling
                    try:
                        id3 = ID3(path)
                    except ID3NoHeaderError:
                        id3 = ID3()
                        id3.save(path)

                    # For MP3 
                    easy = EasyID3(path)
                    if title: easy["title"] = title
                    if artist: easy["artist"] = artist
                    if album: easy["album"] = album
                    if composer: easy["composer"] = composer
                    if year: easy["date"] = year
                    if track: easy["tracknumber"] = track
                    if genre: easy["genre"] = genre
                    if comment: easy["description"] = comment  
                    if album_artist: easy["albumartist"] = album_artist
                    if discnumber: easy["discnumber"] = discnumber
                    easy.save()

                    # Album art
                    if self.new_cover_bytes:
                        for key in list(id3.keys()):
                            if key.startswith("APIC"):
                                del id3[key]
                        id3.add(APIC(
                            encoding=3, mime="image/jpeg", type=3,
                            desc="Cover", data=self.new_cover_bytes
                        ))
                        id3.save(v2_version=3)

                elif ext == ".flac":
                     # For FLAC 
                    audio = MutagenFile(path)
                    if title: audio["title"] = [title]
                    if artist: audio["artist"] = [artist]
                    if album: audio["album"] = [album]
                    if composer: audio["composer"] = [composer]
                    if year: audio["date"] = [year]
                    if track: audio["tracknumber"] = [track]
                    if genre: audio["genre"] = [genre]
                    if comment: audio["description"] = [comment] 
                    if album_artist: audio["albumartist"] = [album_artist]
                    if discnumber: audio["discnumber"] = [discnumber]

                    if self.new_cover_bytes:
                        audio.clear_pictures()
                        pic = Picture()
                        pic.data = self.new_cover_bytes
                        pic.type = 3
                        pic.mime = "image/jpeg"
                        audio.add_picture(pic)

                    audio.save()

                saved += 1

            except Exception as e:
                errors.append(f"{os.path.basename(path)}: {e}")

        if errors:
            QMessageBox.critical(self, "Errors", "\n".join(errors))
        else:
            QMessageBox.information(self, "Success", f"Saved metadata to {saved} files.")