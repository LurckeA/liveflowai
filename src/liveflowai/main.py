# src/liveflowai/main.py

import sys
from pathlib import Path

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.database.database import DatabaseLogic

def main():
    # Initialize analyzer
    analyzer = TempoAnalyzer(sample_rate=22050)
    chord_analyzer = ChordAnalyzer(sample_rate=22050)  # NEW
    chord_detector = LiveChordDetector(sample_rate=22050)  # NEW
    
    PROJECT_ROOT = Path(__file__).resolve().parents[2]    def FetchAllDB(self):
        try:
            with self.ConnectDB() as conn:
                c = conn.cursor()
                
                c.execute('SELECT * FROM liveflow')
                results = c.fetchall()
                
                
                if results:
                    print(f"Found {len(results)} result(s):")
                    for row in results:
                        print(f"  Song: {row[0]}, Duration: {row[1]}, BPM: {row[2]}, Chords: {row[3]}")
                else:
                    print(f"Nothing in database.")
                
                return results
                
        except Exception as e:
            print(f"Error fetching from DB: {e}")
            return []  # Return empty list instead of exiting
    AUDIO_DIR = PROJECT_ROOT / "data" / "songs"
    file_path = AUDIO_DIR / "Mary Had a Little Lamb.mp3"
    
    try:
        # User Greeting
        print("LIVEFLOWAI")
        print("Select your option.")
        print("1. Select Audio Files to analyze.") # Audio file selector works here along with chord analyzer and tempo analyzer with the selected audio file selector. After analyzing, push every results into database with DatabaseLogic
        print("2. Show selected Audio Files.") # Fetch everything stored in database with DatabaseLogic
        print("3. Start Playing.") # ChordDetector works with DatabaseLogic.
        user = int(input(""))

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

         # Detect chords  # NEW
        chords, timestamps = chord_analyzer.detect_from_file(file_path)  # NEW
        
        print("\nDetected chords:")  # NEW 
        for chord, timestamp in zip(chords, timestamps):  # NEW
            print(f"{timestamp:.2f}s: {chord}")  # NEW
        chords_string = ', '.join(chords)
        
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

        # Fetch all in Database
        

        # Detect chords live from microphone
        chord_analyzer.start_analyzer()

        print("\nAnalyzing chord changes...")

        chord_changes = chord_analyzer.analyze_file(file_path)

        chords = [change["chord"] for change in chord_changes]

        print("\nDetected chord changes:")

        for change in chord_changes:
            print(
                f"{change['start_time']:.2f}s - "
                f"{change['end_time']:.2f}s: "
                f"{change['chord']} "
                f"({change['confidence']:.2%})"
            )
                    # Detect chords
        chords, timestamps = chord_detector.detect_from_file(file_path)
        
        print("\nDetected chords:")
        for chord, timestamp in zip(chords, timestamps):
            print(f"{timestamp:.2f}s: {chord}")


    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
