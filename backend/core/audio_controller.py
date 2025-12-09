"""
Audio Controller - Handles audio playback, loading, and trimming operations
WITH FFMPEG CONSOLE WINDOW FIX
"""
from PySide6.QtCore import QObject, Signal, QUrl
from PySide6.QtMultimedia import QMediaPlayer, QAudioOutput
import numpy as np
from mutagen import File as MutagenFile
from mutagen.id3 import ID3, APIC, ID3NoHeaderError
from mutagen.easyid3 import EasyID3
from mutagen.flac import FLAC, Picture
from mutagen.mp4 import MP4, MP4Cover
import os
import sys
import subprocess

# ============================================================
# CRITICAL: Hide FFmpeg console window on Windows
# This MUST be at module level before pydub import
# ============================================================
if sys.platform == 'win32':
    import subprocess
    
    # Save original subprocess.Popen
    _original_subprocess_popen = subprocess.Popen
    
    # Create wrapper that always hides console
    class _PopenWrapper:
        def __init__(self, *args, **kwargs):
            # Force startupinfo with hidden window
            if 'startupinfo' not in kwargs:
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                kwargs['startupinfo'] = startupinfo
            
            # Force creationflags to hide window
            if 'creationflags' not in kwargs:
                kwargs['creationflags'] = 0
            kwargs['creationflags'] |= subprocess.CREATE_NO_WINDOW
            
            # Call original Popen
            self._process = _original_subprocess_popen(*args, **kwargs)
        
        def __getattr__(self, name):
            return getattr(self._process, name)
    
    # Replace subprocess.Popen globally
    subprocess.Popen = _PopenWrapper

# NOW import pydub (will use our patched subprocess)
from pydub import AudioSegment
# ============================================================

