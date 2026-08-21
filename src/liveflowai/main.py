# src/liveflowai/main.py

import sys
from pathlib import Path
from liveflowai.audio.tempo_analyzer import TempoAnalyzer

def main():
    # Initialize analyzer
    analyzer = TempoAnalyzer(sample_rate=22050)
    
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    AUDIO_DIR = PROJECT_ROOT / "data" / "songs"
    file_path = AUDIO_DIR / "Mary Had a Little Lamb.mp3"
    
    try:
        # Detect tempo
        result = analyzer.detect_tempo(file_path)
        print(f"Tempo: {result['tempo_bpm']:.2f} BPM")
        print(f"Duration: {result['duration']:.2f} seconds")
        print(f"Number of beats: {result['num_beats']}")
        
        # Get confidence metrics
        confidence = analyzer.get_beat_confidence(file_path)
        print(f"Confidence score: {confidence['confidence_score']:.2f}")
        
        # Visualize
        analyzer.visualize_tempo(file_path)
        
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
