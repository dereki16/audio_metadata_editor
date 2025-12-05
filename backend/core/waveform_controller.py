"""
Waveform Controller - Handles waveform generation and display
"""
from PySide6.QtCore import QObject, Signal, QTimer
import pyqtgraph as pg
from PySide6.QtCore import Qt
import numpy as np


class WaveformController(QObject):
    """Manages waveform visualization"""
    
    # Signals
    trim_changed = Signal(int, int)  # start_sample, end_sample
    seek_requested = Signal(float)  # position in seconds
    
    def __init__(self, plot_widget=None):
        super().__init__()
        
        self.plot = plot_widget
        self.samples = None
        self.sample_rate = None
        self.duration = 0  # Duration in seconds
        
        # Visual settings
        self.smoothing = 10
        self.amplitude = 1.0
        self.enabled = False
        
        # Playback cursor
        self.play_cursor = pg.InfiniteLine(pos=0, angle=90, movable=True,
                                          pen=pg.mkPen('#44f', width=2))
        self.plot.addItem(self.play_cursor)
        self.play_cursor.hide()
        self.play_cursor.sigDragged.connect(self._on_play_cursor_dragged)
        self._cursor_dragging = False
        self._drag_timer = QTimer()
        self._drag_timer.setSingleShot(True)
        self._drag_timer.timeout.connect(self._end_cursor_drag)
        
        # Trim markers
        self.trim_enabled = False
        self.trim_start = 0
        self.trim_end = 0
        
        self.trim_line_start = pg.InfiniteLine(pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#00ff00', width=3, style=Qt.DashLine))
        self.trim_line_end = pg.InfiniteLine(pos=0, angle=90, movable=True,
            pen=pg.mkPen(color='#ff0000', width=3, style=Qt.DashLine))
        
        self.plot.addItem(self.trim_line_start)
        self.plot.addItem(self.trim_line_end)
        self.trim_line_start.hide()
        self.trim_line_end.hide()
        
        # Connect trim line signals
        self.trim_line_start.sigPositionChanged.connect(self._on_trim_moved)
        self.trim_line_end.sigPositionChanged.connect(self._on_trim_moved)
        
        # Connect click events for seeking
        self.plot.scene().sigMouseClicked.connect(self._on_waveform_clicked)
    
    def set_enabled(self, enabled):
        """Enable or disable waveform display"""
        print(f"WaveformController.set_enabled({enabled}), current enabled={self.enabled}")
        self.enabled = enabled
        if enabled:
            print("Showing waveform plot")
            self.plot.show()
        else:
            print("Hiding waveform plot")
            self.plot.hide()
            self.clear()
    
    def _end_cursor_drag(self):
        """Called after drag timer expires"""
        self._cursor_dragging = False
        print("Cursor drag ended (via timer)")
    
    def set_smoothing(self, value):
        """Set waveform smoothing factor"""
        self.smoothing = max(1, int(value))
    
    def set_amplitude(self, value):
        """Set waveform amplitude multiplier"""
        self.amplitude = max(0.1, float(value))
    
    def load_waveform(self, samples, sample_rate, downsample_factor=1):
        """
        Load and display waveform
        
        Args:
            samples: Audio sample data (numpy array)
            sample_rate: Sample rate in Hz
            downsample_factor: Factor to reduce samples for display
        """
        print(f"WaveformController.load_waveform: {len(samples)} samples, {sample_rate}Hz, enabled={self.enabled}")
        
        self.samples = samples
        self.sample_rate = sample_rate
        self.duration = len(samples) / sample_rate  # Calculate duration in seconds
        
        if not self.enabled:
            print("Waveform not enabled, skipping display")
            return
        
        print(f"Calling display_waveform with factor={downsample_factor}, duration={self.duration:.2f}s")
        self.display_waveform(downsample_factor)
    
    def display_waveform(self, downsample_factor=1):
        """Display the loaded waveform with TIME-BASED x-axis"""
        if self.samples is None or not self.enabled:
            print("Waveform display skipped - samples:", self.samples is not None, "enabled:", self.enabled)
            return
        
        print(f"Displaying waveform: {len(self.samples)} samples, downsample={downsample_factor}")
        
        self.plot.clear()
        
        # Re-add items after clear
        self.plot.addItem(self.play_cursor)
        self.plot.addItem(self.trim_line_start)
        self.plot.addItem(self.trim_line_end)
        
        # Downsample
        downsampled = self.samples[::downsample_factor]
        
        # Apply smoothing
        if self.smoothing > 1:
            kernel = np.ones(self.smoothing) / self.smoothing
            downsampled = np.convolve(downsampled, kernel, mode='same')
        
        # Apply amplitude scaling
        downsampled = downsampled * self.amplitude
        
        # Normalize
        max_val = np.max(np.abs(downsampled))
        if max_val > 0:
            downsampled = downsampled / max_val
        
        # Create TIME-BASED x-axis (in seconds, not samples!)
        num_points = len(downsampled)
        x_seconds = np.linspace(0, self.duration, num_points)
        
        # Plot with time-based x-axis
        pen = pg.mkPen(color=(0, 255, 255), width=1)
        self.plot.plot(x_seconds, downsampled, pen=pen)
        
        # Update axis labels with time formatting
        self._setup_time_axis()
        
        print("Waveform displayed successfully with time-based x-axis")
        
        # Restore trim lines if enabled
        if self.trim_enabled:
            self.trim_line_start.show()
            self.trim_line_end.show()
    
    def _setup_time_axis(self):
        """Setup time-based axis with padding, smart spacing, and clean ticks."""
        if not self.duration:
            return

        dur = float(self.duration)
        vb = self.plot.getViewBox()

        # -------------------------
        # 1. Padding (start/end)
        # -------------------------
        pad = max(dur * 0.05, 0.25)
        start = 0 - pad
        end = dur + pad

        vb.setLimits(
            xMin=start,
            xMax=end,
            minXRange=end - start,
            maxXRange=end - start
        )
        self.plot.setXRange(start, end, padding=0)

        # -------------------------
        # 2. Smart spacing rules
        # -------------------------
        if dur <= 15:
            step = 1
        elif dur <= 30:
            step = 2
        elif dur <= 60:
            step = 5
        elif dur <= 2 * 60:
            step = 10
        elif dur <= 3 * 60:
            step = 15
        elif dur <= 10 * 60:
            step = 30
        else:
            step = 60 

        axis = self.plot.getPlotItem().getAxis("bottom")
        ticks = []

        # -------------------------
        # 3. Generate ticks
        # -------------------------
        t = 0.0
        end_tick_added = False

        while t <= dur + 0.0001:
            # --- ALWAYS show 0:00 ---
            if abs(t) < 0.01:
                label = "0:00"

            # --- TRUE END ONLY: exact dur within float tolerance ---
            elif abs(t - dur) < 0.01:
                m = int(dur // 60)
                s = int(dur % 60)
                label = f"{m}:{s:02d}"
                end_tick_added = True

            # --- Hide labels inside final 5 seconds (but show ticks) ---
            elif dur - 5 <= t < dur:
                label = ""

            else:
                # Normal formatting
                if t < 60:
                    label = f"{int(t)}s"
                else:
                    m = int(t // 60)
                    s = int(t % 60)
                    label = f"{m}:{s:02d}"

            ticks.append((t, label))
            t += step

        # -------------------------
        # 4. Guarantee an end tick at EXACT x = duration
        # -------------------------
        if not end_tick_added:
            m = int(dur // 60)
            s = int(dur % 60)
            ticks.append((dur, f"{m}:{s:02d}"))

        axis.setTicks([ticks])




    
    def refresh(self):
        """Refresh the waveform display with current settings"""
        if self.samples is not None:
            factor = max(1, int(len(self.samples) / 20000))
            self.display_waveform(factor)
    
    def clear(self):
        """Clear the waveform display"""
        self.plot.clear()
        self.samples = None
        self.sample_rate = None
        self.duration = 0
        self._cursor_dragging = False  # Reset drag state
        
        # Re-add items
        self.plot.addItem(self.play_cursor)
        self.plot.addItem(self.trim_line_start)
        self.plot.addItem(self.trim_line_end)
        
        # Hide cursor when clearing
        self.play_cursor.hide()
    
    def _on_play_cursor_dragged(self, line):
        """Handle play cursor drag - emit seek request"""
        if not self.duration:
            return
        
        position_sec = line.value()
        
        # Clamp to valid range
        position_sec = max(0, min(position_sec, self.duration))
        
        # Mark as dragging and restart timer
        self._cursor_dragging = True
        self._drag_timer.start(200)  # End drag 200ms after last movement
        
        # Emit seek request
        print(f"Play cursor dragged to: {position_sec:.2f}s")
        self.seek_requested.emit(position_sec)
    
    def _on_play_cursor_drag_start(self):
        """Mark that cursor is being dragged - NO LONGER USED"""
        pass
    
    def _on_waveform_clicked(self, event):
        """Handle click on waveform to seek"""
        if not self.duration:
            return
        
        # Only respond to left clicks
        if event.button() != Qt.LeftButton:
            return
        
        # Reset dragging flag when clicking (not dragging)
        self._cursor_dragging = False
        
        # Check if click was on the plot area (not on a line or other item)
        items = self.plot.scene().items(event.scenePos())
        # If click hit an InfiniteLine, let it handle the event
        for item in items:
            if isinstance(item, pg.InfiniteLine):
                return
        
        # Get the position in scene coordinates
        vb = self.plot.getViewBox()
        mouse_point = vb.mapSceneToView(event.scenePos())
        
        # Get x position in seconds
        position_sec = mouse_point.x()
        
        # Clamp to valid range
        position_sec = max(0, min(position_sec, self.duration))
        
        # Move play cursor and emit seek
        self.play_cursor.setPos(position_sec)
        print(f"Waveform clicked at: {position_sec:.2f}s")
        self.seek_requested.emit(position_sec)
    
    def update_play_cursor(self, position_ms):
        """Update playback cursor position"""
        if not self.duration:
            return
        
        # Don't update if user is currently dragging the cursor
        if self._cursor_dragging:
            return
        
        # Convert milliseconds to seconds
        position_sec = position_ms / 1000.0
        
        # Update cursor position (in seconds)
        self.play_cursor.setPos(position_sec)
        
        if not self.play_cursor.isVisible():
            self.play_cursor.show()
    
    def hide_play_cursor(self):
        """Hide the playback cursor"""
        self.play_cursor.hide()
    
    def enable_trim(self, enabled):
        """Enable or disable trim markers"""
        print(f"WaveformController.enable_trim({enabled}), samples: {self.samples is not None}, sample_rate: {self.sample_rate}")
        
        self.trim_enabled = enabled
        
        if enabled:
            if self.samples is None:
                print("ERROR: Cannot enable trim - no samples loaded!")
                return False
            
            # Initialize trim positions (in SECONDS)
            self.trim_start = 0
            self.trim_end = len(self.samples)
            
            # Set visual positions in seconds
            start_sec = 0
            end_sec = self.duration
            
            self.trim_line_start.setPos(start_sec)
            self.trim_line_end.setPos(end_sec)
            self.trim_line_start.show()
            self.trim_line_end.show()
            
            print(f"Trim markers set: start={self.trim_start} samples ({start_sec:.2f}s), end={self.trim_end} samples ({end_sec:.2f}s)")
            
            self.trim_changed.emit(self.trim_start, self.trim_end)
            return True
        else:
            self.trim_line_start.hide()
            self.trim_line_end.hide()
            return True
    
    def _on_trim_moved(self):
        """Handle trim line movement"""
        if not self.trim_enabled or self.samples is None:
            return
        
        # Get positions in SECONDS from the lines
        start_sec = self.trim_line_start.value()
        end_sec = self.trim_line_end.value()
        
        # Convert to sample positions
        self.trim_start = self.time_to_samples(start_sec)
        self.trim_end = self.time_to_samples(end_sec)
        
        # Clamp values
        self.trim_start = max(0, self.trim_start)
        self.trim_end = min(len(self.samples), self.trim_end)
        
        # Ensure start < end
        if self.trim_start >= self.trim_end:
            self.trim_end = self.trim_start + 1
            self.trim_line_end.setPos(self.samples_to_time(self.trim_end))
        
        self.trim_changed.emit(self.trim_start, self.trim_end)
    
    def set_trim_start(self, sample_pos):
        """Set trim start position (in samples)"""
        if self.samples is None:
            return
        
        self.trim_start = max(0, min(sample_pos, len(self.samples) - 1))
        
        # Update visual position in SECONDS
        start_sec = self.samples_to_time(self.trim_start)
        self.trim_line_start.setPos(start_sec)
        
        # Ensure start < end
        if self.trim_start >= self.trim_end:
            self.trim_end = self.trim_start + 1
            self.trim_line_end.setPos(self.samples_to_time(self.trim_end))
        
        self.trim_changed.emit(self.trim_start, self.trim_end)
    
    def set_trim_end(self, sample_pos):
        """Set trim end position (in samples)"""
        if self.samples is None:
            return
        
        self.trim_end = max(1, min(sample_pos, len(self.samples)))
        
        # Update visual position in SECONDS
        end_sec = self.samples_to_time(self.trim_end)
        self.trim_line_end.setPos(end_sec)
        
        # Ensure start < end
        if self.trim_end <= self.trim_start:
            self.trim_start = self.trim_end - 1
            self.trim_line_start.setPos(self.samples_to_time(self.trim_start))
        
        self.trim_changed.emit(self.trim_start, self.trim_end)
    
    def get_trim_positions(self):
        """Get current trim positions in samples"""
        return self.trim_start, self.trim_end
    
    def get_trim_times(self):
        """Get current trim positions in seconds"""
        if self.sample_rate is None:
            return 0.0, 0.0
        
        start_sec = self.trim_start / self.sample_rate
        end_sec = self.trim_end / self.sample_rate
        return start_sec, end_sec
    
    def samples_to_time(self, samples):
        """Convert sample position to seconds"""
        if self.sample_rate is None:
            return 0.0
        return samples / self.sample_rate
    
    def time_to_samples(self, seconds):
        """Convert seconds to sample position"""
        if self.sample_rate is None:
            return 0
        return int(seconds * self.sample_rate)