# src/liveflowai/detection/song_predictor.py

from collections import Counter
from typing import Optional, List, Tuple


class SongPredictor:
    """
    Predict a song using chords detected from the microphone.

    The predictor:

        1. Records 15 seconds of audio.
        2. Detects approximately 15 chord segments.
        3. Ignores Unknown/uncertain segments.
        4. Compares the remaining chords against the first
           five chords of every song in the database.
        5. Does NOT require the chords to be in the same order.
        6. Allows one chord to be incorrect/missing.
        7. If there is no match, records another 15 seconds.
    """

    def __init__(
        self,
        chord_detector,
        db,
        recording_duration: float = 15.0,
        segment_duration: float = 1.0,
        minimum_match: int = 4,
    ):
        self.chord_detector = chord_detector
        self.db = db

        self.recording_duration = (
            recording_duration
        )

        self.segment_duration = (
            segment_duration
        )

        # Number of the five database chords that must match.
        #
        # 4 means:
        #
        #     C F G Em F
        #
        # can match:
        #
        #     C G F Em Am
        #
        # because 4/5 chords are present.
        self.minimum_match = minimum_match

        self.last_recording = []

        print(
            "SongPredictor initialized."
        )

    # ============================================================
    # NORMALIZE CHORD
    # ============================================================

    @staticmethod
    def _normalize_chord(
        chord: str,
    ) -> str:
        """Normalize a chord name."""

        return chord.strip()

    # ============================================================
    # REMOVE UNKNOWN CHORDS
    # ============================================================

    def _remove_unknowns(
        self,
        chords: List[Optional[str]],
    ) -> List[str]:
        """
        Remove Unknown/None chords from a recording.

        Example:

            [
                "C",
                None,
                "F",
                "G",
                None,
                "Em"
            ]

        becomes:

            [
                "C",
                "F",
                "G",
                "Em"
            ]
        """

        valid_chords = []

        for chord in chords:

            if chord is None:
                continue

            normalized = (
                self._normalize_chord(
                    chord
                )
            )

            if not normalized:
                continue

            if normalized.lower() in {
                "unknown",
                "none",
            }:
                continue

            valid_chords.append(
                normalized
            )

        return valid_chords

    # ============================================================
    # NORMALIZE SEQUENCE
    # ============================================================

    def _normalize_sequence(
        self,
        chords: List[str],
    ) -> List[str]:
        """Normalize a chord sequence."""

        return [
            self._normalize_chord(chord)
            for chord in chords
        ]

    # ============================================================
    # CALCULATE MATCH SCORE
    # ============================================================

    def _calculate_match_score(
        self,
        detected_chords: List[str],
        database_chords: List[str],
    ) -> int:
        """
        Calculate how many database chords occur in the
        detected recording.

        Chord order is intentionally ignored.

        Counter is used so duplicate chords matter.

        Example:

            Database:
                C, F, G, Em, F

            Detected:
                F, C, Em, G, F

            Score:
                5
        """

        detected_counter = Counter(
            detected_chords
        )

        database_counter = Counter(
            database_chords
        )

        score = 0

        for chord, required_count in (
            database_counter.items()
        ):

            detected_count = (
                detected_counter.get(
                    chord,
                    0
                )
            )

            score += min(
                detected_count,
                required_count
            )

        return score

    # ============================================================
    # FIND BEST MATCH
    # ============================================================

    def find_match(
        self,
        detected_chords: List[Optional[str]],
    ) -> Optional[
        Tuple[str, List[str], int]
    ]:
        """
        Find the best matching song.

        The first five chords of each song are used.

        Chord order is ignored.

        Unknown chords are ignored.

        Returns:

            (
                song_name,
                database_chords,
                match_score
            )

        or:

            None
        """

        # --------------------------------------------------------
        # Remove Unknown values.
        # --------------------------------------------------------

        valid_chords = (
            self._remove_unknowns(
                detected_chords
            )
        )

        if not valid_chords:

            return None

        # --------------------------------------------------------
        # Get first five chords from every song.
        # --------------------------------------------------------

        songs = (
            self.db.FetchAllFirstFiveChords()
        )

        if not songs:

            return None

        best_match = None
        best_score = 0

        # --------------------------------------------------------
        # Compare against every song.
        # --------------------------------------------------------

        for song, first_five in songs:

            database_chords = (
                self._normalize_sequence(
                    first_five
                )
            )

            if len(database_chords) != 5:
                continue

            score = (
                self._calculate_match_score(
                    valid_chords,
                    database_chords,
                )
            )

            if score > best_score:

                best_score = score

                best_match = (
                    song,
                    database_chords,
                    score,
                )

            # Perfect match.
            if score == 5:

                break

        # --------------------------------------------------------
        # Require minimum number of matching chords.
        # --------------------------------------------------------

        if (
            best_match is None
            or best_score < self.minimum_match
        ):

            return None

        return best_match

    # ============================================================
    # SHOW DATABASE
    # ============================================================

    def show_candidates(self):
        """Display songs available to the predictor."""

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

    def predict_once(
        self,
    ) -> Optional[str]:
        """
        Record one 15-second section and search for a match.
        """

        # --------------------------------------------------------
        # Record.
        # --------------------------------------------------------

        detected_chords = (
            self.chord_detector.record_chord_sequence(
                duration=self.recording_duration,
                segment_duration=self.segment_duration,
            )
        )

        # --------------------------------------------------------
        # Replace previous recording.
        # --------------------------------------------------------

        self.last_recording = (
            detected_chords
        )

        if not detected_chords:

            print(
                "\n⚠ No usable recording."
            )

            return None

        # --------------------------------------------------------
        # Show raw detector output.
        # --------------------------------------------------------

        print(
            "\nRaw detected chords:"
        )

        formatted = []

        for chord in detected_chords:

            if chord is None:
                formatted.append(
                    "Unknown"
                )
            else:
                formatted.append(
                    chord
                )

        print(
            f"  {', '.join(formatted)}"
        )

        # --------------------------------------------------------
        # Remove Unknown values.
        # --------------------------------------------------------

        valid_chords = (
            self._remove_unknowns(
                detected_chords
            )
        )

        print(
            "\nUsable chords:"
        )

        if valid_chords:

            print(
                f"  {', '.join(valid_chords)}"
            )

        else:

            print(
                "  None"
            )

            return None

        # --------------------------------------------------------
        # Search database.
        # --------------------------------------------------------

        print(
            "\nSearching database..."
        )

        match = self.find_match(
            detected_chords
        )

        if match is None:

            print(
                "\n✗ No song matched."
            )

            return None

        song, database_chords, score = (
            match
        )

        # --------------------------------------------------------
        # Display match.
        # --------------------------------------------------------

        print(
            "\n✓ SONG MATCH FOUND!"
        )

        print(
            f"  Song: {song}"
        )

        print(
            f"  Database chords: "
            f"{', '.join(database_chords)}"
        )

        print(
            f"  Match: "
            f"{score}/5"
        )

        return song

    # ============================================================
    # PREDICT UNTIL MATCH
    # ============================================================

    def predict_until_match(
        self,
    ) -> Optional[str]:
        """
        Continuously record 15-second sections until a song
        is identified or Ctrl+C is pressed.
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

        # --------------------------------------------------------
        # Predictor information.
        # --------------------------------------------------------

        print(
            "\n=== SONG PREDICTOR ==="
        )

        print(
            "Recording duration: "
            f"{self.recording_duration:.0f} seconds"
        )

        print(
            "Chord segment: "
            f"{self.segment_duration:.1f} seconds"
        )

        print(
            "Unknown chords: ignored"
        )

        print(
            "Chord order: ignored"
        )

        print(
            "Minimum match: "
            f"{self.minimum_match}/5"
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
                    f"\n{'=' * 60}"
                )

                print(
                    f"Prediction attempt #{attempt}"
                )

                print(
                    f"{'=' * 60}"
                )

                result = (
                    self.predict_once()
                )

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
                    "\nNo sufficient match."
                )

                print(
                    "Recording another "
                    f"{self.recording_duration:.0f} seconds..."
                )

        except KeyboardInterrupt:

            print(
                "\n\nSong prediction cancelled."
            )

            return None
