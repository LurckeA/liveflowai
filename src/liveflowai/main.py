import sys
from pathlib import Path

from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.database.database import DatabaseLogic


def main():
    # ------------------------------------------------------------------
    # Project paths
    # ------------------------------------------------------------------
    PROJECT_ROOT = Path(__file__).resolve().parents[2]
    AUDIO_DIR = PROJECT_ROOT / "data" / "songs"

    # ------------------------------------------------------------------
    # Initialize existing analyzers/detectors
    # ------------------------------------------------------------------
    analyzer = TempoAnalyzer(sample_rate=22050)
    chord_detector = LiveChordDetector(sample_rate=22050)

    # ------------------------------------------------------------------
    # Initialize database
    # ------------------------------------------------------------------
    DB = DatabaseLogic()

    try:
        # Create the database/table if necessary.
        DB.MakeDB()

        # Make sure the songs directory exists.
        AUDIO_DIR.mkdir(parents=True, exist_ok=True)

        # --------------------------------------------------------------
        # Find supported music files
        # --------------------------------------------------------------
        supported_extensions = {
            ".mp3",
            ".wav",
            ".flac",
            ".ogg",
            ".m4a",
        }

        songs = sorted(
            file
            for file in AUDIO_DIR.iterdir()
            if file.is_file()
            and file.suffix.lower() in supported_extensions
        )

        if not songs:
            print(f"No music files found in: {AUDIO_DIR}")
            print("Add music files to the songs folder and try again.")
            return

        # --------------------------------------------------------------
        # Display available songs
        # --------------------------------------------------------------
        print("\nAvailable songs:")
        print("-" * 60)

        for index, song in enumerate(songs, start=1):
            print(f"{index}. {song.name}")

        print("-" * 60)

        # --------------------------------------------------------------
        # Ask user which songs to process
        # --------------------------------------------------------------
        user_input = input(
            "\nEnter the song number, filename, or 'all' "
            "to analyze all new songs: "
        ).strip()

        if not user_input:
            print("No song selected.")
            return

        # --------------------------------------------------------------
        # Resolve user selection
        # --------------------------------------------------------------
        if user_input.lower() == "all":
            selected_songs = songs

        elif user_input.isdigit():
            song_index = int(user_input) - 1

            if song_index < 0 or song_index >= len(songs):
                print("Invalid song number.")
                return

            selected_songs = [songs[song_index]]

        else:
            selected_songs = [
                song
                for song in songs
                if song.name == user_input
            ]

            if not selected_songs:
                print(f"Song not found: {user_input}")
                print(f"Make sure the file exists in: {AUDIO_DIR}")
                return

        # --------------------------------------------------------------
        # Process selected songs
        # --------------------------------------------------------------
        for file_path in selected_songs:
            song_name = file_path.name

            print("\n" + "=" * 60)
            print(f"Song: {song_name}")
            print("=" * 60)

            # ----------------------------------------------------------
            # Database lookup MUST happen before analysis.
            #
            # The database uses the filename as the song primary key.
            # ----------------------------------------------------------
            existing_song = DB.GetSong(song_name)

            if existing_song is not None:
                print("Song already exists in database.")
                print("Skipping analysis.")
                continue

            # ----------------------------------------------------------
            # New song: analyze tempo
            # ----------------------------------------------------------
            print("New song detected.")
            print("Analyzing tempo...")

            result = analyzer.detect_tempo(file_path)

            print(f"Tempo: {result['tempo_bpm']:.2f} BPM")
            print(f"Duration: {result['duration']:.2f} seconds")
            print(f"Number of beats: {result['num_beats']}")

            # ----------------------------------------------------------
            # Analyze beat confidence
            # ----------------------------------------------------------
            confidence = analyzer.get_beat_confidence(file_path)

            print(
                f"Confidence score: "
                f"{confidence['confidence_score']:.2f}"
            )

            # ----------------------------------------------------------
            # Analyze chords
            # ----------------------------------------------------------
            print("\nAnalyzing chords...")

            chords, timestamps = chord_detector.detect_from_file(
                file_path
            )

            print("\nDetected chords:")

            for chord, timestamp in zip(chords, timestamps):
                print(f"{timestamp:.2f}s: {chord}")

            # ----------------------------------------------------------
            # Save analysis to database.
            #
            # Pass the chord list directly so DatabaseLogic can
            # serialize it as JSON.
            # ----------------------------------------------------------
            print("\nSaving analysis to database...")

            success = DB.PushDB(
                song_name,
                result["duration"],
                result["tempo_bpm"],
                chords,
            )

            if success:
                print(f"Successfully saved: {song_name}")
            else:
                print(f"Failed to save: {song_name}")

        # --------------------------------------------------------------
        # Start existing live microphone chord detection.
        # --------------------------------------------------------------
        print("\nStarting live chord detection...")
        chord_detector.start_detection()

    except KeyboardInterrupt:
        print("\nProgram interrupted by user.")

    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
