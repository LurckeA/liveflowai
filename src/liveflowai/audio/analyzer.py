# src/liveflowai/audio/analyzer.py
import librosa
import numpy as np
from pathlib import Path
from typing import Dict, Tuple, Optional

class AudioAnalyzer:
    def __init__(self):
        self.song_features = {}
        
    def analyze_song(self, audio_path: Path) -> Dict:
        """Analyze song and extract features"""
        y, sr = librosa.load(audio_path, sr=22050)
        
        return {
            'tempo': librosa.beat.tempo(y=y, sr=sr)[0],
            'key': self.detect_key(y, sr),
            'chord_progression': self.extract_chords(y, sr),
            'energy': self.extract_energy(y),
            'sections': self.detect_sections(y, sr),
            'bpm_curve': self.calculate_bpm_curve(y, sr)
        }
    
    def detect_key(self, y: np.ndarray, sr: int) -> str:
        """Detect musical key using chromagram"""
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        # Simple key detection
        return self._key_from_chroma(chroma)
    
    def extract_chords(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Extract chord progression"""
        # Use simple chroma-based chord detection
        chroma = librosa.feature.chroma_cqt(y=y, sr=sr)
        return np.mean(chroma, axis=1)
    
    def calculate_bpm_curve(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Calculate BPM variations over time"""
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
        return tempo
    
    def extract_energy(self, y: np.ndarray) -> float:
        """Extract energy from audio"""
        return float(np.sqrt(np.mean(y**2)))
    
    def detect_sections(self, y: np.ndarray, sr: int) -> list:
        """Detect song sections using librosa"""
        # Simple section detection based on spectral clustering
        S = librosa.feature.melspectrogram(y=y, sr=sr)
        sync = librosa.util.sync(
            np.vstack([librosa.feature.tempogram(y=y, sr=sr)]),
            librosa.frames_to_time(np.arange(0, S.shape[1]), sr=sr)
        )
        # Return simple frame-based sections
        return [y[i*sr:(i+1)*sr] for i in range(len(y)//sr)][:5]  # Limit to 5 sections
    
    def _key_from_chroma(self, chroma: np.ndarray) -> str:
        """Detect key from chromagram"""
        key_names = ['C', 'C#', 'D', 'D#', 'E', 'F', 'F#', 'G', 'G#', 'A', 'A#', 'B']
        chroma_mean = np.mean(chroma, axis=1)
        detected_key = key_names[np.argmax(chroma_mean)]
        return detected_key