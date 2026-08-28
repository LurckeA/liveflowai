# src/liveflowai/detection/song_predictor.py

from typing import Optional


class SongPredictor:
    """
    Predict a song by comparing a live 5-second chord recording
    against the first five chords of songs stored in the database.
    """

    def __init__(
        self,
        db,
        chord_detector,
        recording_duration: float = 5.0,
    ):
        self.db = db
        self.chord_detector = chord_detector
        self.recording_duration = recording_duration

    # ============================================================
    # NORMALIZE CHORD
    # ============================================================

    @staticmethod
    def normalize_chord(chord: str) -> str:
        """
        Normalize a chord name for comparison.

        Example:
            " C " -> "C"
            "Em"  -> "Em"
        """

        return str(chord).strip()

    # ============================================================
    # COMPARE CHORDS
    # ============================================================

    def chords_match(
        self,
        recorded_chords: list[str],
        stored_chords: list[str],
    ) -> bool:
        """
        Check whether the recorded chord sequence matches
        the stored first-five chord sequence.
        """

        if len(recorded_chords) < 5:
            return False

        if len(stored_chords) < 5:
            return False

        recorded = [
            self.normalize_chord(chord)
            for chord in recorded_chords[:5]
        ]

        stored = [
            self.normalize_chord(chord)
            for chord in stored_chords[:5]
        ]

        return recorded == stored

    # ============================================================
    # FIND MATCH
    # ============================================================

    def find_match(
        self,
        recorded_chords: list[str],
    ) -> Optional[str]:
        """
        Compare the recorded chords against every song
        in the database.

        Returns:
            Song name if a match is found.
            None if there is no match.
        """

        files = self.db.FetchAllDB()

        if not files:
            return None

        for row in files:
            song = row[0]

            stored_chords = (
                self.db.FetchFirstFiveChords(song)
            )

            if self.chords_match(
                recorded_chords,
                stored_chords,
            ):
                return song

        return None

    # ============================================================
    # PREDICT
    # ============================================================

    def predict(self):
        """
        Continuously record five seconds of chords and try
        to identify the song.

        If no song matches, another five-second recording
        is made and the previous recording is discarded.
        """

        print("\n=== SONG PREDICTOR ===")

        files = self.db.FetchAllDB()

        if not files:
            print("No songs are stored in the database.")
            return None

        print(
            "\nPlay the beginning of a song."
        )
        print(
            "LIVEFLOWAI will listen for 5 seconds..."
        )

        attempt = 1

        while True:

            print(
                f"\n--- Recording attempt {attempt} ---"
            )

            # ----------------------------------------------------
            # Record and detect chords
            # ----------------------------------------------------

            recorded_chords = (
                self.chord_detector.record_chords(
                    duration=self.recording_duration
                )
            )

            print(
                "\nDetected chords:"
            )

            if recorded_chords:
                print(
                    ", ".join(recorded_chords)
                )
            else:
                print("No chords detected.")

            # ----------------------------------------------------
            # Try to find a song
            # ----------------------------------------------------

            matched_song = self.find_match(
                recorded_chords
            )

            if matched_song is not None:

                print(
                    f"\n✓ Song matched: "
                    f"{matched_song}"
                )

                return matched_song

            # ----------------------------------------------------
            # No match
            # ----------------------------------------------------

            print(
                "\n✗ No matching song found."
            )

            print(
                "Recording another 5 seconds..."
            )

            attempt += 1
