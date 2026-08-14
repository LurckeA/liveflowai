# src/liveflowai/transition/engine.py
import numpy as np
from scipy import signal
from typing import Dict, Tuple
import librosa

class TransitionEngine:
    def __init__(self):
        self.transition_time = 0.5  # seconds
        self.crossfade_curve = None
        
    def prepare(self, current_song: Dict, next_song: Dict) -> Dict:
        """Prepare transition between two songs"""
        # Calculate BPM difference
        bpm_diff = abs(current_song['tempo'] - next_song['tempo'])
        
        # Match BPM if needed
        if bpm_diff > 5:
            bpm_shift = self.calculate_bpm_shift(
                current_song['tempo'], 
                next_song['tempo']
            )
        
        # Prepare EQ matching
        eq_profile = self.match_eq(
            current_song['energy'],
            next_song['energy']
        )
        
        # Generate crossfade
        crossfade = self.generate_crossfade(
            current_song['sections'][-1],
            next_song['sections'][0]
        )
        
        return {
            'bpm_shift': bpm_shift if 'bpm_shift' in locals() else 0,
            'eq_profile': eq_profile,
            'crossfade': crossfade,
            'timing_offset': self.calculate_timing(current_song, next_song)
        }
    
    def generate_crossfade(self, current_section: np.ndarray, 
                          next_section: np.ndarray) -> np.ndarray:
        """Generate smooth crossfade between sections"""
        # Simple linear crossfade
        fade_length = int(self.transition_time * 44100)
        fade_in = np.linspace(0, 1, fade_length)
        fade_out = np.linspace(1, 0, fade_length)
        
        # Apply to sections
        mixed = current_section[:fade_length] * fade_out + \
                next_section[:fade_length] * fade_in
        
        return mixed
    
    def calculate_bpm_shift(self, current_bpm: float, target_bpm: float) -> float:
        """Calculate BPM shift ratio for tempo matching"""
        if current_bpm == 0:
            return 0.0
        return target_bpm / current_bpm
    
    def match_eq(self, current_energy: float, target_energy: float) -> Dict:
        """Match EQ profiles between songs"""
        energy_ratio = target_energy / (current_energy + 1e-6)
        return {
            'gain': np.clip(energy_ratio, 0.5, 2.0),
            'curve': 'smooth'
        }
    
    def calculate_timing(self, current_song: Dict, next_song: Dict) -> float:
        """Calculate timing offset for smooth transition"""
        # Simple timing based on song durations
        current_duration = current_song.get('duration', 180.0)
        return self.transition_time