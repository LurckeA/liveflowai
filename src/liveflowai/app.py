# src/liveflowai/app.py
import asyncio
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np

from .audio.analyzer import AudioAnalyzer
from .detection.chord_detector import ChordDetector
from .transition.engine import TransitionEngine
from .output.iem_manager import IEMManager

class LiveFlowAI:
    def __init__(self, config_path: Path = Path("config/config.yaml")):
        self.analyzer = AudioAnalyzer()
        self.chord_detector = ChordDetector()
        self.transition_engine = TransitionEngine()
        self.iem_manager = IEMManager()
        self.song_library: Dict[str, dict] = {}
        self.current_song: Optional[Dict] = None
        
    async def run(self):
        """Main loop"""
        # Load song library
        await self.load_song_library("data/songs/")
        
        # Start real-time processing
        while True:
            # Capture live audio
            live_audio = await self.capture_audio()
            
            # Detect chords
            chords = self.chord_detector.detect(live_audio)
            
            # Predict next song
            next_song = self.predict_next_song(chords)
            
            if next_song and self.current_song:
                # Prepare transition
                transition = self.transition_engine.prepare(
                    current_song=self.current_song,
                    next_song=next_song
                )
                
                # Send to IEM
                self.iem_manager.send_transition(transition)
                self.current_song = next_song
    
    async def load_song_library(self, path: str) -> None:
        """Load song library from path"""
        # Simulate async loading
        await asyncio.sleep(0.1)
        # Load some mock songs
        self.song_library = {
            'song1': {'tempo': 120, 'key': 'C', 'energy': 0.7},
            'song2': {'tempo': 128, 'key': 'G', 'energy': 0.8},
        }
        print(f"Loaded {len(self.song_library)} songs")
    
    async def capture_audio(self) -> np.ndarray:
        """Capture live audio"""
        # Simulate audio capture
        await asyncio.sleep(0.1)
        return np.random.randn(44100)  # 1 second of audio
    
    def predict_next_song(self, chords: List[str]) -> Optional[Dict]:
        """Predict next song based on last few chords"""
        if not chords or not self.song_library:
            return None
        # Simple prediction: return first song in library
        return list(self.song_library.values())[0] if self.song_library else None