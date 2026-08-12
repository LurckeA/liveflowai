# src/liveflowai/detection/chord_detector.py
import numpy as np
import librosa
from collections import deque
from typing import List, Tuple

class ChordDetector:
    def __init__(self, buffer_size: int = 44100 * 2):  # 2 seconds
        self.buffer = deque(maxlen=buffer_size)
        self.last_chords = deque(maxlen=20)  # Last 20 chord detections
        
    def detect(self, audio_chunk: np.ndarray) -> List[str]:
        """Detect chords from real-time audio"""
        # Append to buffer
        self.buffer.extend(audio_chunk)
        
        if len(self.buffer) < self.buffer.maxlen:
            return []
        
        # Convert buffer to array
        audio = np.array(self.buffer)
        
        # Detect chords using harmonic scope
        from harmonyscope import ChordDetector
        detector = ChordDetector()
        chords = detector.process(audio, 22050)  # Assuming 22.05kHz sample rate
        
        self.last_chords.append(chords)
        return chords
    
    def get_progression(self) -> List[str]:
        """Get recent chord progression"""
        return list(self.last_chords)