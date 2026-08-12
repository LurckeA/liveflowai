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