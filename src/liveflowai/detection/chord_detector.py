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
        
        # Simple chord detection using chromagram
        chords = self._simple_chord_detect(audio, 22050)
        
        self.last_chords.append(chords)
        return chords
    
    def _simple_chord_detect(self, y: np.ndarray, sr: int) -> List[str]:
        """Simple chord detection using chroma features"""
        try:
            chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
            # Get the average chroma vector
            chroma_mean = np.mean(chroma, axis=1)
            chord_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
            # Get top 3 chroma features
            top_indices = np.argsort(chroma_mean)[-3:]
            detected_chords = [chord_names[i] for i in top_indices]
            return detected_chords
        except Exception as e:
            print(f"Chord detection error: {e}")
            return ['C', 'G', 'Am']
    
    def get_progression(self) -> List[str]:
        """Get recent chord progression"""
        return list(self.last_chords)