"""
Main Window - Coordinates all components
"""
import os
from io import BytesIO
from PySide6.QtWidgets import QWidget, QHBoxLayout, QFileDialog, QMessageBox
from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QPixmap
from PySide6.QtMultimedia import QMediaPlayer
from PIL import Image
from PIL.ImageQt import ImageQt
from mutagen import File as MutagenFile

from core.audio_controller import AudioController
from core.metadata_manager import MetadataManager
from core.waveform_controller import WaveformController
from ui.left_panel import LeftPanel
from ui.right_panel import RightPanel
from ui.genre_manager import GenreManager
from utils.title_cleaner import TitleCleaner
from .album_editor import AlbumCoverEditor


class MainWindow(QWidget):
    """Main application window"""
    
    def __init__(self):
        super().__init__()
        
        self.setWindowTitle("Sound Simulation")
        self.setGeometry(100, 100, 1400, 800)
        self.setFocusPolicy(Qt.StrongFocus)
        
        # State
        self.audio_files = []
        self.current_folder = None
        self.file_path = None
        self.new_cover_bytes = None
        
        # Controllers
        self.audio_controller = AudioController()
        self.metadata_manager = MetadataManager()
        
        # Load stylesheet
        self._load_stylesheet()
        
        # Setup UI
        self._setup_ui()
        self._connect_signals()
    
    def _load_stylesheet(self):
        """Load external QSS stylesheet"""
        try:
            style_path = os.path.join(os.path.dirname(__file__), '..', 'styles.qss')
            with open(style_path, 'r') as f:
                self.setStyleSheet(f.read())
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
        # self.left_panel.save_clicked.connect(self.save_metadata)
        self.left_panel.field_changed.connect(self._on_left_field_changed)
        
        # Right panel signals
        self.right_panel.load_folder_clicked.connect(self.load_folder)
        self.right_panel.refresh_clicked.connect(self.refresh_folder)
        self.right_panel.waveform_toggled.connect(self.toggle_waveform)
        self.right_panel.waveform_settings_changed.connect(self.update_waveform_settings)
        self.right_panel.selection_changed.connect(self.on_selection_changed)
        self.right_panel.play_pause_clicked.connect(self.audio_controller.toggle_play_pause)
        self.right_panel.trim_toggled.connect(self.on_trim_toggled)
        self.right_panel.trim_values_changed.connect(self.on_trim_values_changed)
        self.right_panel.crop_audio_clicked.connect(self.crop_audio)
        self.right_panel.table_cell_changed.connect(self._on_right_cell_changed)

        
        # Audio controller signals
        self.audio_controller.position_changed.connect(self.waveform_controller.update_play_cursor)
        self.audio_controller.playback_state_changed.connect(self.on_playback_state_changed)
        self.audio_controller.audio_loaded.connect(self.on_audio_loaded)
        
        # In _connect_signals method, add:
        self.waveform_controller.seek_requested.connect(self.audio_controller.seek_to_position)
        # Waveform controller signals
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

            if new_value.strip():
                metadata[field_name] = new_value.strip()
            else:
                metadata.pop(field_name, None)

            self.metadata_manager.write_metadata(file_path, metadata)

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

        if new_value.strip():
            metadata[field] = new_value.strip()
        else:
            metadata.pop(field, None)

        # Save metadata
        self.metadata_manager.write_metadata(file_path, metadata)

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
            
            trimmed_path = self.audio_controller.crop_audio(self.file_path, start_sample, end_sample)
            
            # Add to file list
            self.audio_files.append(trimmed_path)
            self.right_panel.populate_table(self.audio_files, self.metadata_manager)
            
            QMessageBox.information(self, "Saved", f"Trimmed audio saved to:\n{trimmed_path}")
            
        except Exception as e:
            import traceback
            traceback.print_exc()
            QMessageBox.critical(self, "Trim Error", f"Failed to trim audio: {e}")
    
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
        """Auto-clean titles"""
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return
        
        selected_paths = [self.audio_files[row] for row in selected_rows]
        ui_artist = self.left_panel.artist_input.text().strip()
        
        cleaned_data = TitleCleaner.batch_clean_titles(
            selected_paths, self.metadata_manager, ui_artist
        )
        
        # Show preview
        preview = []
        for path, data in cleaned_data.items():
            ft_preview = f" (ft: {data['composer']})" if data['composer'] else ""
            preview.append(f"{os.path.basename(path)}\n  → {data['title']}{ft_preview}")
        
        preview_text = "\n\n".join(preview[:50])
        if len(preview) > 50:
            preview_text += f"\n\n...and {len(preview)-50} more"
        
        msg = QMessageBox(self)
        msg.setWindowTitle("Cleanup Preview")
        msg.setText(f"Preview of cleaned titles for {len(preview)} files:")
        msg.setDetailedText(preview_text)
        msg.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
        
        if msg.exec() == QMessageBox.Ok:
            saved = TitleCleaner.apply_cleaned_titles(cleaned_data)
            QMessageBox.information(self, "Complete", f"Cleaned {saved} files.")
            
            # Refresh if single file
            if len(selected_rows) == 1:
                self._load_metadata_only(self.file_path)

    def save_metadata(self):
        """Save metadata to selected files"""
        selected_rows = self.right_panel.get_selected_rows()
        if not selected_rows:
            QMessageBox.information(self, "Info", "Select at least one file first.")
            return
        
        metadata = self.left_panel.get_metadata()
        
        print(f"Saving metadata: {metadata}")
        
        # Confirm batch save
        if len(selected_rows) > 1:
            details = []
            for key, val in metadata.items():
                if val:
                    details.append(f"• {key.replace('_', ' ').title()}: '{val}'")
                else:
                    details.append(f"• {key.replace('_', ' ').title()}: (will be cleared)")
            
            if self.new_cover_bytes:
                details.append("• Album Art: (new image)")
            
            msg = QMessageBox(self)
            msg.setWindowTitle("Batch Save")
            msg.setText(f"Save to {len(selected_rows)} files?")
            msg.setInformativeText("\n".join(details) if details else "No changes detected")
            msg.setStandardButtons(QMessageBox.Save | QMessageBox.Cancel)
            
            if msg.exec() != QMessageBox.Save:
                return
        
        # Save to all selected files
        selected_paths = [self.audio_files[row] for row in selected_rows]
        
        success_count = 0
        for path in selected_paths:
            # Include ALL fields (even blank ones) to allow clearing
            file_metadata = metadata.copy()
            print(f"Saving to {os.path.basename(path)}: {file_metadata}")
            
            # Use allow_blanks=True to enable clearing fields
            if self.metadata_manager.write_metadata(path, file_metadata, self.new_cover_bytes, allow_blanks=True):
                success_count += 1
        
        QMessageBox.information(self, "Saved", f"Metadata saved to {success_count}/{len(selected_paths)} file(s).")
        
        # Clear new cover bytes after saving
        self.new_cover_bytes = None
        
        # Refresh table
        self.right_panel.populate_table(self.audio_files, self.metadata_manager)


    # Also update _on_left_field_changed to allow blanks:
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


    # Update _on_right_cell_changed similarly:
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


                ### WORKING CODE ###