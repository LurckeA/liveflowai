import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Union

import librosa
import numpy as np


logger = logging.getLogger(__name__)


@dataclass
class Chord:
    """Represents one detected chord region."""

    name: str
    root: str
    timestamp: float
    duration: float
    confidence: float = 0.0

    def __str__(self) -> str:
        return self.name

    def to_dict(self) -> Dict:
        return {
            "chord": self.name,
            "root": self.root,
            "timestamp": self.timestamp,
            "duration": self.duration,
            "confidence": self.confidence,
        }


class ChordAnalyzer:
    """
    Hierarchical chord analyzer using librosa.

    Detection process:

    1. Extract harmonic chroma.
    2. Detect the global musical key.
    3. Detect a basic major/minor chord.
    4. Check special chord families.
    5. Refine to complex chords only with strong evidence.
    6. Carry the previous stable chord through silence.
    7. Smooth short, isolated chord changes.
    8. Merge consecutive identical chords.

    The analyzer is intentionally conservative with complex chords.
    For example, D is preferred over D9 unless both C and E are
    clearly present and strong enough.
    """

    PITCH_CLASSES = [
        "C",
        "C#",
        "D",
        "D#",
        "E",
        "F",
        "F#",
        "G",
        "G#",
        "A",
        "A#",
        "B",
    ]

    # ============================================================
    # KEY DETECTION PROFILES
    # ============================================================

    MAJOR_KEY_PROFILE = np.array(
        [
            6.35,
            2.23,
            3.48,
            2.33,
            4.38,
            4.09,
            2.52,
            5.19,
            2.39,
            3.66,
            2.29,
            2.88,
        ],
        dtype=np.float32,
    )

    MINOR_KEY_PROFILE = np.array(
        [
            6.33,
            2.68,
            3.52,
            5.38,
            2.60,
            3.53,
            2.54,
            4.75,
            3.98,
            2.69,
            3.34,
            3.17,
        ],
        dtype=np.float32,
    )

    # ============================================================
    # STAGE 1: BASIC CHORD FAMILIES
    # ============================================================

    BASIC_CHORDS = {
        "major": [0, 4, 7],
        "minor": [0, 3, 7],
    }

    # ============================================================
    # STAGE 2: SPECIAL CHORDS
    #
    # These must beat the basic major/minor chord by a margin.
    # ============================================================

    SPECIAL_CHORDS = {
        "sus2": [0, 2, 7],
        "sus4": [0, 5, 7],
        "dim": [0, 3, 6],
        "aug": [0, 4, 8],
    }

    # ============================================================
    # STAGE 3: MAJOR REFINEMENTS
    #
    # Conservative settings:
    #
    # required_strength:
    #   Minimum absolute chroma energy required for each extra note.
    #
    # required_ratio:
    #   Extra notes must also be strong relative to the main chord.
    #
    # bonus:
    #   Small bonus for genuinely present extension notes.
    # ============================================================

    MAJOR_REFINEMENTS = {
        "maj7": {
            "extra_notes": [11],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.08,
        },
        "7": {
            "extra_notes": [10],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.08,
        },
        "6": {
            "extra_notes": [9],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.06,
        },
        "add9": {
            "extra_notes": [2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.05,
        },
        "9": {
            "extra_notes": [10, 2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.08,
        },
    }

    # ============================================================
    # STAGE 3: MINOR REFINEMENTS
    # ============================================================

    MINOR_REFINEMENTS = {
        "m7": {
            "extra_notes": [10],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.08,
        },
        "m6": {
            "extra_notes": [9],
            "required_strength": 0.15,
            "required_ratio": 0.50,
            "bonus": 0.06,
        },
        "madd9": {
            "extra_notes": [2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.05,
        },
        "m9": {
            "extra_notes": [10, 2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
            "bonus": 0.08,
        },
    }

    def __init__(
        self,
        sample_rate: int = 22050,
        hop_length: int = 512,
        chord_segment_duration: float = 0.75,
        key_bonus: float = 0.04,
        silence_rms_threshold: float = 0.01,
        refinement_margin: float = 0.16,
        minimum_confidence: float = 0.35,
    ):
        self.sample_rate = sample_rate
        self.hop_length = hop_length
        self.chord_segment_duration = chord_segment_duration
        self.key_bonus = key_bonus
        self.silence_rms_threshold = silence_rms_threshold
        self.refinement_margin = refinement_margin
        self.minimum_confidence = minimum_confidence

        self.detected_key: Optional[str] = None
        self.key_root_index: Optional[int] = None
        self.key_mode: Optional[str] = None

        logger.info(
            "ChordAnalyzer initialized "
            f"(sample_rate={self.sample_rate})"
        )

    # ============================================================
    # AUDIO LOADING
    # ============================================================

    def load_audio(
        self,
        audio_path: Union[str, Path],
    ) -> np.ndarray:
        """Load and normalize an audio file."""

        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        logger.info(f"Loading audio: {audio_path}")

        audio, _ = librosa.load(
            str(audio_path),
            sr=self.sample_rate,
            mono=True,
        )

        if len(audio) == 0:
            raise ValueError("Audio file is empty.")

        audio = audio.astype(np.float32)

        # Remove DC offset.
        audio = audio - np.mean(audio)

        # Safe normalization.
        peak = np.max(np.abs(audio))

        if peak > 1e-8:
            audio = audio / peak

        logger.info(
            f"Audio loaded successfully. "
            f"Duration: {len(audio) / self.sample_rate:.2f}s"
        )

        return audio

    # ============================================================
    # CHROMA EXTRACTION
    # ============================================================

    def extract_chroma(
        self,
        audio: np.ndarray,
    ) -> np.ndarray:
        """
        Extract chroma primarily from harmonic audio.

        HPSS helps reduce the influence of drums and percussion.
        """

        harmonic_audio, _ = librosa.effects.hpss(audio)

        chroma = librosa.feature.chroma_cqt(
            y=harmonic_audio,
            sr=self.sample_rate,
            hop_length=self.hop_length,
            n_chroma=12,
        )

        return chroma.astype(np.float32)

    # ============================================================
    # KEY DETECTION
    # ============================================================

    @staticmethod
    def _correlation(
        a: np.ndarray,
        b: np.ndarray,
    ) -> float:
        """Calculate normalized correlation."""

        a = a - np.mean(a)
        b = b - np.mean(b)

        denominator = np.linalg.norm(a) * np.linalg.norm(b)

        if denominator < 1e-8:
            return 0.0

        return float(np.dot(a, b) / denominator)

    def detect_key(
        self,
        chroma: np.ndarray,
    ) -> Tuple[str, str, float]:
        """Detect the global musical key."""

        profile = np.mean(chroma, axis=1)

        total = np.sum(profile)

        if total > 1e-8:
            profile = profile / total

        best_score = -np.inf
        best_root = 0
        best_mode = "major"

        for root in range(12):
            major_profile = np.roll(
                self.MAJOR_KEY_PROFILE,
                root,
            )

            major_score = self._correlation(
                profile,
                major_profile,
            )

            if major_score > best_score:
                best_score = major_score
                best_root = root
                best_mode = "major"

            minor_profile = np.roll(
                self.MINOR_KEY_PROFILE,
                root,
            )

            minor_score = self._correlation(
                profile,
                minor_profile,
            )

            if minor_score > best_score:
                best_score = minor_score
                best_root = root
                best_mode = "minor"

        self.key_root_index = best_root
        self.key_mode = best_mode

        key_name = (
            f"{self.PITCH_CLASSES[best_root]} {best_mode}"
        )

        self.detected_key = key_name

        logger.info(
            f"Detected key: {key_name} "
            f"(score={best_score:.3f})"
        )

        return key_name, best_mode, float(best_score)

    # ============================================================
    # CHORD TEMPLATE CREATION
    # ============================================================

    def _make_template(
        self,
        root: int,
        intervals: List[int],
    ) -> Tuple[np.ndarray, List[int]]:
        """Create a weighted chord template."""

        template = np.zeros(
            12,
            dtype=np.float32,
        )

        notes = []

        for position, interval in enumerate(intervals):
            note = (root + interval) % 12

            notes.append(note)

            # Root is slightly more important.
            if position == 0:
                template[note] = 1.0
            else:
                template[note] = 0.9

        norm = np.linalg.norm(template)

        if norm > 1e-8:
            template /= norm

        return template, notes

    # ============================================================
    # TEMPLATE SCORING
    # ============================================================

    def _template_score(
        self,
        chroma: np.ndarray,
        root: int,
        intervals: List[int],
    ) -> Tuple[float, List[int]]:
        """
        Score chroma against a chord template.

        The score rewards:
        - template similarity
        - energy on chord tones
        - root presence

        It penalizes:
        - energy outside the chord
        """

        template, chord_notes = self._make_template(
            root,
            intervals,
        )

        chroma_norm = np.linalg.norm(chroma)

        if chroma_norm < 1e-8:
            return 0.0, chord_notes

        similarity = float(
            np.dot(chroma, template)
            / (
                chroma_norm
                * np.linalg.norm(template)
                + 1e-8
            )
        )

        chord_energy = float(
            np.sum(chroma[chord_notes])
        )

        root_energy = float(chroma[root])

        outside_energy = max(
            0.0,
            1.0 - chord_energy,
        )

        score = (
            0.55 * similarity
            + 0.30 * chord_energy
            + 0.15 * root_energy
            - 0.12 * outside_energy
        )

        return float(score), chord_notes

    # ============================================================
    # KEY BONUS
    # ============================================================

    def _key_chord_bonus(
        self,
        root: int,
        family: str,
    ) -> float:
        """
        Give a very small bonus to likely diatonic chords.

        This is intentionally weak. The detected audio always
        remains more important than the global key.
        """

        if (
            self.key_root_index is None
            or self.key_mode is None
        ):
            return 0.0

        relative_root = (
            root - self.key_root_index
        ) % 12

        if self.key_mode == "major":
            if (
                family == "major"
                and relative_root in {0, 5, 7}
            ):
                return self.key_bonus

            if (
                family == "minor"
                and relative_root in {2, 4, 9}
            ):
                return self.key_bonus

        elif self.key_mode == "minor":
            if (
                family == "minor"
                and relative_root in {0, 5}
            ):
                return self.key_bonus

            if (
                family == "major"
                and relative_root in {7, 8, 10}
            ):
                return self.key_bonus

        return 0.0

    # ============================================================
    # STAGE 1: BASIC CHORD DETECTION
    # ============================================================

    def detect_basic_chord(
        self,
        chroma: np.ndarray,
    ) -> Tuple[int, str, float]:
        """
        Detect only the root and major/minor family.

        Example:
            C major

        At this stage, the analyzer does NOT try to choose
        Cmaj7, C9, C6, etc.
        """

        best_root = 0
        best_family = "major"
        best_score = -np.inf

        for root in range(12):
            for family, intervals in self.BASIC_CHORDS.items():
                score, _ = self._template_score(
                    chroma,
                    root,
                    intervals,
                )

                score += self._key_chord_bonus(
                    root,
                    family,
                )

                if score > best_score:
                    best_score = score
                    best_root = root
                    best_family = family

        return (
            best_root,
            best_family,
            float(best_score),
        )

    # ============================================================
    # STAGE 2: SPECIAL CHORD DETECTION
    # ============================================================

    def detect_special_chord(
        self,
        chroma: np.ndarray,
        root: int,
        basic_score: float,
    ) -> Optional[Tuple[str, float]]:
        """
        Check sus2, sus4, diminished and augmented.

        A special chord must beat the basic chord by the
        refinement margin.
        """

        best_name = None
        best_score = basic_score

        for name, intervals in self.SPECIAL_CHORDS.items():
            score, _ = self._template_score(
                chroma,
                root,
                intervals,
            )

            if score > best_score + self.refinement_margin:
                best_score = score
                best_name = name

        if best_name is None:
            return None

        return best_name, float(best_score)

    # ============================================================
    # STAGE 3: CONSERVATIVE COMPLEX REFINEMENT
    # ============================================================

    def refine_chord(
        self,
        chroma: np.ndarray,
        root: int,
        family: str,
        basic_score: float,
    ) -> Tuple[str, float]:
        """
        Refine a basic chord only when there is strong evidence.

        Example:

            Stage 1:
                D major

            Stage 3 checks:
                Dmaj7
                D7
                D6
                Dadd9
                D9

            D9 is selected only when BOTH:
                C natural is strong
                E natural is strong

            Otherwise:
                D remains D
        """

        root_name = self.PITCH_CLASSES[root]

        # --------------------------------------------------------
        # CHECK SPECIAL CHORDS
        # --------------------------------------------------------

        special = self.detect_special_chord(
            chroma,
            root,
            basic_score,
        )

        if special is not None:
            special_name, special_score = special

            return (
                f"{root_name}{special_name}",
                special_score,
            )

        # --------------------------------------------------------
        # SELECT BASIC CHORD FAMILY
        # --------------------------------------------------------

        if family == "major":
            basic_intervals = [0, 4, 7]
            refinements = self.MAJOR_REFINEMENTS
            best_name = root_name
        else:
            basic_intervals = [0, 3, 7]
            refinements = self.MINOR_REFINEMENTS
            best_name = f"{root_name}m"

        best_score = basic_score

        # --------------------------------------------------------
        # CALCULATE BASIC CHORD ENERGY
        # --------------------------------------------------------

        basic_note_indices = [
            (root + interval) % 12
            for interval in basic_intervals
        ]

        basic_note_strengths = chroma[
            basic_note_indices
        ]

        basic_energy = float(
            np.mean(basic_note_strengths)
        )

        # --------------------------------------------------------
        # TEST EXTENSIONS CONSERVATIVELY
        # --------------------------------------------------------

        for refinement_name, config in refinements.items():
            extra_intervals = config["extra_notes"]

            required_strength = config[
                "required_strength"
            ]

            required_ratio = config[
                "required_ratio"
            ]

            extra_strengths = []

            for interval in extra_intervals:
                note_index = (
                    root + interval
                ) % 12

                extra_strengths.append(
                    float(chroma[note_index])
                )

            # ----------------------------------------------------
            # RULE 1:
            # Every required extension note must be strong.
            #
            # Example:
            #
            # D9 requires:
            # D F# A C E
            #
            # Both C and E must be present.
            #
            # Weak C + strong E = NOT D9
            # Strong C + weak E = NOT D9
            # ----------------------------------------------------

            if any(
                strength < required_strength
                for strength in extra_strengths
            ):
                continue

            average_extra_strength = float(
                np.mean(extra_strengths)
            )

            # ----------------------------------------------------
            # RULE 2:
            # Extension notes must be significant compared with
            # the main chord tones.
            #
            # This prevents weak harmonics or background notes
            # from turning:
            #
            # D -> D9
            # ----------------------------------------------------

            if basic_energy > 1e-8:
                extension_ratio = (
                    average_extra_strength
                    / basic_energy
                )

                if extension_ratio < required_ratio:
                    continue

            # ----------------------------------------------------
            # RULE 3:
            # The full complex chord must actually fit the
            # chroma well.
            # ----------------------------------------------------

            full_intervals = (
                basic_intervals
                + extra_intervals
            )

            full_score, _ = self._template_score(
                chroma,
                root,
                full_intervals,
            )

            # ----------------------------------------------------
            # RULE 4:
            # Complex chords should not win automatically just
            # because they contain more notes.
            #
            # The extra notes must contribute meaningful evidence.
            # ----------------------------------------------------

            extension_bonus = (
                config["bonus"]
                * average_extra_strength
            )

            refinement_score = (
                full_score
                + extension_bonus
            )

            # ----------------------------------------------------
            # RULE 5:
            # The refinement must beat the current best result
            # by a meaningful margin.
            # ----------------------------------------------------

            if (
                refinement_score
                <= best_score
                + self.refinement_margin
            ):
                continue

            # ----------------------------------------------------
            # Complex chord accepted.
            # ----------------------------------------------------

            best_score = refinement_score

            best_name = (
                f"{root_name}{refinement_name}"
            )

        return best_name, float(best_score)

    # ============================================================
    # FULL HIERARCHICAL DETECTION
    # ============================================================

    def detect_chord(
        self,
        chroma: np.ndarray,
    ) -> Tuple[Optional[str], float]:
        """
        Run the complete hierarchical chord detector.
        """

        total_energy = float(np.sum(chroma))

        if total_energy < 1e-8:
            return None, 0.0

        chroma = chroma / total_energy

        # Stage 1: Basic major/minor chord.
        root, family, basic_score = (
            self.detect_basic_chord(chroma)
        )

        # Stage 2 and 3: Special/complex refinement.
        chord_name, refined_score = self.refine_chord(
            chroma,
            root,
            family,
            basic_score,
        )

        # Convert score to a safe confidence value.
        confidence = float(
            np.clip(
                refined_score,
                0.0,
                1.0,
            )
        )

        if confidence < self.minimum_confidence:
            return None, confidence

        return chord_name, confidence

    # ============================================================
    # TEMPORAL SMOOTHING
    # ============================================================

    def smooth_predictions(
        self,
        predictions: List[Chord],
    ) -> List[Chord]:
        """
        Remove one-segment chord glitches.

        Example:

            C
            C
            G   <- isolated glitch
            C
            C

        becomes:

            C
            C
            C
            C
            C
        """

        if len(predictions) < 3:
            return predictions

        result = predictions.copy()

        for i in range(1, len(predictions) - 1):
            previous = predictions[i - 1]
            current = predictions[i]
            next_chord = predictions[i + 1]

            if (
                previous.name == next_chord.name
                and current.name != previous.name
            ):
                result[i] = Chord(
                    name=previous.name,
                    root=previous.root,
                    timestamp=current.timestamp,
                    duration=current.duration,
                    confidence=max(
                        previous.confidence,
                        current.confidence,
                        next_chord.confidence,
                    ),
                )

        return result

    # ============================================================
    # REMOVE SHORT ISOLATED CHORDS
    # ============================================================

    def remove_short_chords(
        self,
        chords: List[Chord],
        minimum_duration: float = 1.0,
    ) -> List[Chord]:
        """
        Replace short isolated chord regions when the surrounding
        chord is the same.
        """

        if len(chords) < 3:
            return chords

        result = chords.copy()

        for i in range(1, len(chords) - 1):
            previous = chords[i - 1]
            current = chords[i]
            next_chord = chords[i + 1]

            if (
                current.duration < minimum_duration
                and previous.name == next_chord.name
                and current.name != previous.name
            ):
                result[i] = Chord(
                    name=previous.name,
                    root=previous.root,
                    timestamp=current.timestamp,
                    duration=current.duration,
                    confidence=max(
                        previous.confidence,
                        next_chord.confidence,
                    ),
                )

        return result

    # ============================================================
    # MERGE IDENTICAL CHORDS
    # ============================================================

    def merge_similar_chords(
        self,
        chords: List[Chord],
    ) -> List[Chord]:
        """Merge consecutive identical chord regions."""

        if not chords:
            return []

        merged = []

        current = Chord(
            name=chords[0].name,
            root=chords[0].root,
            timestamp=chords[0].timestamp,
            duration=chords[0].duration,
            confidence=chords[0].confidence,
        )

        confidence_values = [
            chords[0].confidence
        ]

        for chord in chords[1:]:
            if chord.name == current.name:
                new_end = (
                    chord.timestamp
                    + chord.duration
                )

                current.duration = (
                    new_end
                    - current.timestamp
                )

                confidence_values.append(
                    chord.confidence
                )

                current.confidence = float(
                    np.mean(confidence_values)
                )

            else:
                merged.append(current)

                current = Chord(
                    name=chord.name,
                    root=chord.root,
                    timestamp=chord.timestamp,
                    duration=chord.duration,
                    confidence=chord.confidence,
                )

                confidence_values = [
                    chord.confidence
                ]

        merged.append(current)

        return merged

    # ============================================================
    # MAIN FILE ANALYSIS
    # ============================================================

    def analyze_chords(
        self,
        audio_path: Union[str, Path],
    ) -> List[Chord]:
        """
        Analyze chords in an audio file.

        Important behavior:

        - No "N/A" chords are returned.
        - Silence carries the previous stable chord forward.
        - Beginning silence is filled with the first real chord.
        - Complex chords require strong evidence.
        """

        logger.info(
            f"Analyzing chords: {audio_path}"
        )

        # --------------------------------------------------------
        # LOAD AUDIO
        # --------------------------------------------------------

        audio = self.load_audio(audio_path)

        # --------------------------------------------------------
        # EXTRACT CHROMA
        # --------------------------------------------------------

        chroma = self.extract_chroma(audio)

        # --------------------------------------------------------
        # DETECT GLOBAL KEY
        # --------------------------------------------------------

        key_name, _, key_score = self.detect_key(
            chroma
        )

        print(
            f"\nDetected Key: {key_name} "
            f"(score: {key_score:.2%})"
        )

        total_frames = chroma.shape[1]

        segment_frames = max(
            1,
            round(
                self.chord_segment_duration
                * self.sample_rate
                / self.hop_length
            ),
        )

        predictions: List[Optional[Chord]] = []

        previous_stable_chord: Optional[Chord] = None

        # --------------------------------------------------------
        # ANALYZE EACH SEGMENT
        # --------------------------------------------------------

        for start_frame in range(
            0,
            total_frames,
            segment_frames,
        ):
            end_frame = min(
                start_frame + segment_frames,
                total_frames,
            )

            if end_frame <= start_frame:
                continue

            timestamp = (
                start_frame
                * self.hop_length
                / self.sample_rate
            )

            duration = (
                (end_frame - start_frame)
                * self.hop_length
                / self.sample_rate
            )

            # ----------------------------------------------------
            # GET AUDIO SEGMENT FOR SILENCE DETECTION
            # ----------------------------------------------------

            start_sample = int(
                start_frame
                * self.hop_length
            )

            end_sample = min(
                len(audio),
                int(
                    end_frame
                    * self.hop_length
                ),
            )

            audio_segment = audio[
                start_sample:end_sample
            ]

            if len(audio_segment) > 0:
                rms = float(
                    np.sqrt(
                        np.mean(
                            audio_segment ** 2
                        )
                    )
                )
            else:
                rms = 0.0

            # ----------------------------------------------------
            # SILENCE:
            # Carry previous stable chord forward.
            # ----------------------------------------------------

            if rms < self.silence_rms_threshold:
                if previous_stable_chord is not None:
                    predictions.append(
                        Chord(
                            name=previous_stable_chord.name,
                            root=previous_stable_chord.root,
                            timestamp=timestamp,
                            duration=duration,
                            confidence=previous_stable_chord.confidence,
                        )
                    )
                else:
                    predictions.append(None)

                continue

            # ----------------------------------------------------
            # CALCULATE SEGMENT CHROMA
            # ----------------------------------------------------

            segment_chroma = np.mean(
                chroma[
                    :,
                    start_frame:end_frame,
                ],
                axis=1,
            )

            chord_name, confidence = self.detect_chord(
                segment_chroma
            )

            # ----------------------------------------------------
            # LOW-CONFIDENCE FALLBACK:
            # Keep previous stable chord.
            # ----------------------------------------------------

            if chord_name is None:
                if previous_stable_chord is not None:
                    predictions.append(
                        Chord(
                            name=previous_stable_chord.name,
                            root=previous_stable_chord.root,
                            timestamp=timestamp,
                            duration=duration,
                            confidence=previous_stable_chord.confidence,
                        )
                    )
                else:
                    predictions.append(None)

                continue

            # ----------------------------------------------------
            # EXTRACT ROOT NAME
            # ----------------------------------------------------

            if (
                len(chord_name) >= 2
                and chord_name[1] == "#"
            ):
                root = chord_name[:2]
            else:
                root = chord_name[:1]

            detected = Chord(
                name=chord_name,
                root=root,
                timestamp=timestamp,
                duration=duration,
                confidence=confidence,
            )

            predictions.append(detected)

            previous_stable_chord = detected

        # ========================================================
        # FIND FIRST REAL CHORD
        # ========================================================

        first_real_chord = next(
            (
                chord
                for chord in predictions
                if chord is not None
            ),
            None,
        )

        if first_real_chord is None:
            logger.warning(
                "No usable harmonic information detected."
            )
            return []

        # ========================================================
        # FILL BEGINNING SILENCE
        # ========================================================

        cleaned: List[Chord] = []

        for index, chord in enumerate(predictions):
            if chord is not None:
                cleaned.append(chord)
                continue

            timestamp = (
                index
                * segment_frames
                * self.hop_length
                / self.sample_rate
            )

            cleaned.append(
                Chord(
                    name=first_real_chord.name,
                    root=first_real_chord.root,
                    timestamp=timestamp,
                    duration=(
                        segment_frames
                        * self.hop_length
                        / self.sample_rate
                    ),
                    confidence=first_real_chord.confidence,
                )
            )

        # ========================================================
        # TEMPORAL POST-PROCESSING
        # ========================================================

        cleaned = self.smooth_predictions(
            cleaned
        )

        cleaned = self.remove_short_chords(
            cleaned,
            minimum_duration=1.0,
        )

        cleaned = self.smooth_predictions(
            cleaned
        )

        # ========================================================
        # MERGE CONSECUTIVE IDENTICAL CHORDS
        # ========================================================

        chords = self.merge_similar_chords(
            cleaned
        )

        logger.info(
            "Chord analysis complete: "
            f"{len(chords)} chord regions."
        )

        return chords