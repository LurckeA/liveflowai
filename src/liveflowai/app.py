# src/liveflowai/app.py
import asyncio
from pathlib import Path
from typing import List, Dict
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
            
            if next_song:
                # Prepare transition
                transition = self.transition_engine.prepare(
                    current_song=self.current_song,
                    next_song=next_song
                )
                
                # Send to IEM
                self.iem_manager.send_transition(transition)
    
    def predict_next_song(self, chords: np.ndarray) -> str:
        """Predict next song based on last few chords"""
        # Implement ML prediction here
        pass