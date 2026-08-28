# src/liveflowai/detection/song_predictor.py

from typing import Optional, List, Tuple


class SongPredictor:
    """
    Predict a song by comparing a five-chord sequence detected
    from the microphone against the first five chords of every
    song stored in the database.
    """

    def __init__(
        self,
        chord_detector,
        db,
        recording_duration: float = 5.0,
        segment_duration: float = 1.0,
    ):
        self.chord_detector = chord_detector
        self.db = db

        self.recording_duration = recording_duration
        self.segment_duration = segment_duration

        self.last_recording = []

        print(
            "SongPredictor initialized."
        )

    # ============================================================
    # NORMALIZE CHORD
    # ============================================================

    @staticmethod
    def _normalize_chord(chord: str) -> str:
        """Normalize a chord name before comparison."""

        return chord.strip()

    # ============================================================
    # NORMALIZE SEQUENCE
    # ============================================================

    def _normalize_sequence(
        self,
        chords: List[str],
    ) -> List[str]:
        """Normalize a complete chord sequence."""

        return [
            self._normalize_chord(chord)
            for chord in chords
        ]

    # ============================================================
    # FIND MATCH
    # ============================================================

    def find_match(
        self,
        detected_chords: List[str],
    ) -> Optional[Tuple[str, List[str]]]:
        """
        Compare detected chords against every song in the database.

        Returns:
            (song_name, first_five_chords)

        or:

            None
        """

        detected_chords = (
            self._normalize_sequence(
                detected_chords
            )
        )

        if len(detected_chords) != 5:
            return None

        songs = (
            self.db.FetchAllFirstFiveChords()
        )

        if not songs:
            return None

        for song, first_five in songs:

            database_chords = (
                self._normalize_sequence(
                    first_five
                )
            )

            if detected_chords == database_chords:
                return (
                    song,
                    database_chords,
                )

        return None

    # ============================================================
    # SHOW DATABASE
    # ============================================================

    def show_candidates(self):
        """Display the chord sequences available for prediction."""

        songs = (
            self.db.FetchAllFirstFiveChords()
        )

        if not songs:
            print(
                "\nNo songs with at least "
                "five chords found in database."
            )

            return

        print(
            "\n=== Song Predictor Database ==="
        )

        for song, chords in songs:
            print(
                f"{song}: "
                f"{', '.join(chords)}"
            )

    # ============================================================
    # ONE PREDICTION ATTEMPT
    # ============================================================

    def predict_once(self) -> Optional[str]:
        """
        Record five seconds and attempt to identify a song.

        Returns:
            Song name if matched.
            None if no match.
        """

        detected_chords = (
            self.chord_detector.record_chord_sequence(
                duration=self.recording_duration,
                segment_duration=self.segment_duration,
            )
        )

        # Replace the previous recording.
        self.last_recording = detected_chords

        if not detected_chords:
            print(
                "\n⚠ No usable chord sequence "
                "was detected."
            )

            return None

        print(
            "\nDetected sequence:"
        )

        print(
            f"  {', '.join(detected_chords)}"
        )

        print(
            "\nSearching database..."
        )

        match = self.find_match(
            detected_chords
        )

        if match is None:
            print(
                "\n✗ No song matched "
                "the five-chord sequence."
            )

            return None

        song, chords = match

        print(
            "\n✓ SONG MATCH FOUND!"
        )

        print(
            f"  Song: {song}"
        )

        print(
            f"  Chords: {', '.join(chords)}"
        )

        return song

    # ============================================================
    # PREDICT UNTIL MATCH
    # ============================================================

    def predict_until_match(self) -> Optional[str]:
        """
        Continuously record five seconds and search for a song.

        Every failed attempt is replaced by a new five-second
        recording.

        Stops when:
            - A song is matched.
            - Ctrl+C is pressed.
        """

        songs = (
            self.db.FetchAllFirstFiveChords()
        )

        if not songs:
            print(
                "\n✗ There are no songs with "
                "at least five chords in the database."
            )

            return None

        print(
            "\n=== SONG PREDICTOR ==="
        )

        print(
            "The system will record five seconds "
            "at a time."
        )

        print(
            "Each recording replaces the previous "
            "recording."
        )

        print(
            "The predictor will continue until "
            "a song is matched."
        )

        print(
            "\nSongs available for prediction:"
        )

        for song, chords in songs:
            print(
                f"  - {song}: "
                f"{', '.join(chords)}"
            )

        attempt = 1

        try:
            while True:

                print(
                    f"\n{'=' * 55}"
                )

                print(
                    f"Prediction attempt #{attempt}"
                )

                print(
                    f"{'=' * 55}"
                )

                result = self.predict_once()

                if result is not None:

                    print(
                        "\n🎵 Predicted song:"
                    )

                    print(
                        f"   {result}"
                    )

                    return result

                attempt += 1

                print(
                    "\nNo match."
                )

                print(
                    "Recording another five seconds..."
                )

        except KeyboardInterrupt:

            print(
                "\n\nSong prediction cancelled."
            )

            return None
