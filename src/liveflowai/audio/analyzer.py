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
        # Use harmonic scope or implement chord detection
        from harmonyscope import ChordDetector
        detector = ChordDetector()
        chords = detector.process(y, sr)
        return chords
    
    def calculate_bpm_curve(self, y: np.ndarray, sr: int) -> np.ndarray:
        """Calculate BPM variations over time"""
        tempo, beats = librosa.beat.beat_track(y=y, sr=sr, units='time')
        return tempo