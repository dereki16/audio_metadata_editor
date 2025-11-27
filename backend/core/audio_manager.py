from PySide6.QtCore import QObject, Signal
from pydub import AudioSegment
import numpy as np

# ============================================================
#                       AUDIO MANAGER
# ============================================================
class AudioManager(QObject):
    audioLoaded = Signal(dict)

    def __init__(self):
        super().__init__()
        self.samples = None
        self.sample_rate = None

    def extract_cover(self, audio):
        """Extract album art bytes from Mutagen audio object."""
        if audio is None or audio.tags is None:
            return None
        
        # MP3 (ID3)
        if hasattr(audio.tags, "getall"):
            apic = audio.tags.getall("APIC")
            if apic:
                return apic[0].data
        
        # FLAC
        if hasattr(audio, "pictures") and audio.pictures:
            return audio.pictures[0].data
        
        return None

    def load_audio(self, path):
        """Load audio and produce numpy samples."""
        try:
            audio = AudioSegment.from_file(path)
            samples = np.array(audio.get_array_of_samples())
            
            if audio.channels > 1:
                samples = samples.reshape((-1, audio.channels)).mean(axis=1)
            
            if samples.dtype.kind in ("i", "u"):
                max_val = float(np.iinfo(samples.dtype).max)
                samples = samples.astype(np.float32) / max_val
            
            self.samples = samples
            self.sample_rate = audio.frame_rate
            
            info = {"sampleRate": self.sample_rate, "sampleCount": len(self.samples)}
            self.audioLoaded.emit(info)
            return info
        except Exception as e:
            print("Load error:", e)
            self.samples = None
            self.sample_rate = None
            return None
        