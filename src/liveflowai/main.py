# src/liveflowai/main.py

import sys
from pathlib import Path

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.database.database import DatabaseLogic


def analyze_audio_file(file_path, analyzer, chord_analyzer, db):
    """Analyze a single audio file and store results in database."""
    try:
        # Detect tempo
        tempo_result = analyzer.detect_tempo(file_path)
        print(f"\nAnalyzing: {file_path.name}")
        print(f"Tempo: {tempo_result['tempo_bpm']:.2f} BPM")
        print(f"Duration: {tempo_result['duration']:.2f} seconds")
        print(f"Number of beats: {tempo_result['num_beats']}")
        
        # Get confidence metrics
        confidence = analyzer.get_beat_confidence(file_path)
        print(f"Confidence score: {confidence['confidence_score']:.2f}")
        
        # Detect chords
        chords = chord_analyzer.analyze_chords(file_path)
        print("\nDetected Chords:")
        for chord in chords:
            print(
                f"{chord.timestamp:.2f}s - "
                f"{chord.timestamp + chord.duration:.2f}s: "
                f"{chord} "
                f"(confidence: {chord.confidence:.2%})"
            )
        
        # Convert chords for database storage
        chords_string = ", ".join(str(chord) for chord in chords)
        
        # Visualize tempo
        analyzer.visualize_tempo(file_path)
        
        # Push to database
        db.PushDB(
            file_path.name, 
            tempo_result['duration'], 
            tempo_result['tempo_bpm'], 
            chords_string
        )
        
        print(f"✓ Successfully analyzed and stored: {file_path.name}\n")
        return True
        
    except Exception as e:
        print(f"✗ Error analyzing {file_path.name}: {e}\n")
        return False

def show_audio_files(db):
    """Display all audio files stored in the database."""

    try:
        files = db.FetchAllDB()

        if not files:
            print("\nNo audio files found in database.\n")
            return

        print("\n=== Stored Audio Files ===")

        for i, file in enumerate(files, 1):
            song = file[0]
            duration = file[1]
            bpm = file[2]
            chords = file[3]

            print(
                f"{i}. {song} - "
                f"{bpm:.2f} BPM - "
                f"{duration:.2f}s"
            )
            print(f"   Chords: {chords}\n")

    except Exception as e:
        print(f"Error fetching files: {e}\n")

def start_live_detection(chord_detector, db):
    """Start live chord detection from microphone."""
    try:
        print("\n=== Starting Live Chord Detection ===")
        print("Press Ctrl+C to stop...\n")
        chord_detector.start_detection()
    except KeyboardInterrupt:
        print("\nLive detection stopped.")
    except Exception as e:
        print(f"Error in live detection: {e}")


def main():
    # Initialize analyzers
    SAMPLE_RATE = 22050
    analyzer = TempoAnalyzer(sample_rate=SAMPLE_RATE)
    chord_analyzer = ChordAnalyzer(sample_rate=SAMPLE_RATE)
    chord_detector = LiveChordDetector(sample_rate=SAMPLE_RATE)
    audio_selector = AudioFileSelector()
    
    # Setup paths
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    AUDIO_DIR = PROJECT_ROOT / "data" / "songs"
    default_file = AUDIO_DIR / "Mary Had a Little Lamb.mp3"
    
    # Initialize database
    db = DatabaseLogic()
    db.ConnectDB()
    db.MakeDB()
    
    print("\n=== LIVEFLOWAI ===")
    
    while True:
        try:
            print("\nSelect your option:")
            print("1. Analyze Audio Files")
            print("2. Show Analyzed Audio Files")
            print("3. Start Live Chord Detection")
            print("4. Exit")
            
            user_input = input("Enter your choice (1-4): ").strip()
            
            if user_input == "1":
                # Option 1: Analyze audio files
                print("\nSelect audio files to analyze:")
                print("1. Use default file (Mary Had a Little Lamb.mp3)")
                print("2. Select from file browser")
                
                file_choice = input("Enter your choice (1-2): ").strip()
                
                if file_choice == "1":
                    # Analyze default file
                    if default_file.exists():
                        analyze_audio_file(default_file, analyzer, chord_analyzer, db)
                    else:
                        print(f"Default file not found: {default_file}")
                elif file_choice == "2":
                    # Use audio file selector
                    selected_files = audio_selector.select_files()
                    if selected_files:
                        for file_path in selected_files:
                            analyze_audio_file(file_path, analyzer, chord_analyzer, db)
                    else:
                        print("No files selected.")
                else:
                    print("Invalid choice.")
                    
            elif user_input == "2":
                # Option 2: Show analyzed files
                show_audio_files(db)
                
            elif user_input == "3":
                # Option 3: Start live detection
                start_live_detection(chord_detector, db)
                
            elif user_input == "4":
                # Option 4: Exit
                print("\nThank you for using LIVEFLOWAI!")
                break
                
            else:
                print("Invalid choice. Please enter 1, 2, 3, or 4.")
                
        except KeyboardInterrupt:
            print("\n\nProgram interrupted. Exiting...")
            break
        except Exception as e:
            print(f"Unexpected error: {e}")
            continue


if __name__ == "__main__":
    main()
