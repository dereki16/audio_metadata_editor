"""
Right Panel - File table, waveform, and playback controls
"""
import os
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
    QLabel, QLineEdit, QCheckBox, QTableWidget, QTableWidgetItem, QAbstractItemView, QScrollArea
)
from PySide6.QtCore import Qt, Signal
import pyqtgraph as pg


class RightPanel(QWidget):
    """Right panel with file list, waveform, and controls"""
    
    # Signals
    load_folder_clicked = Signal()
    refresh_clicked = Signal()
    waveform_toggled = Signal(bool)
    waveform_settings_changed = Signal(int, float)  # smoothing, amplitude
    selection_changed = Signal(list)  # list of row indices
    play_pause_clicked = Signal()
    trim_toggled = Signal(bool)
    trim_values_changed = Signal(float, float, float)  # start_sec, end_sec, play_sec
    crop_audio_clicked = Signal()
    table_cell_changed = Signal(int, int, str)  # row, column, new_value
    seek_requested = Signal(float)  # New signal for seeking playback position
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._metadata_manager = None
        self._audio_files = []
        self._drag_start_pos = None
        self._drag_start_range = None

    
    def _setup_ui(self):
        """Initialize UI components"""
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Top controls
        top_controls = QHBoxLayout()
        
        self.load_folder_btn = QPushButton("📂 Load Folder")
        self.load_folder_btn.clicked.connect(self.load_folder_clicked.emit)
        top_controls.addWidget(self.load_folder_btn)
        
        self.refresh_btn = QPushButton("🔄 Refresh")
        self.refresh_btn.setEnabled(False)
        self.refresh_btn.clicked.connect(self.refresh_clicked.emit)
        top_controls.addWidget(self.refresh_btn)
        
        self.waveform_toggle = QCheckBox("Show Waveform")
        self.waveform_toggle.setChecked(False)
        self.waveform_toggle.stateChanged.connect(self._on_waveform_toggled)
        top_controls.addWidget(self.waveform_toggle)
        
        top_controls.addWidget(QLabel("Smooth:"))
        self.smooth_input = QLineEdit("10")
        self.smooth_input.setFixedWidth(50)
        self.smooth_input.editingFinished.connect(self._on_waveform_settings_changed)
        top_controls.addWidget(self.smooth_input)
        
        top_controls.addWidget(QLabel("Height:"))
        self.amplitude_input = QLineEdit("1.0")
        self.amplitude_input.setFixedWidth(50)
        self.amplitude_input.editingFinished.connect(self._on_waveform_settings_changed)
        top_controls.addWidget(self.amplitude_input)
        
        top_controls.addStretch()
        layout.addLayout(top_controls)
        
        # File list
        list_label = QLabel("Audio Files:")
        layout.addWidget(list_label)
        
        self.table = QTableWidget()
        self.table.setColumnCount(11)
        self.table.setHorizontalHeaderLabels([
            "Filename", "Title", "Artist", "Album", "Album Artist",
            "Track", "Disc", "Year", "Genre", "Comment", "Length"
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setDefaultSectionSize(150)
        self.table.setHorizontalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.setVerticalScrollMode(QTableWidget.ScrollPerPixel)
        self.table.itemSelectionChanged.connect(self._on_selection_changed)
        self.table.itemChanged.connect(self._on_table_cell_changed)
        
        # Enable tab key navigation and enter to finish editing
        self.table.setTabKeyNavigation(True)
        
        layout.addWidget(self.table, stretch=3)

        # # Create waveform with custom ViewBox
        # class CustomViewBox(pg.ViewBox):
        #     def __init__(self, *args, **kwargs):
        #         super().__init__(*args, **kwargs)
        #         self._ignore_left_drag = False
        #         self.audio_duration = 0
        #         self._drag_start_pos = None
        #         self._drag_start_range = None

        #     def set_duration(self, duration):
        #         self.audio_duration = duration
            
        #     def mouseDragEvent(self, ev):
        #         dur = self.audio_duration
        #         if dur is None or dur <= 0:
        #             ev.accept()
        #             return

        #         # Start drag
        #         if ev.isStart():
        #             self._drag_start_pos = ev.pos()
        #             self._drag_start_range = self.viewRange()
        #             ev.accept()
        #             return

        #         # Only handle right or middle button drags
        #         if ev.buttons() & (Qt.RightButton | Qt.MiddleButton):
        #             if self._drag_start_pos is None or self._drag_start_range is None:
        #                 ev.ignore()
        #                 return

        #             dx = ev.pos().x() - self._drag_start_pos.x()

        #             (x0, x1), _ = self._drag_start_range
        #             full_width = self.width()

        #             if full_width > 0:
        #                 sec_per_px = (x1 - x0) / full_width
        #                 shift = -dx * sec_per_px

        #                 new_x0 = x0 + shift
        #                 new_x1 = x1 + shift

        #                 # clamp inside duration
        #                 new_x0 = max(0, min(new_x0, dur))
        #                 new_x1 = max(0, min(new_x1, dur))

        #                 self.setXRange(new_x0, new_x1, padding=0)

        #             ev.accept()
        #             return

        #         ev.ignore()

        #     def wheelEvent(self, ev, axis=None):
        #         # Allow normal scroll wheel behavior with axis parameter
        #         super().wheelEvent(ev, axis=axis)

        # self.waveform_plot = pg.PlotWidget(viewBox=CustomViewBox())
        self.waveform_plot = pg.PlotWidget()
        self.waveform_plot.setMenuEnabled(False)
        self.waveform_plot.showButtons()
        self.waveform_plot.showGrid(x=False, y=False, alpha=0.2)
        self.waveform_plot.setBackground("#111")
        self.waveform_plot.setFocusPolicy(Qt.StrongFocus)
        self.waveform_plot.getPlotItem().hideAxis('left')

        # init empty plot handle
        self.waveform_curve = self.waveform_plot.plot([], [], pen=pg.mkPen('#0af', width=1))

        layout.addWidget(self.waveform_plot, stretch=2)
        
        # Playback controls
        playback_frame = QWidget()
        playback_frame.setObjectName("controlFrame")
        playback_layout = QHBoxLayout(playback_frame)
        
        self.play_pause_btn = QPushButton("▶ Play")
        self.play_pause_btn.setObjectName("playButton")
        self.play_pause_btn.clicked.connect(self.play_pause_clicked.emit)
        self.play_pause_btn.setEnabled(False)
        playback_layout.addWidget(self.play_pause_btn)
        
        layout.addWidget(playback_frame)
        
        # Trim controls
        trim_frame = QWidget()
        trim_frame.setObjectName("controlFrame")
        trim_layout = QVBoxLayout(trim_frame)
        
        trim_row = QHBoxLayout()
        self.trim_toggle = QCheckBox("Enable Audio Trimming")
        self.trim_toggle.stateChanged.connect(self._on_trim_toggled)
        trim_row.addWidget(self.trim_toggle)
        
        self.trim_btn = QPushButton("✂️ Crop Audio")
        self.trim_btn.setObjectName("cropButton")
        self.trim_btn.clicked.connect(self.crop_audio_clicked.emit)
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
        dec_start.clicked.connect(lambda: self._bump_start(-1))
        start_row.addWidget(dec_start)
        
        self.start_input = QLineEdit("0:00")
        self.start_input.setObjectName("startInput")
        self.start_input.setFixedWidth(80)
        self.start_input.setAlignment(Qt.AlignCenter)
        self.start_input.editingFinished.connect(self._on_manual_start_input)
        start_row.addWidget(self.start_input)
        
        inc_start = QPushButton("+")
        inc_start.setObjectName("incStart")
        inc_start.setFixedWidth(35)
        inc_start.clicked.connect(lambda: self._bump_start(1))
        start_row.addWidget(inc_start)
        start_row.addStretch()
        # trim_layout.addLayout(start_row)
        
        # End controls
        # end_row = QHBoxLayout()
        end_label = QLabel("End:")
        end_label.setObjectName("endLabel")
        start_row.addWidget(end_label)
        
        dec_end = QPushButton("−")
        dec_end.setObjectName("decEnd")
        dec_end.setFixedWidth(35)
        dec_end.clicked.connect(lambda: self._bump_end(-1))
        start_row.addWidget(dec_end)
        
        self.end_input = QLineEdit("0:00")
        self.end_input.setObjectName("endInput")
        self.end_input.setFixedWidth(80)
        self.end_input.setAlignment(Qt.AlignCenter)
        self.end_input.editingFinished.connect(self._on_manual_end_input)
        start_row.addWidget(self.end_input)
        
        inc_end = QPushButton("+")
        inc_end.setObjectName("incEnd")
        inc_end.setFixedWidth(35)
        inc_end.clicked.connect(lambda: self._bump_end(1))
        start_row.addWidget(inc_end)
        start_row.addStretch()
        trim_layout.addLayout(start_row)
        
        layout.addWidget(trim_frame)
        
        # Store sample rate for conversions
        self._sample_rate = None
        self.duration_seconds = 0

    def _on_table_cell_changed(self, item):
        """Handle table cell edits and save metadata immediately"""
        if not self._metadata_manager or not self._audio_files:
            return
        
        # Don't process if we're currently populating the table
        if self.table.signalsBlocked():
            return
        
        row = item.row()
        column = item.column()
        new_value = item.text().strip()
        
        # Skip if it's the filename or length column (read-only)
        if column == 0 or column == 10:  # Filename or Length columns
            return
        
        if row < len(self._audio_files):
            file_path = self._audio_files[row]
            
            # Map table columns to metadata fields
            field_map = {
                1: 'title',
                2: 'artist', 
                3: 'album',
                4: 'album_artist',
                5: 'track',
                6: 'disc',
                7: 'year',
                8: 'genre',
                9: 'comment'
            }
            
            field_name = field_map.get(column)
            if field_name:
                print(f"Table edit: {os.path.basename(file_path)} - {field_name} = '{new_value}'")
                
                # Read current metadata
                current_metadata = self._metadata_manager.read_metadata(file_path) or {}
                
                # Update only the changed field
                updated_metadata = current_metadata.copy()
                if new_value:  # Only save non-empty values
                    updated_metadata[field_name] = new_value
                else:
                    # If empty, remove the field
                    updated_metadata.pop(field_name, None)
                
                # Save to file immediately
                success = self._metadata_manager.write_metadata(file_path, updated_metadata)
                
                if success:
                    print(f"✓ Successfully saved {field_name} to {os.path.basename(file_path)}")
                    # Emit signal to notify main window
                    self.table_cell_changed.emit(row, column, new_value)
                    
                    # Refresh just this row to ensure display is correct
                    self._refresh_single_row(row)
                else:
                    print(f"✗ Failed to save {field_name} to {os.path.basename(file_path)}")
                    # Revert the cell value if save failed
                    self.table.blockSignals(True)
                    item.setText(current_metadata.get(field_name, ''))
                    self.table.blockSignals(False)

    def _refresh_single_row(self, row):
        """Refresh a single row with updated metadata"""
        if row < len(self._audio_files) and self._metadata_manager:
            path = self._audio_files[row]
            metadata = self._metadata_manager.read_metadata(path)
            
            if metadata:
                values = [
                    os.path.basename(path),
                    metadata.get('title', ''),
                    metadata.get('artist', ''),
                    metadata.get('album', ''),
                    metadata.get('album_artist', ''),
                    metadata.get('track', ''),
                    metadata.get('disc', ''),
                    metadata.get('year', ''),
                    metadata.get('genre', ''),
                    metadata.get('comment', ''),
                    metadata.get('length', '')
                ]
                
                # Block signals to prevent recursive calls
                self.table.blockSignals(True)
                
                for col, val in enumerate(values):
                    # Only update if the value actually changed (to avoid cursor jumping)
                    current_item = self.table.item(row, col)
                    if current_item and current_item.text() != str(val):
                        current_item.setText(str(val))
                
                self.table.blockSignals(False)

    def set_waveform_axis(self, duration_seconds):
        """Set up the X-axis for the waveform based on duration"""
        self.duration_seconds = duration_seconds
        
        vb = self.waveform_plot.getViewBox()
        vb.setLimits(
            xMin=0, xMax=duration_seconds,
            minXRange=duration_seconds,
            maxXRange=duration_seconds
        )
        self.waveform_plot.setXRange(0, duration_seconds, padding=0)

        # Build time-based ticks
        ticks = []
        step = max(1, int(duration_seconds // 6))
        for t in range(0, int(duration_seconds) + 1, step):
            ticks.append((t, f"{t//60}:{t%60:02d}"))

        axis = self.waveform_plot.getPlotItem().getAxis("bottom")
        axis.setTicks([ticks])


    class TrimHandle(pg.GraphicsObject):
        def _find_duration_seconds(self):
            p = self.parentItem()
            while p is not None:
                if hasattr(p, "duration_seconds"):
                    return p.duration_seconds
                p = p.parentItem()
            return None



    def update_waveform_plot(self, samples, duration_seconds):
        """Update the waveform plot with new audio data"""
        self.duration_seconds = duration_seconds

        # Generate x-axis values in seconds (not sample indices)
        num_samples = len(samples)
        x = [i * duration_seconds / num_samples for i in range(num_samples)]

        # Update curve
        self.waveform_curve.setData(x, samples)

        # Update axis
        self.set_waveform_axis(duration_seconds)
    
    def _on_waveform_toggled(self, state):
        """Handle waveform toggle"""
        # state is an int: 0 = unchecked, 2 = checked
        checked = bool(state)
        print(f"Waveform checkbox toggled: state={state}, checked={checked}")
        self.waveform_toggled.emit(checked)
    
    def _on_waveform_settings_changed(self):
        """Handle waveform settings change"""
        try:
            smoothing = max(1, int(self.smooth_input.text()))
            amplitude = max(0.1, float(self.amplitude_input.text()))
            self.waveform_settings_changed.emit(smoothing, amplitude)
        except ValueError:
            pass
    
    def _on_selection_changed(self):
        """Handle table selection change"""
        selected_rows = [idx.row() for idx in self.table.selectionModel().selectedRows()]
        self.selection_changed.emit(selected_rows)
    
    def _on_trim_toggled(self, state):
        """Handle trim toggle"""
        # state is an int: 0 = unchecked, 2 = checked
        checked = bool(state)
        print(f"Trim checkbox toggled: state={state}, checked={checked}")
        self.trim_toggled.emit(checked)
    
    def _format_time(self, seconds):
        """Convert seconds to M:SS format"""
        minutes = int(seconds // 60)
        secs = int(seconds % 60)
        return f"{minutes}:{secs:02d}"
    
    def _parse_time(self, time_str):
        """Convert M:SS format to seconds"""
        try:
            # Handle both "M:SS" and "MM:SS" formats
            if ':' in time_str:
                parts = time_str.split(':')
                minutes = int(parts[0])
                seconds = int(parts[1])
                return minutes * 60 + seconds
            else:
                # Just seconds
                return int(time_str)
        except (ValueError, IndexError):
            return 0
    
    def _on_manual_start_input(self):
        """Handle manual start time input"""
        try:
            start_sec = self._parse_time(self.start_input.text())
            end_sec = self._parse_time(self.end_input.text())
            
            # Update display with formatted time
            self.start_input.setText(self._format_time(start_sec))
            
            self.trim_values_changed.emit(start_sec, end_sec, start_sec)
        except ValueError:
            pass
    
    def _on_manual_end_input(self):
        """Handle manual end time input"""
        try:
            start_sec = self._parse_time(self.start_input.text())
            end_sec = self._parse_time(self.end_input.text())
            
            # Update display with formatted time
            self.end_input.setText(self._format_time(end_sec))
            
            self.trim_values_changed.emit(start_sec, end_sec, start_sec)
        except ValueError:
            pass
    
    def _bump_start(self, direction):
        """Bump start time by 1 second"""
        try:
            current = self._parse_time(self.start_input.text())
            new_val = max(0.0, current + direction)
            self.start_input.setText(self._format_time(new_val))
            end_sec = self._parse_time(self.end_input.text())
            self.trim_values_changed.emit(new_val, end_sec, new_val)
        except ValueError:
            pass
    
    def _bump_end(self, direction):
        """Bump end time by 1 second"""
        try:
            current = self._parse_time(self.end_input.text())
            new_val = max(0.0, current + direction)
            self.end_input.setText(self._format_time(new_val))
            start_sec = self._parse_time(self.start_input.text())
            self.trim_values_changed.emit(start_sec, new_val, start_sec)
        except ValueError:
            pass
    
    def populate_table(self, audio_files, metadata_manager):
        """Populate table with audio files and metadata"""
        # Store references for cell editing
        self._audio_files = audio_files
        self._metadata_manager = metadata_manager
        
        print(f"=== DEBUG POPULATE TABLE ===")
        print(f"Number of files: {len(audio_files)}")
        
        # Block signals during population to prevent false cell change events
        self.table.blockSignals(True)
        
        self.table.setRowCount(len(audio_files))
        
        for row, path in enumerate(audio_files):
            metadata = metadata_manager.read_metadata(path)
            
            print(f"Row {row}: {os.path.basename(path)}")
            if metadata:
                print(f"  Has metadata: {bool(metadata)}")
                print(f"  Title: '{metadata.get('title', '')}'")
                print(f"  Artist: '{metadata.get('artist', '')}'")
            else:
                print(f"  No metadata found")
            
            # Handle missing metadata gracefully
            if not metadata:
                # Create default metadata with filename
                values = [os.path.basename(path)] + [''] * 10
            else:
                values = [
                    os.path.basename(path),
                    metadata.get('title', ''),
                    metadata.get('artist', ''),
                    metadata.get('album', ''),
                    metadata.get('album_artist', ''),
                    metadata.get('track', ''),
                    metadata.get('disc', ''),
                    metadata.get('year', ''),
                    metadata.get('genre', ''),
                    metadata.get('comment', ''),
                    metadata.get('length', '')
                ]
            
            for col, val in enumerate(values):
                item = QTableWidgetItem(str(val))  # Ensure it's a string
                
                # Make filename and length columns read-only
                if col == 0 or col == 10:
                    item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                else:
                    item.setFlags(item.flags() | Qt.ItemIsEditable)
                
                self.table.setItem(row, col, item)
        
        # Unblock signals
        self.table.blockSignals(False)
        
        # Optional: Auto-resize columns to fit content
        self.table.resizeColumnsToContents()
        print("=== END POPULATE TABLE ===\n")
    
    def get_selected_rows(self):
        """Get list of selected row indices"""
        return [idx.row() for idx in self.table.selectionModel().selectedRows()]
    
    def set_current_row(self, row):
        """Set current selected row"""
        self.table.setCurrentCell(row, 0)
    
    def set_play_button_text(self, text):
        """Set play/pause button text"""
        self.play_pause_btn.setText(text)
    
    def enable_play_button(self, enabled):
        """Enable/disable play button"""
        self.play_pause_btn.setEnabled(enabled)
    
    def enable_refresh_button(self, enabled):
        """Enable/disable refresh button"""
        self.refresh_btn.setEnabled(enabled)
    
    def set_trim_times(self, start_sec, end_sec):
        """Set trim time displays in MM:SS.ms format"""
        self.start_input.setText(self._format_time(start_sec))
        self.end_input.setText(self._format_time(end_sec))
    
    def set_sample_rate(self, sample_rate):
        """Store sample rate for conversions"""
        self._sample_rate = sample_rate

    def update_single_row(self, row, file_path, metadata_manager):
        """Update a single row with current metadata"""
        if row < len(self._audio_files) and metadata_manager:
            metadata = metadata_manager.read_metadata(file_path)
            
            if metadata:
                values = [
                    os.path.basename(file_path),
                    metadata.get('title', ''),
                    metadata.get('artist', ''),
                    metadata.get('album', ''),
                    metadata.get('album_artist', ''),
                    metadata.get('track', ''),
                    metadata.get('disc', ''),
                    metadata.get('year', ''),
                    metadata.get('genre', ''),
                    metadata.get('comment', ''),
                    metadata.get('length', '')
                ]
                
                # Block signals to prevent recursive calls
                self.table.blockSignals(True)
                
                for col, val in enumerate(values):
                    # Only update if the value actually changed (to avoid cursor jumping)
                    current_item = self.table.item(row, col)
                    if current_item and current_item.text() != str(val):
                        current_item.setText(str(val))
                
                self.table.blockSignals(False)