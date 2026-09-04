# src/liveflowai/main.py

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.detection.song_predictor import SongPredictor
from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.output.iem_manager import IEMManager
from liveflowai.database.database import DatabaseLogic


def analyze_audio_file(
    file_path,
    analyzer,
    chord_analyzer,
    db,
    iem_manager,
):
    """Analyze a single audio file and store results in database."""

    try:
        print(
            f"\n=== Analyzing: "
            f"{file_path.name} ==="
        )

        # ---------------------------------------------------------
        # Detect tempo
        # ---------------------------------------------------------

        tempo_result = analyzer.detect_tempo(
            file_path
        )

        print(
            f"Tempo: "
            f"{tempo_result['tempo_bpm']:.2f} BPM"
        )

        print(
            f"Duration: "
            f"{tempo_result['duration']:.2f} seconds"
        )

        print(
            f"Number of beats: "
            f"{tempo_result['num_beats']}"
        )

        # ---------------------------------------------------------
        # Get confidence metrics
        # ---------------------------------------------------------

        confidence = (
            analyzer.get_beat_confidence(
                file_path
            )
        )

        print(
            f"Confidence score: "
            f"{confidence['confidence_score']:.2f}"
        )

        # ---------------------------------------------------------
        # Detect chords
        # ---------------------------------------------------------

        chords = chord_analyzer.analyze_chords(
            file_path
        )

        print("\nDetected Chords:")

        for chord in chords:
            print(
                f"{chord.timestamp:.2f}s - "
                f"{chord.timestamp + chord.duration:.2f}s: "
                f"{chord} "
                f"(confidence: "
                f"{chord.confidence:.2%})"
            )

        # ---------------------------------------------------------
        # Convert chords to database string
        # ---------------------------------------------------------

        chords_string = ", ".join(
            str(chord)
            for chord in chords
        )
        # ---------------------------------------------------------
        # Convert chords to database string
        # ---------------------------------------------------------

        chords_string = ", ".join(
            str(chord)
            for chord in chords
        )
        # ---------------------------------------------------------
        # Announce over IEM
        # ---------------------------------------------------------

        iem_manager.announce_next_song(
            title=file_path.stem,
            duration_seconds=tempo_result["duration"],
            bpm=tempo_result["tempo_bpm"],
            chords=chords,
        )        
        # ---------------------------------------------------------
        # Visualize tempo
        # ---------------------------------------------------------

        analyzer.visualize_tempo(
            file_path
        )

        # ---------------------------------------------------------
        # Store results in database
        # ---------------------------------------------------------

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
    iem_manager,
):
    """
    Handle the audio-file selection and analysis workflow.

    The user can:
        1. Select an audio file.
        2. Analyze and store it.
        3. Select another file.
        4. Return to the startup menu.
    """

    print(
        "\n=== ANALYZE AUDIO FILES ==="
    )

    selected_files = (
        audio_selector.select_multiple()
    )

    if not selected_files:

        print(
            "\nNo audio files selected."
        )

        return

    print(
        f"\nSelected "
        f"{len(selected_files)} "
        f"audio file(s) for analysis."
    )

    for file_path in selected_files:

        analyze_audio_file(
            file_path,
            analyzer,
            chord_analyzer,
            db,
            iem_manager,
        )

    print(
        "\nReturning to startup menu..."
    )


def show_audio_files(db):
    """Display all audio files stored in the database."""

    try:
        files = db.FetchAllDB()

        if not files:

            print(
                "\nNo audio files found "
                "in database.\n"
            )

            return

        print(
            "\n=== Stored Audio Files ==="
        )

        for i, file in enumerate(
            files,
            1,
        ):

            song = file[0]
            duration = file[1]
            bpm = file[2]

            # -------------------------------------------------
            # Fetch only the first five chords.
            # -------------------------------------------------

            first_five_chords = (
                db.FetchFirstFiveChords(
                    song
                )
            )

            print(
                f"{i}. {song} - "
                f"{bpm:.2f} BPM - "
                f"{duration:.2f}s"
            )

            if first_five_chords:

                print(
                    f"   First five chords: "
                    f"{', '.join(first_five_chords)}"
                )

            else:

                print(
                    "   First five chords: None"
                )

            print()

    except Exception as e:

        print(
            f"Error fetching files: {e}\n"
        )


def start_performance(
    song_predictor,
    iem_manager,
):
    """
    Start a live performance session.

    The song predictor listens through the microphone.
    Once a song is identified, the IEM manager announces
    the song and starts the metronome at the song BPM.

    Ctrl+C stops the performance and metronome.
    """

    try:

        print(
            "\n=== Starting Performance ==="
        )

        print(
            "Play your instrument. LiveFlowAI will listen in "
            "15-second windows and try to identify the song."
        )

        print(
            "Once a song is identified, the metronome will "
            "start at its BPM."
        )

        print(
            "Press Ctrl+C to stop...\n"
        )

        song_predictor.run_performance()

    except KeyboardInterrupt:

        print(
            "\nPerformance stopped."
        )

    except Exception as e:

        print(
            f"Error during performance: {e}"
        )

    finally:

        # Always stop the metronome when performance ends.
        iem_manager.stop_metronome()


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

    audio_selector = AudioFileSelector()

    # ---------------------------------------------------------
    # Initialize database
    # ---------------------------------------------------------

    db = DatabaseLogic()

    db.MakeDB()
    # ---------------------------------------------------------
    # Initialize IEM manager
    # ---------------------------------------------------------

    iem_manager = IEMManager()
    # ---------------------------------------------------------
    # Initialize song predictor
    #
    # It uses the SAME LiveChordDetector instance, which is
    # what drives both live chord feedback and the recording
    # used for matching during a performance.
    # ---------------------------------------------------------

    song_predictor = SongPredictor(
        chord_detector=chord_detector,
        db=db,
        recording_duration=15.0,
        segment_duration=1.0,
        iem_manager=iem_manager,
    )

    # ---------------------------------------------------------
    # Startup menu
    # ---------------------------------------------------------

    print(
        "\n=== LIVEFLOWAI ==="
    )

    while True:

        try:

            print(
                "\nSelect your option:"
            )

            print(
                "1. Analyze Audio Files"
            )

            print(
                "2. Show Analyzed Audio Files"
            )

            print(
                "3. Start Performance"
            )

            print(
                "4. Exit"
            )

            user_input = input(
                "Enter your choice (1-4): "
            ).strip()

            # -------------------------------------------------
            # Option 1
            # -------------------------------------------------

            if user_input == "1":

                analyze_audio_files(
                    audio_selector,
                    analyzer,
                    chord_analyzer,
                    db,
                    iem_manager,
                )

            # -------------------------------------------------
            # Option 2
            # -------------------------------------------------

            elif user_input == "2":

                show_audio_files(
                    db
                )

            # -------------------------------------------------
            # Option 3
            # -------------------------------------------------

            elif user_input == "3":

                start_performance(
                    song_predictor,
                    iem_manager,
                )

            # -------------------------------------------------
            # Option 4
            # -------------------------------------------------

            elif user_input == "4":

                iem_manager.shutdown()

                print(
                    "\nThank you for using "
                    "LIVEFLOWAI!"
                )

                break

            else:

                print(
                    "Invalid choice. "
                    "Please enter 1, 2, 3, or 4."
                )

        except KeyboardInterrupt:

            print(
                "\n\nProgram interrupted. "
                "Exiting..."
            )

            break

        except Exception as e:

            print(
                f"Unexpected error: {e}"
            )

            continue


if __name__ == "__main__":
    main()