class AudioController(QObject):
    """Manages audio playback, loading, and trimming"""
    
    # Signals
    position_changed = Signal(int)  # milliseconds
    playback_state_changed = Signal(object)  # QMediaPlayer.PlaybackState
    audio_loaded = Signal(dict)  # info dict with samples, sample_rate, duration
    
    def __init__(self):
        super().__init__()
        
        # Playback
        self.player = QMediaPlayer()
        self.audio_output = QAudioOutput()
        self.player.setAudioOutput(self.audio_output)
        
        # Connect signals
        self.player.positionChanged.connect(self.position_changed.emit)
        self.player.playbackStateChanged.connect(self.playback_state_changed.emit)
        
        # Audio data
        self.samples = None
        self.sample_rate = None
        self.current_file = None
        self.duration_seconds = 0
    
    def load_audio(self, file_path):
        """Load audio file and extract waveform data"""
        try:
            print(f"Loading audio: {file_path}")
            
            # This now uses our hidden subprocess wrapper
            audio = AudioSegment.from_file(file_path)
            self.samples = np.array(audio.get_array_of_samples(), dtype=np.float32)
            
            # Convert to mono if stereo
            if audio.channels == 2:
                self.samples = self.samples.reshape((-1, 2)).mean(axis=1)
            
            self.sample_rate = audio.frame_rate
            self.current_file = file_path
            self.duration_seconds = len(self.samples) / self.sample_rate
            
            print(f"Loaded {len(self.samples)} samples at {self.sample_rate}Hz")
            
            # Set up playback
            file_url = QUrl.fromLocalFile(os.path.abspath(file_path))
            self.player.setSource(file_url)
            
            info = {
                'samples': self.samples,
                'sample_rate': self.sample_rate,
                'duration': self.duration_seconds,
                'channels': audio.channels
            }
            
            self.audio_loaded.emit(info)
            return info
            
        except Exception as e:
            print(f"Error loading audio: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def play(self):
        """Start playback"""
        print(f"play() called - source empty: {self.player.source().isEmpty()}")
        self.player.play()
    
    def pause(self):
        """Pause playback"""
        self.player.pause()
    
    def stop(self):
        """Stop playback and reset position"""
        self.player.stop()

    def is_playing(self):
        """Check if audio is currently playing"""
        return self.player.playbackState() == QMediaPlayer.PlayingState
    
    def get_position_ms(self):
        """Get current playback position in milliseconds"""
        return self.player.position()
    
    def get_duration_ms(self):
        """Get total duration in milliseconds"""
        return self.player.duration()
    
    def clear_audio(self):
        """Clear loaded audio data"""
        self.stop()
        self.samples = None
        self.sample_rate = None
        self.current_file = None
        self.duration_seconds = 0
        self.player.setSource(QUrl())

    def seek_to_position(self, seconds):
        """Seek to a specific position in seconds"""
        if not self.player:
            print("No player available")
            return
        
        # Check if source is loaded
        if self.player.source().isEmpty():
            print("No audio source loaded")
            return
        
        position_ms = int(seconds * 1000)
        print(f"AudioController: Seeking to {seconds:.2f}s ({position_ms}ms)")
        
        # Set position
        self.player.setPosition(position_ms)
        
        # If not playing, start playback
        if self.player.playbackState() == QMediaPlayer.StoppedState:
            print("Audio was stopped, starting playback")
            self.player.play()

    def toggle_play_pause(self):
        """Toggle between play and pause"""
        if not self.player:
            print("No player available")
            return
            
        if self.player.source().isEmpty():
            print("No audio source loaded in player")
            return
        
        current_state = self.player.playbackState()
        print(f"Current playback state: {current_state}")
        
        if current_state == QMediaPlayer.PlayingState:
            print("Pausing playback")
            self.player.pause()
        else:
            print("Starting/resuming playback")
            self.player.play()
    
    def crop_audio(self, file_path, trim_start_samples, trim_end_samples, overwrite_original=False):
        """Trim audio file, optionally overwriting original, preserving metadata correctly."""

        if not self.sample_rate:
            raise ValueError("No audio loaded for trimming")

        # Convert samples -> ms
        start_ms = int((trim_start_samples / self.sample_rate) * 1000)
        end_ms = int((trim_end_samples / self.sample_rate) * 1000)
        if start_ms >= end_ms:
            raise ValueError("Start time must be before end time")

        base, ext = os.path.splitext(file_path)
        save_path = file_path if overwrite_original else f"{base}_trimmed{ext}"

        # --- Read original metadata BEFORE we touch the file ---
        try:
            original_easy = MutagenFile(file_path, easy=True)   # easy tags (dict-like) for many formats
        except Exception:
            original_easy = None

        # extract cover bytes (works for mp3/flac/mp4)
        try:
            original_full = MutagenFile(file_path, easy=False)
        except Exception:
            original_full = None

        cover_bytes = None
        try:
            cover_bytes = self._extract_cover(original_full) if original_full else None
        except Exception:
            cover_bytes = None

        # Load and trim audio (this step will overwrite metadata if we write to same file)
        audio_segment = AudioSegment.from_file(file_path)
        trimmed = audio_segment[start_ms:end_ms]

        # Determine export format
        format_map = {
            ".mp3": "mp3",
            ".wav": "wav",
            ".flac": "flac",
            ".ogg": "ogg",
            ".m4a": "mp4",
        }
        export_format = format_map.get(ext.lower())
        if not export_format:
            raise ValueError(f"Unsupported format: {ext}")

        # Preserve bitrate for MP3 if available
        kwargs = {}
        try:
            orig_meta_for_bitrate = MutagenFile(file_path)
            if hasattr(orig_meta_for_bitrate, "info") and hasattr(orig_meta_for_bitrate.info, "bitrate"):
                kwargs["bitrate"] = f"{orig_meta_for_bitrate.info.bitrate // 1000}k"
        except Exception:
            pass

        # Export trimmed audio (this will replace file if overwrite_original=True)
        trimmed.export(save_path, format=export_format, **kwargs)

        # --- Restore metadata according to format ---
        try:
            lower_ext = ext.lower()
            if lower_ext == ".mp3":
                # original_easy may be EasyID3-like or None
                self._copy_mp3_metadata(save_path, original_easy, cover_bytes)
            elif lower_ext == ".flac":
                self._copy_flac_metadata(save_path, original_easy, cover_bytes)
            elif lower_ext in (".m4a", ".mp4"):
                self._copy_m4a_metadata(save_path, original_easy, cover_bytes)
            else:
                # generic fallback - write common tags back
                self._copy_generic_metadata(save_path, original_easy)
        except Exception as e:
            print(f"Warning: failed to restore metadata after trimming: {e}")

        print(f"Audio trimmed {'(overwritten original)' if overwrite_original else '(new copy)'}: {save_path}")
        return save_path

    
    def _copy_metadata(self, src, dst):
        """Copy metadata from src → dst, supporting MP3, FLAC, WAV, etc."""
        try:
            original = MutagenFile(src, easy=False)
            target = MutagenFile(dst, easy=False)

            if not original:
                print("No original metadata found.")
                return

            # ---------- MP3 (ID3 Tags) ----------
            if isinstance(original, ID3):
                target.clear()   # wipe auto-generated tags
                for key, frame in original.items():
                    target.add(frame)  # add actual ID3 frame
                target.save(v2_version=3)
                print("ID3 metadata copied.")
                return

            # ---------- Non-MP3 (FLAC, OGG, M4A, WAV) ----------
            if original.tags:
                target.tags = original.tags
                target.save()
                print("Non-MP3 metadata copied.")

        except Exception as e:
            print(f"Metadata copy failed: {e}")

    def _extract_cover(self, audio_file):
        """Extract album art from audio file"""
        try:
            # MP3
            if hasattr(audio_file, 'tags') and audio_file.tags:
                for key in audio_file.tags.keys():
                    if key.startswith('APIC'):
                        return audio_file.tags[key].data
            
            # FLAC
            if hasattr(audio_file, 'pictures') and audio_file.pictures:
                return audio_file.pictures[0].data
            
            # MP4/M4A
            if hasattr(audio_file, 'tags') and 'covr' in audio_file.tags:
                return bytes(audio_file.tags['covr'][0])
                
        except Exception as e:
            print(f"Cover extraction error: {e}")
        
        return None
    
    def _copy_mp3_metadata(self, dest_path, original_easy, cover_data):
        """Copy metadata for MP3 files"""
        try:
            # Ensure ID3 header exists
            try:
                id3 = ID3(dest_path)
            except ID3NoHeaderError:
                id3 = ID3()
                id3.save(dest_path)
            
            # Copy text tags
            easy_new = EasyID3(dest_path)
            for key in ["title", "artist", "album", "composer", "genre", "date", "tracknumber", "discnumber"]:
                if original_easy and key in original_easy:
                    easy_new[key] = original_easy.get(key)
            easy_new.save()
            
            # Copy cover art
            if cover_data:
                id3 = ID3(dest_path)
                for k in list(id3.keys()):
                    if k.startswith("APIC"):
                        del id3[k]
                id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data))
                id3.save(v2_version=3)
        except Exception as e:
            print(f"MP3 metadata error: {e}")
    
    def _copy_flac_metadata(self, dest_path, original_easy, cover_data):
        """Copy metadata for FLAC files"""
        try:
            fl = FLAC(dest_path)
            if original_easy:
                for key in ["title", "artist", "album", "composer", "genre", "date", "tracknumber", "discnumber"]:
                    if key in original_easy:
                        fl[key] = original_easy.get(key)
            if cover_data:
                pic = Picture()
                pic.data = cover_data
                pic.type = 3
                pic.mime = "image/jpeg"
                fl.clear_pictures()
                fl.add_picture(pic)
            fl.save()
        except Exception as e:
            print(f"FLAC metadata error: {e}")
    
    def _copy_m4a_metadata(self, dest_path, original_easy, cover_data):
        """Copy metadata for M4A files"""
        try:
            mp4 = MP4(dest_path)
            if original_easy:
                tag_map = {
                    "title": "\xa9nam",
                    "artist": "\xa9ART",
                    "album": "\xa9alb",
                    "genre": "\xa9gen",
                    "date": "\xa9day",
                    "tracknumber": "trkn",
                    "discnumber": "disk",
                }
                for key, mp4k in tag_map.items():
                    if key in original_easy:
                        value = original_easy.get(key)
                        if mp4k in ("trkn", "disk"):
                            try:
                                val = original_easy.get(key)[0]
                                if "/" in val:
                                    nums = val.split("/")
                                    mp4[mp4k] = [(int(nums[0]), int(nums[1]) if len(nums) > 1 else 0)]
                                else:
                                    mp4[mp4k] = [(int(val), 0)]
                            except Exception:
                                pass
                        else:
                            mp4[mp4k] = value
            if cover_data:
                mp4["covr"] = [MP4Cover(cover_data, imageformat=MP4Cover.FORMAT_JPEG)]
            mp4.save()
        except Exception as e:
            print(f"MP4 metadata error: {e}")
    
    def _copy_generic_metadata(self, dest_path, original_easy):
        """Copy metadata for other formats"""
        try:
            newfile = MutagenFile(dest_path, easy=False)
            if newfile and original_easy:
                for key in ["title", "artist", "album", "composer", "genre", "date", "tracknumber", "discnumber"]:
                    if key in original_easy:
                        newfile[key] = original_easy.get(key)
                newfile.save()
        except Exception as e:
            print(f"Generic metadata error: {e}")