# src/liveflowai/main.py

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.audio.chord_analyzer import ChordAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.detection.song_predictor import SongPredictor
from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.output.iem_manager import IEMManager
from liveflowai.database.database import DatabaseLogic
from liveflowai.ui import ConsoleUI


def analyze_audio_file(
    file_path,
    analyzer,
    chord_analyzer,
    db,
    iem_manager,
):
    """Analyze a single audio file and store results in database."""

    try:
        ui = ConsoleUI()
        ui.header("Analysis", file_path.name, "Extracting tempo, beat confidence, and harmonic progression.")

        # ---------------------------------------------------------
        # Detect tempo
        # ---------------------------------------------------------

        tempo_result = analyzer.detect_tempo(
            file_path
        )

        ui.table(
            ("TEMPO", "DURATION", "BEATS"),
            [
                (
                    f"{tempo_result['tempo_bpm']:.0f} BPM",
                    ui.format_duration(tempo_result["duration"]),
                    str(tempo_result["num_beats"]),
                )
            ],
        )

        # ---------------------------------------------------------
        # Get confidence metrics
        # ---------------------------------------------------------

        confidence = (
            analyzer.get_beat_confidence(
                file_path
            )
        )

        ui.status(f"Beat confidence: {confidence['confidence_score']:.0%}")

        # ---------------------------------------------------------
        # Detect chords
        # ---------------------------------------------------------

        chords = chord_analyzer.analyze_chords(
            file_path
        )

        print()
        ui.table(
            ("START", "END", "CHORD", "CONFIDENCE"),
            (
                (
                    f"{chord.timestamp:.1f}s",
                    f"{chord.timestamp + chord.duration:.1f}s",
                    str(chord),
                    f"{chord.confidence:.0%}",
                )
                for chord in chords
            ),
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

        ui.status(f"Analysis saved to your song library: {file_path.name}", "success")

        return True

    except Exception as e:

        ConsoleUI().status(f"Could not analyze {file_path.name}: {e}", "error")

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

    ConsoleUI().header("Library", "Analyze songs", "Choose a folder, then add one or more audio files to the queue.")

    selected_files = (
        audio_selector.select_multiple()
    )

    if not selected_files:

        ConsoleUI().status("No audio files selected.", "warning")

        return

    ConsoleUI().status(f"{len(selected_files)} audio file(s) queued for analysis.")

    for file_path in selected_files:

        analyze_audio_file(
            file_path,
            analyzer,
            chord_analyzer,
            db,
            iem_manager,
        )

    ConsoleUI().status("Returning to the dashboard.")


def show_audio_files(db):
    """Display all audio files stored in the database."""

    try:
        ui = ConsoleUI()
        files = db.FetchAllDB()

        if not files:
            ui.header("Library", "Your analyzed songs", "Songs you analyze are saved here for performance matching.")
            ui.status("Your library is empty. Analyze a song to get started.", "warning")
            return

        ui.header("Library", "Your analyzed songs", f"{len(files)} song(s) ready for performance matching.")
        rows = []
        for i, file in enumerate(files, 1):
            song, duration, bpm = file[0], file[1], file[2]

            # -------------------------------------------------
            # Fetch only the first five chords.
            # -------------------------------------------------

            first_five_chords = (
                db.FetchFirstFiveChords(
                    song
                )
            )

            rows.append((
                str(i), song, f"{bpm:.0f}", ui.format_duration(duration),
                ", ".join(first_five_chords) if first_five_chords else "—",
            ))

        ui.table(("#", "SONG", "BPM", "LENGTH", "OPENING CHORDS"), rows)

    except Exception as e:

        ConsoleUI().status(f"Could not load the song library: {e}", "error")


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

        ConsoleUI().header(
            "Performance mode", "Listening for your song",
            "LiveFlowAI samples 15-second windows, identifies a match, and starts the stored tempo. Press Ctrl+C to stop.",
        )

        song_predictor.run_performance()

    except KeyboardInterrupt:

        ConsoleUI().status("Performance stopped.", "warning")

    except Exception as e:

        ConsoleUI().status(f"Performance error: {e}", "error")

    finally:

        # Always stop the metronome when performance ends.
        iem_manager.stop_metronome()


def cli_main():
    """Run the legacy terminal workflow.

    The installed application starts the desktop GUI through :func:`main`.
    This entry point remains available for scripts and terminal users.
    """

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

    ui = ConsoleUI()

    while True:

        try:

            ui.header(
                "LiveFlowAI", "Live music intelligence",
                "Analyze your catalog, then identify songs and drive the metronome live.",
            )
            ui.menu([
                ("1", "Analyze audio files", "Add songs and detect tempo, beats, and chords."),
                ("2", "View song library", "Review analyzed songs and their opening chord progressions."),
                ("3", "Start performance", "Listen through the microphone and match a song in real time."),
                ("4", "Exit LiveFlowAI", "Close the application safely."),
            ])
            user_input = ui.prompt("Choose an option [1–4]:")

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

                ui.status("Thanks for using LiveFlowAI. See you at soundcheck.", "success")

                break

            else:

                ui.status("Choose one of the numbered options (1–4).", "warning")

        except KeyboardInterrupt:

            ui.status("Program interrupted. Exiting safely.", "warning")

            break

        except Exception as e:

            ui.status(f"Unexpected error: {e}", "error")

            continue


def main():
    """Launch the LiveFlowAI desktop application."""

    from liveflowai.gui import launch_app

    launch_app()


if __name__ == "__main__":
    main()
