"""
Main Window - Coordinates all components
"""
import os
from io import BytesIO
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog, QMessageBox, QLabel
from PySide6.QtCore import Qt, QUrl, QItemSelectionModel
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtMultimedia import QMediaPlayer
from PIL import Image
from PIL.ImageQt import ImageQt
from mutagen import File as MutagenFile

from core.audio_controller import AudioController
from core.metadata_manager import MetadataManager
from core.waveform_controller import WaveformController
from core.tag_inference import TagInference
from ui.left_panel import LeftPanel
from ui.right_panel import RightPanel
from ui.genre_manager import GenreManager
from .album_editor import AlbumCoverEditor


class MainWindow(QWidget):
    """Main application window"""
    
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Sound Simulation")
        self.setGeometry(100, 100, 1400, 800)
        self.setFocusPolicy(Qt.StrongFocus)

        # Set window icon
        import sys
        try:
            if getattr(sys, 'frozen', False):
                icon_path = os.path.join(sys._MEIPASS, 'assets', 'icon.ico')
            else:
                icon_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'icon.ico')
            
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception as e:
            print(f"Could not load icon: {e}")
        
        # State
        self.audio_files = []
        self.current_folder = None
        self.file_path = None
        self.new_cover_bytes = None
        
        # Controllers
        self.audio_controller = AudioController()
        self.metadata_manager = MetadataManager()

        self.overwrite_original = True  # Default to overwrite

        
        # Load stylesheet
        self._load_stylesheet()
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
    
    def _load_stylesheet(self):
        """Load external QSS stylesheet"""
        import sys
        try:
            # Check if running as PyInstaller bundle
            if getattr(sys, 'frozen', False):
                base_path = sys._MEIPASS
            else:
                base_path = os.path.dirname(__file__)
                base_path = os.path.join(base_path, '..')
            
            style_path = os.path.join(base_path, 'styles.qss')
            
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())
                print(f"✓ Stylesheet loaded from: {style_path}")
        except FileNotFoundError:
            print("Warning: styles.qss not found, using default styles")
    
    def _setup_ui(self):
        """Initialize UI layout"""
        main_layout = QHBoxLayout(self)
        main_layout.setSpacing(15)
        
        # Left panel
        self.left_panel = LeftPanel(album_size=400)
        GenreManager.populate_combobox(self.left_panel.genre_input)
        main_layout.addWidget(self.left_panel)
        
        # Right panel
        self.right_panel = RightPanel()
        
        # Create waveform controller AFTER right_panel is created
        self.waveform_controller = WaveformController(self.right_panel.waveform_plot)
        
        # Initially hide waveform plot
        self.right_panel.waveform_plot.hide()
        
        main_layout.addWidget(self.right_panel, stretch=1)
    
    def _connect_signals(self):
        """Connect all signals"""
        # Left panel signals
        self.left_panel.change_cover_clicked.connect(self.change_album_art)
        self.left_panel.crop_cover_clicked.connect(self.crop_album_art)
        self.left_panel.cleanup_clicked.connect(self.auto_cleanup)
        self.left_panel.clean_filename_clicked.connect(self.clean_filenames)
        self.left_panel.field_changed.connect(self._on_left_field_changed)
        
        # Right panel signals
        self.right_panel.load_folder_clicked.connect(self.load_folder)
        self.right_panel.refresh_clicked.connect(self.refresh_folder)
        self.right_panel.waveform_toggled.connect(self.toggle_waveform)
        self.right_panel.waveform_settings_changed.connect(self.update_waveform_settings)
        self.right_panel.selection_changed.connect(self.on_selection_changed)
        self.right_panel.play_pause_clicked.connect(self.audio_controller.toggle_play_pause)
        self.right_panel.trim_toggled.connect(self.on_trim_toggled)
        self.right_panel.overwrite_toggled.connect(self.on_overwrite_toggled)
        self.right_panel.trim_values_changed.connect(self.on_trim_values_changed)
        self.right_panel.crop_audio_clicked.connect(self.crop_audio)
        self.right_panel.table_cell_changed.connect(self._on_right_cell_changed)
        
        # Audio controller signals
        self.audio_controller.position_changed.connect(self.waveform_controller.update_play_cursor)
        self.audio_controller.playback_state_changed.connect(self.on_playback_state_changed)
        self.audio_controller.audio_loaded.connect(self.on_audio_loaded)
        
        # Waveform controller signals
        self.waveform_controller.seek_requested.connect(self.audio_controller.seek_to_position)
        self.waveform_controller.trim_changed.connect(self.on_trim_changed)
        
        # Keyboard shortcut
        self.right_panel.waveform_plot.keyPressEvent = self._waveform_key_press
    
    def _waveform_key_press(self, event):
        """Handle keyboard shortcuts on waveform"""
        if event.key() == Qt.Key_Space:
            self.audio_controller.toggle_play_pause()
            event.accept()
    
    def _on_left_field_changed(self, field_name, new_value):
        selected = self.right_panel.get_selected_rows()
        if not selected:
            return

        for row in selected:
            file_path = self.audio_files[row]
            metadata = self.metadata_manager.read_metadata(file_path) or {}

            # Always update the field, even if blank (to allow clearing)
            metadata[field_name] = new_value.strip()

            # Save with allow_blanks=True
            self.metadata_manager.write_metadata(file_path, metadata, allow_blanks=True)

            # Update right table UI
            col = self._right_column_index(field_name)
            if col is not None:
                self.right_panel.table.blockSignals(True)
                item = self.right_panel.table.item(row, col)
                if item:
                    item.setText(new_value)
                self.right_panel.table.blockSignals(False)
    
    def _get_row_for_file(self, path):
        try:
            return self.audio_files.index(path)
        except ValueError:
            return None

    def _right_column_index(self, field):
        mapping = {
            "title": 1,
            "artist": 2,
            "album": 3,
            "album_artist": 4,
            "track": 5,
            "disc": 6,
            "year": 7,
            "genre": 8,
            "comment": 9
        }
        return mapping.get(field)

    def _on_right_cell_changed(self, row, column, new_value):
        """Update left panel and metadata when right table editing occurs."""
        if row < 0 or row >= len(self.audio_files):
            return

        file_path = self.audio_files[row]
        field = self._right_column_field(column)

        if not field:
            return

        metadata = self.metadata_manager.read_metadata(file_path) or {}

        # Always update (even blank values)
        metadata[field] = new_value.strip()

        # Save metadata with allow_blanks=True
        self.metadata_manager.write_metadata(file_path, metadata, allow_blanks=True)

        # Update left panel in ALL cases where this file is part of current selection
        selected_rows = self.right_panel.get_selected_rows()
        
        if row in selected_rows:
            # For single selection, update all fields
            if len(selected_rows) == 1:
                self.left_panel.blockSignals(True)
                self.left_panel.set_field(field, new_value)
                self.left_panel.blockSignals(False)
            # For multiple selection, refresh shared metadata
            else:
                self._load_shared_metadata(selected_rows)

    def _right_column_field(self, col):
        mapping = {
            1: "title",
            2: "artist",
            3: "album",
            4: "album_artist",
            5: "track",
            6: "disc",
            7: "year",
            8: "genre",
            9: "comment"
        }
        return mapping.get(col)
    
    def _load_shared_metadata(self, selected_rows):
        """Show only metadata values that are identical across selected files."""
        if not selected_rows:
            return

        paths = [self.audio_files[r] for r in selected_rows]
        all_metadata = [self.metadata_manager.read_metadata(p) or {} for p in paths]

        if not all_metadata:
            return

        # Keys from first file
        first = all_metadata[0]
        shared = {}

        for key, value in first.items():
            if all(md.get(key) == value for md in all_metadata):
                shared[key] = value
            else:
                shared[key] = ""  # use blank for mixed values

        self.left_panel.set_metadata(shared)
    
    # ==================== FOLDER OPERATIONS ====================
    
    def load_folder(self):
        """Load all audio files from a folder"""
        folder = QFileDialog.getExistingDirectory(self, "Select Folder")
        if not folder:
            return
        
        # Find audio files
        self.audio_files = []
        for root, _, files in os.walk(folder):
            for f in files:
                if f.lower().endswith((".mp3", ".flac", ".wav", ".m4a", ".ogg")):
                    self.audio_files.append(os.path.join(root, f))
        
        self.current_folder = folder
        self.right_panel.enable_refresh_button(True)
        
        # Populate table
        self.right_panel.populate_table(self.audio_files, self.metadata_manager)
        
        QMessageBox.information(self, "Loaded", f"Loaded {len(self.audio_files)} audio files.")
    
    def refresh_folder(self):
        """Refresh current folder"""
        if not self.current_folder:
            QMessageBox.warning(self, "No Folder", "No folder loaded to refresh.")
            return
        
        # Rebuild file list
        self.audio_files = [
            os.path.join(self.current_folder, f)
            for f in sorted(os.listdir(self.current_folder))
            if f.lower().endswith((".mp3", ".flac", ".m4a", ".wav", ".ogg"))
        ]
        
        # Repopulate table
        self.right_panel.populate_table(self.audio_files, self.metadata_manager)
        
        # Auto-load first file
        if self.audio_files:
            self.right_panel.set_current_row(0)


    def refresh_after_edit(self, file_path):
        """Refresh UI after trimming or overwriting."""
        print(f"[MainWindow] refresh_after_edit(): {file_path}")

        # Re-scan files on the LEFT (folder panel)
        if self.current_folder:
            self.load_folder(self.current_folder)

        # Rebuild right table
        self.right_panel.populate_table(self.audio_files, self.metadata_manager)

        # Re-select the file
        self.select_file_in_table(file_path)

        # Reload metadata + waveform + audio
        self.load_file(file_path)

    
    # ==================== SELECTION HANDLING ====================
    
    def on_selection_changed(self, selected_rows):
        """Handle file selection change"""
        if len(selected_rows) == 1:
            self._handle_single_selection(selected_rows[0])
        elif len(selected_rows) > 1:
            self._handle_multiple_selection(selected_rows)
        else:
            self._clear_selection()
    
    def _handle_single_selection(self, row):
        """Handle single file selection"""
        self.file_path = self.audio_files[row]
        
        print(f"Single selection: {self.file_path}")
        
        # Stop current playback
        self.audio_controller.stop()
        
        # Load audio if waveform enabled
        if self.waveform_controller.enabled:
            print("Waveform enabled, loading audio...")
            self.audio_controller.load_audio(self.file_path)
        else:
            print("Waveform disabled, loading metadata only...")
            # Just load metadata and set up player source
            self._load_metadata_only(self.file_path)
            # Set player source for playback even without waveform
            file_url = QUrl.fromLocalFile(os.path.abspath(self.file_path))
            self.audio_controller.player.setSource(file_url)
        
        # Enable controls
        self.right_panel.enable_play_button(True)
        self.left_panel.enable_buttons(True, True)
    
    def _load_metadata_only(self, path):
        """Load metadata without audio samples"""
        metadata = self.metadata_manager.read_metadata(path)
        if metadata:
            self.left_panel.set_metadata(metadata)
        
        # Load album art
        pixmap = self.metadata_manager.get_cover_as_pixmap(path, size=400)
        if pixmap:
            self.left_panel.set_cover_pixmap(pixmap)
        else:
            self.left_panel.set_cover_text("No Album Art")
    
    def _handle_multiple_selection(self, selected_rows):
        """Handle multiple file selection"""
        self.audio_controller.stop()
        self.waveform_controller.clear()
        self.left_panel.clear_metadata()
        
        # Check for shared album art
        self._check_shared_album_art(selected_rows)
        
        # Enable buttons
        self.left_panel.enable_buttons(True, True)
        self.right_panel.enable_play_button(False)

        self._load_shared_metadata(selected_rows)
    
    def _check_shared_album_art(self, selected_rows):
        """Check if selected files share same album art"""
        if not selected_rows:
            return
        
        try:
            first_path = self.audio_files[selected_rows[0]]
            first_cover = self.metadata_manager.extract_cover(first_path)
            
            if not first_cover:
                self.left_panel.set_cover_text(f"{len(selected_rows)} Files Selected")
                return
            
            shared = True
            for row in selected_rows[1:]:
                path = self.audio_files[row]
                cover = self.metadata_manager.extract_cover(path)
                if cover != first_cover:
                    shared = False
                    break
            
            if shared:
                img = Image.open(BytesIO(first_cover)).resize((400, 400))
                qimg = ImageQt(img)
                self.left_panel.set_cover_pixmap(QPixmap.fromImage(qimg))
            else:
                self.left_panel.set_cover_text(f"{len(selected_rows)} Files Selected\n(Different Album Art)")
        except Exception as e:
            print(f"Album art check error: {e}")
            self.left_panel.set_cover_text(f"{len(selected_rows)} Files Selected")
    
    def _clear_selection(self):
        """Clear selection state"""
        self.audio_controller.clear_audio()
        self.waveform_controller.clear()
        self.left_panel.clear_metadata()
        self.left_panel.set_cover_text("No Album Art")
        self.left_panel.enable_buttons(False, False)
        self.right_panel.enable_play_button(False)

    def select_file_in_table(self, file_path):
        """Select the given file in the right panel table."""
        table = self.right_panel.file_table
        target_name = os.path.basename(file_path)

        for row in range(table.rowCount()):
            item = table.item(row, 0)
            if item and os.path.basename(item.text()) == target_name:
                table.selectRow(row)
                return
    
    # ==================== WAVEFORM ====================
    
    def toggle_waveform(self, enabled):
        """Toggle waveform display"""
        print(f"Toggle waveform: {enabled}, current file: {self.file_path}")
        self.waveform_controller.set_enabled(enabled)
        
        if enabled:
            if self.file_path:
                print(f"Loading audio for waveform: {self.file_path}")
                # Load audio for current file
                info = self.audio_controller.load_audio(self.file_path)
                if info:
                    print("Audio loaded successfully")
                else:
                    print("Failed to load audio")
            else:
                print("No file selected yet")
        else:
            print("Waveform disabled, clearing samples")
            self.audio_controller.samples = None
            self.waveform_controller.samples = None
    
    def update_waveform_settings(self, smoothing, amplitude):
        """Update waveform display settings"""
        self.waveform_controller.set_smoothing(smoothing)
        self.waveform_controller.set_amplitude(amplitude)
        self.waveform_controller.refresh()
    
    def on_audio_loaded(self, info):
        """Handle audio loaded event"""
        print("Audio loaded event received")
        
        # Load waveform
        samples = info['samples']
        sample_rate = info['sample_rate']
        
        print(f"Loading waveform with {len(samples)} samples at {sample_rate}Hz")
        
        factor = max(1, int(len(samples) / 20000))
        self.waveform_controller.load_waveform(samples, sample_rate, factor)
        
        # Reset trim markers if trim is enabled
        if self.waveform_controller.trim_enabled:
            print("Resetting trim markers for new file")
            self.waveform_controller.enable_trim(True)  # This will reset positions
        
        # Load metadata
        metadata = self.metadata_manager.read_metadata(self.audio_controller.current_file)
        if metadata:
            self.left_panel.set_metadata(metadata)
        
        # Load album art
        pixmap = self.metadata_manager.get_cover_as_pixmap(
            self.audio_controller.current_file, size=400
        )
        if pixmap:
            self.left_panel.set_cover_pixmap(pixmap)
        else:
            self.left_panel.set_cover_text("No Album Art")
    
    # ==================== PLAYBACK ====================
    
    def on_playback_state_changed(self, state):
        """Handle playback state change"""
        if state == QMediaPlayer.PlayingState:
            self.right_panel.set_play_button_text("⏸ Pause")
        else:
            self.right_panel.set_play_button_text("▶ Play")
            if state == QMediaPlayer.StoppedState:
                self.waveform_controller.hide_play_cursor()
    
    # ==================== TRIMMING ====================
    
    def on_trim_toggled(self, enabled):
        """Handle trim toggle"""
        print(f"Trim toggled: {enabled}")
        
        if enabled:
            # Check if waveform is enabled
            if not self.waveform_controller.enabled:
                QMessageBox.warning(
                    self, 
                    "Waveform Required",
                    "Please enable 'Show Waveform' first to use audio trimming."
                )
                # Uncheck the trim checkbox
                self.right_panel.trim_toggle.setChecked(False)
                return
            
            # Check if samples are loaded
            if self.audio_controller.samples is None:
                QMessageBox.warning(
                    self,
                    "No Audio Loaded",
                    "Please select a file first, then enable waveform to load audio samples."
                )
                # Uncheck the trim checkbox
                self.right_panel.trim_toggle.setChecked(False)
                return
        
        # Enable/disable trim in waveform controller
        success = self.waveform_controller.enable_trim(enabled)
        
        if not success and enabled:
            # If enabling failed, uncheck the checkbox
            self.right_panel.trim_toggle.setChecked(False)

    def on_overwrite_toggled(self, enabled):
        """Handle overwrite toggle"""
        print(f"Overwrite toggle: {enabled}")
        # Store the overwrite preference
        self.overwrite_original = enabled
        
        # Update button text based on overwrite mode
        if enabled:
            self.right_panel.trim_btn.setText("✂️ Overwrite Audio")
        else:
            self.right_panel.trim_btn.setText("✂️ Save Trimmed Copy")
    
    def on_trim_changed(self, start_sample, end_sample):
        """Handle trim position change"""
        start_sec, end_sec = self.waveform_controller.get_trim_times()
        self.right_panel.set_trim_times(start_sec, end_sec)
    
    def on_trim_values_changed(self, start_sec, end_sec):
        """Handle manual trim value input"""
        start_sample = self.waveform_controller.time_to_samples(start_sec)
        end_sample = self.waveform_controller.time_to_samples(end_sec)
        
        self.waveform_controller.set_trim_start(start_sample)
        self.waveform_controller.set_trim_end(end_sample)
    
    def crop_audio(self):
        """Crop audio file"""
        print(f"Crop audio called - file_path: {self.file_path}, trim_enabled: {self.waveform_controller.trim_enabled}")
        print(f"Audio samples loaded: {self.audio_controller.samples is not None}")
        print(f"Overwrite original: {self.overwrite_original}")
        
        if not self.file_path:
            QMessageBox.warning(self, "Cannot Trim", "No file selected.")
            return
            
        if not self.waveform_controller.trim_enabled:
            QMessageBox.warning(self, "Cannot Trim", "Trimming not enabled. Check 'Enable Audio Trimming' first.")
            return
        
        if self.audio_controller.samples is None:
            QMessageBox.warning(self, "Cannot Trim", "No audio loaded. Enable waveform first to load audio samples.")
            return
        
        try:
            start_sample, end_sample = self.waveform_controller.get_trim_positions()
            print(f"Trimming from {start_sample} to {end_sample} samples")
            print(f"Overwrite mode: {self.overwrite_original}")
            
            # Confirm overwrite if enabled
            if self.overwrite_original:
                reply = QMessageBox.question(
                    self,
                    "Overwrite Original File",
                    "⚠️ This will permanently overwrite the original audio file.\n\n"
                    "This action cannot be undone.\n\n"
                    "Are you sure you want to continue?",
                    QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                    QMessageBox.StandardButton.No
                )
                
                if reply != QMessageBox.StandardButton.Yes:
                    print("Overwrite cancelled by user")
                    return
            
            # Crop with overwrite option
            trimmed_path = self.audio_controller.crop_audio(
                self.file_path, 
                start_sample, 
                end_sample,
                overwrite_original=self.overwrite_original
            )
            
            # Refresh the current file if overwritten
            if self.overwrite_original:
                # Reload file (metadata + samples)
                self.load_file(trimmed_path)

                # --- FORCE waveform to refresh by imitating a file selection ---
                row = self._get_row_for_file(trimmed_path)
                if row is not None:
                    model = self.right_panel.table.model()
                    index = model.index(row, 0)

                    # Re-select row
                    self.right_panel.table.selectionModel().setCurrentIndex(
                        index,
                        QItemSelectionModel.Select | QItemSelectionModel.Rows
                    )

                    # Emit selection event manually
                    self.right_panel.selection_changed.emit([row])

            else:
                # Saved as new file → just repopulate
                self.audio_files.append(trimmed_path)
                self.right_panel.populate_table(self.audio_files, self.metadata_manager)


        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Trim Error", f"Failed to trim audio: {e}")


    def load_file(self, file_path):
        """Load single audio file for metadata, waveform, and playback."""
        try:
            print(f"[MainWindow] load_file(): {file_path}")

            # Clear UI state
            self.clear_current_file()

            # Update right-panel header
            self.right_panel.file_info_label.setText(
                f"File: {os.path.basename(file_path)}"
            )

            # Load metadata
            metadata = self.metadata_manager.get_metadata(file_path)
            self.metadata_manager.update_metadata_panel(metadata)

            # Load audio for waveform + playback
            audio_info = self.audio_controller.load_audio(file_path)

            if audio_info:
                if self.waveform_controller.enabled:
                    self.waveform_controller.set_audio_data(
                        audio_info["samples"],
                        audio_info["sample_rate"]
                    )

                # Set current file
                self.file_path = file_path

                # If trim already enabled, update displayed trim times
                if self.waveform_controller.trim_enabled:
                    start_sec, end_sec = self.waveform_controller.get_trim_times()
                    self.right_panel.set_trim_times(start_sec, end_sec)

                print(f"[MainWindow] File loaded OK: {file_path}")
                return True

            print("[MainWindow] Failed to load audio file.")
            return False

        except Exception as e:
            print(f"[MainWindow] ERROR load_file(): {e}")
            import traceback
            traceback.print_exc()
            return False


    # ==================== ALBUM ART ====================
    
    def change_album_art(self):
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Please select at least one file.")
            return

        img_path, _ = QFileDialog.getOpenFileName(
            self, "Choose Album Art", "", "Images (*.png *.jpg *.jpeg *.bmp)"
        )
        if not img_path:
            return

        try:
            # Resize preview
            img = Image.open(img_path).resize((400, 400))
            qimg = ImageQt(img)
            self.left_panel.set_cover_pixmap(QPixmap.fromImage(qimg))

            # Load bytes
            with open(img_path, "rb") as f:
                self.new_cover_bytes = f.read()

            # AUTO-SAVE COVER TO ALL SELECTED FILES
            self._apply_cover_to_selected_files()

            QMessageBox.information(self, "Success", "Album art updated!")

        except Exception as e:
            QMessageBox.warning(self, "Error", f"Could not load image: {e}")

    def _apply_cover_to_selected_files(self):
        """Immediately saves the new cover to all selected files."""
        if not self.new_cover_bytes:
            return

        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            return

        cover = self.new_cover_bytes
        paths = [self.audio_files[r] for r in selected_rows]

        for path in paths:
            # Write cover ONLY, leave text metadata untouched.
            self.metadata_manager.write_metadata(
                path,
                metadata={},                # don't change any text fields
                cover_data=cover,
                allow_blanks=False          # prevents accidental clearing
            )

        # Refresh table
        self.right_panel.populate_table(self.audio_files, self.metadata_manager)
    
    def crop_album_art(self):
        """Crop album art"""
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Please select at least one file.")
            return
        
        try:
            first_file = self.audio_files[selected_rows[0]]
            cover_data = self.metadata_manager.extract_cover(first_file)
            
            if not cover_data:
                QMessageBox.information(self, "No Album Art", "The selected file(s) have no album art.")
                return
            
            # Check if shared across multiple files
            if len(selected_rows) > 1:
                shared = all(
                    self.metadata_manager.extract_cover(self.audio_files[row]) == cover_data
                    for row in selected_rows[1:]
                )
                
                if not shared:
                    reply = QMessageBox.question(
                        self, "Different Album Arts",
                        "Use first file's album art for all?",
                        QMessageBox.Yes | QMessageBox.No
                    )
                    if reply == QMessageBox.No:
                        return
            
            self.album_editor = AlbumCoverEditor(cover_data, self)
            self.album_editor.finished_signal.connect(self.on_album_crop_finished)
            self.album_editor.show()
            
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open album editor: {e}")
    
    def on_album_crop_finished(self):
        if not hasattr(self.album_editor, 'result_bytes'):
            return

        if not self.album_editor.result_bytes:
            return

        # Save bytes
        self.new_cover_bytes = self.album_editor.result_bytes

        # Preview
        img = Image.open(BytesIO(self.new_cover_bytes)).resize((400, 400))
        qimg = ImageQt(img)
        self.left_panel.set_cover_pixmap(QPixmap.fromImage(qimg))

        # AUTO-SAVE CROPPED COVER
        self._apply_cover_to_selected_files()

        QMessageBox.information(self, "Success", "Album art cropped and saved!")
    
    # ==================== METADATA OPERATIONS ====================
    
    def auto_cleanup(self):
        """Auto-clean metadata using smart inference"""
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return
        
        selected_paths = [self.audio_files[row] for row in selected_rows]
        
        # Use new TagInference system
        cleaned_data = TagInference.batch_clean_files(selected_paths, self.metadata_manager)
        
        # Show preview
        preview = []
        for path, data in cleaned_data.items():
            composer_preview = f" | Composer: {data['composer']}" if data['composer'] else ""
            preview.append(
                f"{os.path.basename(path)}\n"
                f"  → Title: {data['title']}\n"
                f"  → Artist: {data['artist']}{composer_preview}"
            )
        
        preview_text = "\n\n".join(preview[:30])
        if len(preview) > 30:
            preview_text += f"\n\n...and {len(preview)-30} more"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Cleanup Preview")
        msg.setText(f"Preview of cleaned metadata for {len(preview)} files:")
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() == QMessageBox.Ok:
            saved = TagInference.apply_cleaned_metadata(cleaned_data, self.metadata_manager)
            QMessageBox.information(self, "Complete", f"Cleaned {saved} files.")
            
            # Refresh table
            self.right_panel.populate_table(self.audio_files, self.metadata_manager)
            
            # Refresh left panel if single file
            if len(selected_rows) == 1:
                self._load_metadata_only(self.file_path)
    
    def clean_filenames(self):
        """Clean selected filenames"""
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return
        
        # CRITICAL: Stop playback and clear audio to release file handles
        was_playing = self.audio_controller.is_playing()
        current_position = self.audio_controller.get_position_ms() if was_playing else 0
        self.audio_controller.stop()
        self.audio_controller.clear_audio()
        
        selected_paths = [self.audio_files[row] for row in selected_rows]
        
        # Show preview of new filenames
        rename_plan = []
        for path in selected_paths:
            old_name = os.path.basename(path)
            new_name_no_ext = TagInference.clean_filename(old_name)
            ext = os.path.splitext(old_name)[1]
            new_name = new_name_no_ext + ext
            
            # Only add to plan if the name actually changed
            if old_name != new_name:
                # Check if target filename already exists
                new_path = os.path.join(os.path.dirname(path), new_name)
                
                # If file exists and it's not the same file, add a number
                if os.path.exists(new_path) and os.path.abspath(new_path) != os.path.abspath(path):
                    base, ext = os.path.splitext(new_name)
                    counter = 1
                    while os.path.exists(new_path):
                        new_name = f"{base}_{counter}{ext}"
                        new_path = os.path.join(os.path.dirname(path), new_name)
                        counter += 1
                
                rename_plan.append({
                    'old_path': path,
                    'old_name': old_name,
                    'new_name': new_name,
                    'new_path': new_path
                })
        
        if not rename_plan:
            QMessageBox.information(self, "No Changes", "No filenames need cleaning.")
            # Reload audio if it was playing
            if was_playing and self.file_path:
                self.audio_controller.load_audio(self.file_path)
                self.audio_controller.player.setPosition(current_position)
            return
        
        # Show preview
        preview = [f"{item['old_name']}\n  → {item['new_name']}" for item in rename_plan]
        preview_text = "\n\n".join(preview[:30])
        if len(preview) > 30:
            preview_text += f"\n\n...and {len(preview)-30} more"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Rename Preview")
        msg.setText(f"Preview filename changes for {len(rename_plan)} files:")
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() == QMessageBox.Ok:
            success_count = 0
            errors = []
            
            for item in rename_plan:
                try:
                    # Double-check file isn't locked
                    import time
                    time.sleep(0.1)  # Small delay to ensure file handles are released
                    
                    os.rename(item['old_path'], item['new_path'])
                    # Update internal list
                    idx = self.audio_files.index(item['old_path'])
                    self.audio_files[idx] = item['new_path']
                    
                    # Update current file path if it was renamed
                    if self.file_path == item['old_path']:
                        self.file_path = item['new_path']
                    
                    success_count += 1
                    print(f"✓ Renamed: {item['old_name']} → {item['new_name']}")
                except Exception as e:
                    error_msg = f"{item['old_name']}: {str(e)}"
                    print(f"✗ Failed to rename {error_msg}")
                    errors.append(error_msg)
            
            # Show result
            if errors:
                error_text = "\n".join(errors[:10])
                if len(errors) > 10:
                    error_text += f"\n...and {len(errors)-10} more errors"
                QMessageBox.warning(
                    self, 
                    "Partial Success", 
                    f"Renamed {success_count}/{len(rename_plan)} files.\n\nErrors:\n{error_text}"
                )
            else:
                QMessageBox.information(self, "Complete", f"Successfully renamed {success_count} file(s).")
            
            # Refresh table
            self.right_panel.populate_table(self.audio_files, self.metadata_manager)
            
            # Reload the current file if needed
            if self.file_path and os.path.exists(self.file_path):
                if self.waveform_controller.enabled:
                    self.audio_controller.load_audio(self.file_path)
                else:
                    file_url = QUrl.fromLocalFile(os.path.abspath(self.file_path))
                    self.audio_controller.player.setSource(file_url)
        else:
            # User cancelled, reload audio if it was playing
            if was_playing and self.file_path:
                if self.waveform_controller.enabled:
                    self.audio_controller.load_audio(self.file_path)
                else:
                    file_url = QUrl.fromLocalFile(os.path.abspath(self.file_path))
                    self.audio_controller.player.setSource(file_url)
                if current_position > 0:
                    self.audio_controller.player.setPosition(current_position)