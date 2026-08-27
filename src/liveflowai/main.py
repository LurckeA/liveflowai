# src/liveflowai/main.py

from pathlib import Path

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.database.database import DatabaseLogic


def analyze_audio_file(file_path, analyzer, chord_analyzer, db):
    """Analyze a single audio file and store results in database."""

    try:
        print(f"\n=== Analyzing: {file_path.name} ===")

        # Detect tempo
        tempo_result = analyzer.detect_tempo(file_path)

        print(f"Tempo: {tempo_result['tempo_bpm']:.2f} BPM")
        print(f"Duration: {tempo_result['duration']:.2f} seconds")
        print(f"Number of beats: {tempo_result['num_beats']}")

        # Get confidence metrics
        confidence = analyzer.get_beat_confidence(file_path)

        print(
            f"Confidence score: "
            f"{confidence['confidence_score']:.2f}"
        )

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

        # Convert chords to a database-friendly string
        chords_string = ", ".join(str(chord) for chord in chords)

        # Visualize tempo
        analyzer.visualize_tempo(file_path)

        # Store results in database
        db.PushDB(
            file_path.name,
            tempo_result["duration"],
            tempo_result["tempo_bpm"],
            chords_string,
        )

        print(
            f"\n✓ Successfully analyzed and stored: "
            f"{file_path.name}"
        )

        return True

    except Exception as e:
        print(
            f"\n✗ Error analyzing "
            f"{file_path.name}: {e}"
        )

        return False


def analyze_audio_files(
    audio_selector,
    analyzer,
    chord_analyzer,
    db,
):
    """
    Handle the audio-file selection and analysis workflow.

    The user can:
        1. Select an audio file.
        2. Analyze and store it.
        3. Select another file.
        4. Return to the startup menu.
    """

    print("\n=== ANALYZE AUDIO FILES ===")

    selected_files = audio_selector.select_multiple()

    if not selected_files:
        print("\nNo audio files selected.")
        return

    print(
        f"\nSelected {len(selected_files)} "
        f"audio file(s) for analysis."
    )

    for file_path in selected_files:
        analyze_audio_file(
            file_path,
            analyzer,
            chord_analyzer,
            db,
        )

    print("\nReturning to startup menu...")

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

            # Fetch only the first five chords
            first_five_chords = db.FetchFirstFiveChords(song)

            print(
                f"{i}. {song} - "
                f"{bpm:.2f} BPM - "
                f"{duration:.2f}s"
            )
            print(f"   Chords: {chords}\n")

            if first_five_chords:
                print(
                    f"   First five chords: "
                    f"{', '.join(first_five_chords)}"
                )
            else:
                print("   Chords: None")

            print()

    except Exception as e:
        print(f"Error fetching files: {e}\n")

def start_live_detection(chord_detector):
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
    # ---------------------------------------------------------
    # Initialize analyzers
    # ---------------------------------------------------------

    SAMPLE_RATE = 22050

    analyzer = TempoAnalyzer(
        sample_rate=SAMPLE_RATE
    )

    chord_analyzer = ChordAnalyzer(
        sample_rate=SAMPLE_RATE
    )

    chord_detector = LiveChordDetector(
        sample_rate=SAMPLE_RATE
    )

    # ---------------------------------------------------------
    # Setup audio selector
    # ---------------------------------------------------------

    PROJECT_ROOT = Path(__file__).resolve().parents[2]

    audio_selector = AudioFileSelector(
        base_dir=PROJECT_ROOT
    )

    # ---------------------------------------------------------
    # Initialize database
    # ---------------------------------------------------------

    db = DatabaseLogic()

    db.ConnectDB()
    db.MakeDB()

    # ---------------------------------------------------------
    # Startup menu
    # ---------------------------------------------------------

    print("\n=== LIVEFLOWAI ===")

    while True:
        try:
            print("\nSelect your option:")
            print("1. Analyze Audio Files")
            print("2. Show Analyzed Audio Files")
            print("3. Start Live Chord Detection")
            print("4. Exit")

            user_input = input(
                "Enter your choice (1-4): "
            ).strip()

            # -------------------------------------------------
            # Option 1: Analyze Audio Files
            # -------------------------------------------------

            if user_input == "1":

                analyze_audio_files(
                    audio_selector,
                    analyzer,
                    chord_analyzer,
                    db,
                )

            # -------------------------------------------------
            # Option 2: Show Analyzed Audio Files
            # -------------------------------------------------

            elif user_input == "2":

                show_audio_files(db)

            # -------------------------------------------------
            # Option 3: Live Chord Detection
            # -------------------------------------------------

            elif user_input == "3":

                start_live_detection(
                    chord_detector
                )

            # -------------------------------------------------
            # Option 4: Exit
            # -------------------------------------------------

            elif user_input == "4":

                print(
                    "\nThank you for using LIVEFLOWAI!"
                )

                break

            else:

                print(
                    "Invalid choice. "
                    "Please enter 1, 2, 3, or 4."
                )

        except KeyboardInterrupt:

            print(
                "\n\nProgram interrupted. Exiting..."
            )

            break

        except Exception as e:

            print(
                f"Unexpected error: {e}"
            )

            continue


if __name__ == "__main__":
    main()
