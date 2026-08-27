# src/liveflowai/main.py

import sys
from pathlib import Path

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.database.database import DatabaseLogic


def main():
    # Initialize analyzer
    analyzer = TempoAnalyzer(sample_rate=22050)
    chord_analyzer = ChordAnalyzer(sample_rate=22050)
    live_detector = LiveChordDetector(sample_rate=22050)

    

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

        # ADDED: Detect chords
        chords = chord_analyzer.analyze_chords(file_path)

        print("\nDetected Chords:")
        for chord in chords:
            print(
                f"{chord.timestamp:.2f}s - "
                f"{chord.timestamp + chord.duration:.2f}s: "
                f"{chord} "
                f"(confidence: {chord.confidence:.2%})"
            )

        # ADDED: Convert chords for database storage
        chords_string = ", ".join(str(chord) for chord in chords)
        
        # Visualize
        analyzer.visualize_tempo(file_path)
        
        live_detector.start_detection()
        
        # Database Logic
        DB = DatabaseLogic()
        DB.ConnectDB()
        DB.MakeDB()
        DB.PushDB(
            file_path.name, 
            result['duration'], 
            result['tempo_bpm'], 
            chords_string  
        )

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
