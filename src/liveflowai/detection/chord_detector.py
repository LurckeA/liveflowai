# src/liveflowai/detection/chord_predictor.py

import queue
import time
from collections import Counter, deque
from typing import Optional, Tuple, List

import librosa
import numpy as np
import sounddevice as sd


class LiveChordDetector:
    """
    Real-time microphone chord detector.

    Detection pipeline:

    Microphone
        ↓
    Audio buffer
        ↓
    Harmonic/percussive separation
        ↓
    Chroma extraction
        ↓
    Basic chord detection
        ↓
    Conservative complex chord refinement
        ↓
    Temporal smoothing
        ↓
    Stable live chord output
    """

    PITCH_CLASSES = [
        "C", "C#", "D", "D#", "E", "F",
        "F#", "G", "G#", "A", "A#", "B",
    ]

    BASIC_CHORDS = {
        "major": [0, 4, 7],
        "minor": [0, 3, 7],
    }

    SPECIAL_CHORDS = {
        "sus2": [0, 2, 7],
        "sus4": [0, 5, 7],
        "dim": [0, 3, 6],
        "aug": [0, 4, 8],
    }

    # Conservative complex chord rules.
    MAJOR_REFINEMENTS = {
        "maj7": {
            "extra_notes": [11],
            "required_strength": 0.14,
            "required_ratio": 0.45,
        },
        "7": {
            "extra_notes": [10],
            "required_strength": 0.14,
            "required_ratio": 0.45,
        },
        "6": {
            "extra_notes": [9],
            "required_strength": 0.15,
            "required_ratio": 0.50,
        },
        "add9": {
            "extra_notes": [2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
        },
        "9": {
            "extra_notes": [10, 2],
            "required_strength": 0.14,
            "required_ratio": 0.50,
        },
    }

    MINOR_REFINEMENTS = {
        "m7": {
            "extra_notes": [10],
            "required_strength": 0.14,
            "required_ratio": 0.45,
        },
        "m6": {
            "extra_notes": [9],
            "required_strength": 0.15,
            "required_ratio": 0.50,
        },
        "madd9": {
            "extra_notes": [2],
            "required_strength": 0.16,
            "required_ratio": 0.55,
        },
        "m9": {
            "extra_notes": [10, 2],
            "required_strength": 0.14,
            "required_ratio": 0.50,
        },
    }

    def __init__(
        self,
        sample_rate: int = 44100,
        block_size: int = 2048,
        analysis_duration: float = 1.0,
        silence_threshold: float = 0.01,
        minimum_confidence: float = 0.45,
        refinement_margin: float = 0.10,
        history_size: int = 5,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.analysis_duration = analysis_duration
        self.silence_threshold = silence_threshold
        self.minimum_confidence = minimum_confidence
        self.refinement_margin = refinement_margin

        self.audio_queue = queue.Queue()

        self.audio_buffer = deque(
            maxlen=int(
                self.sample_rate
                * self.analysis_duration
            )
        )

        self.prediction_history = deque(
            maxlen=history_size
        )

        self.current_chord = None
        self.current_confidence = 0.0

        self.is_running = False

        self.last_print_time = 0.0

        print(
            "LiveChordDetector initialized "
            f"(sample_rate={self.sample_rate})"
        )

    # ============================================================
    # MICROPHONE CALLBACK
    # ============================================================

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        """Receive microphone audio."""

        if status:
            print(f"Audio status: {status}")

        audio_data = indata[:, 0].copy()

        self.audio_queue.put(audio_data)

    # ============================================================
    # CREATE CHORD TEMPLATE
    # ============================================================

    def _create_template(
        self,
        root: int,
        intervals: list,
    ) -> np.ndarray:
        """Create a normalized chord template."""

        template = np.zeros(
            12,
            dtype=np.float32,
        )

        for position, interval in enumerate(intervals):
            note = (root + interval) % 12

            if position == 0:
                # Give the root slightly more importance.
                template[note] = 1.0
            else:
                template[note] = 0.9

        norm = np.linalg.norm(template)

        if norm > 1e-8:
            template /= norm

        return template

    # ============================================================
    # SCORE CHORD TEMPLATE
    # ============================================================

    def _template_score(
        self,
        chroma: np.ndarray,
        root: int,
        intervals: list,
    ) -> float:
        """Calculate how well a chord matches the chroma."""

        template = self._create_template(
            root,
            intervals,
        )

        chroma_norm = np.linalg.norm(chroma)

        if chroma_norm < 1e-8:
            return 0.0

        similarity = float(
            np.dot(chroma, template)
            / (
                chroma_norm
                * np.linalg.norm(template)
                + 1e-8
            )
        )

        chord_notes = [
            (root + interval) % 12
            for interval in intervals
        ]

        chord_energy = float(
            np.sum(chroma[chord_notes])
        )

        root_energy = float(chroma[root])

        outside_notes = [
            note
            for note in range(12)
            if note not in chord_notes
        ]

        outside_energy = float(
            np.sum(chroma[outside_notes])
        )

        score = (
            0.55 * similarity
            + 0.30 * chord_energy
            + 0.15 * root_energy
            - 0.08 * outside_energy
        )

        return float(score)

    # ============================================================
    # EXTRACT LIVE CHROMA
    # ============================================================

    def _extract_chroma(
        self,
        audio: np.ndarray,
    ) -> Optional[np.ndarray]:
        """Convert microphone audio into a chroma vector."""

        if len(audio) < 1024:
            return None

        rms = float(
            np.sqrt(
                np.mean(audio ** 2)
            )
        )

        # Silence.
        if rms < self.silence_threshold:
            return None

        # Remove DC offset.
        audio = audio - np.mean(audio)

        peak = np.max(np.abs(audio))

        if peak > 1e-8:
            audio = audio / peak

        try:
            # Reduce drums/percussion.
            harmonic_audio, _ = librosa.effects.hpss(
                audio
            )

            chroma = librosa.feature.chroma_stft(
                y=harmonic_audio,
                sr=self.sample_rate,
                n_fft=2048,
                hop_length=512,
                n_chroma=12,
            )

            chroma_vector = np.mean(
                chroma,
                axis=1,
            )

            total = np.sum(chroma_vector)

            if total < 1e-8:
                return None

            chroma_vector = (
                chroma_vector / total
            )

            return chroma_vector.astype(
                np.float32
            )

        except Exception as error:
            print(
                f"Chroma extraction error: {error}"
            )
            return None

    # ============================================================
    # STAGE 1: DETECT BASIC MAJOR/MINOR CHORD
    # ============================================================

    def _detect_basic_chord(
        self,
        chroma: np.ndarray,
    ) -> Tuple[int, str, float]:
        """
        First detect only a basic major/minor chord.

        Examples:
            D
            Dm

        Not yet:
            D9
            Dmaj7
            Dm7
        """

        best_root = 0
        best_family = "major"
        best_score = -np.inf

        for root in range(12):
            for family, intervals in (
                self.BASIC_CHORDS.items()
            ):
                score = self._template_score(
                    chroma,
                    root,
                    intervals,
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
    # STAGE 2: CHECK SPECIAL CHORDS
    # ============================================================

    def _detect_special_chord(
        self,
        chroma: np.ndarray,
        root: int,
        basic_score: float,
    ) -> Optional[Tuple[str, float]]:
        """
        Check sus2, sus4, diminished and augmented chords.

        A special chord must beat the basic chord clearly.
        """

        best_name = None
        best_score = basic_score

        for name, intervals in (
            self.SPECIAL_CHORDS.items()
        ):
            score = self._template_score(
                chroma,
                root,
                intervals,
            )

            if (
                score
                > best_score
                + self.refinement_margin
            ):
                best_score = score
                best_name = name

        if best_name is None:
            return None

        return (
            best_name,
            float(best_score),
        )

    # ============================================================
    # STAGE 3: CONSERVATIVE COMPLEX REFINEMENT
    # ============================================================

    def _refine_chord(
        self,
        chroma: np.ndarray,
        root: int,
        family: str,
        basic_score: float,
    ) -> Tuple[str, float]:
        """
        Upgrade a basic chord only with strong evidence.

        Example:

            Basic result:
                D

            Possible refinements:
                D7
                Dmaj7
                D6
                Dadd9
                D9

            D9 requires both C and E to be clearly present.
        """

        root_name = self.PITCH_CLASSES[root]

        # --------------------------------------------------------
        # CHECK SPECIAL CHORDS FIRST
        # --------------------------------------------------------

        special = self._detect_special_chord(
            chroma,
            root,
            basic_score,
        )

        if special is not None:
            name, score = special

            return (
                f"{root_name}{name}",
                score,
            )

        # --------------------------------------------------------
        # SELECT BASIC CHORD
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
        # CALCULATE MAIN CHORD ENERGY
        # --------------------------------------------------------

        basic_notes = [
            (root + interval) % 12
            for interval in basic_intervals
        ]

        basic_energy = float(
            np.mean(chroma[basic_notes])
        )

        # --------------------------------------------------------
        # TEST COMPLEX CHORDS
        # --------------------------------------------------------

        for name, config in refinements.items():

            extra_notes = config["extra_notes"]

            required_strength = (
                config["required_strength"]
            )

            required_ratio = (
                config["required_ratio"]
            )

            extra_strengths = []

            for interval in extra_notes:
                note = (
                    root + interval
                ) % 12

                extra_strengths.append(
                    float(chroma[note])
                )

            # ----------------------------------------------------
            # RULE 1:
            #
            # EVERY extension note must be strong enough.
            #
            # D9:
            # D F# A C E
            #
            # Both C and E are required.
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
            #
            # Extra notes must be strong relative to the basic
            # chord tones.
            #
            # This prevents a harmonic or microphone noise from
            # turning D into D9.
            # ----------------------------------------------------

            if basic_energy > 1e-8:
                extension_ratio = (
                    average_extra_strength
                    / basic_energy
                )

                if (
                    extension_ratio
                    < required_ratio
                ):
                    continue

            # ----------------------------------------------------
            # RULE 3:
            #
            # Full complex chord template must actually score well.
            # ----------------------------------------------------

            full_intervals = (
                basic_intervals
                + extra_notes
            )

            full_score = self._template_score(
                chroma,
                root,
                full_intervals,
            )

            # ----------------------------------------------------
            # RULE 4:
            #
            # Complex chord must beat the simple chord.
            # ----------------------------------------------------

            if (
                full_score
                <= best_score
                + self.refinement_margin
            ):
                continue

            # Complex chord accepted.
            best_score = full_score

            best_name = (
                f"{root_name}{name}"
            )

        return (
            best_name,
            float(best_score),
        )

    # ============================================================
    # DETECT ONE CHORD
    # ============================================================

    def _detect_chord(
        self,
        chroma: np.ndarray,
    ) -> Tuple[Optional[str], float]:
        """Run the complete chord detection pipeline."""

        if chroma is None:
            return None, 0.0

        # Stage 1.
        root, family, basic_score = (
            self._detect_basic_chord(chroma)
        )

        # Stage 2 + 3.
        chord_name, score = self._refine_chord(
            chroma,
            root,
            family,
            basic_score,
        )

        confidence = float(
            np.clip(
                score,
                0.0,
                1.0,
            )
        )

        if (
            confidence
            < self.minimum_confidence
        ):
            return None, confidence

        return chord_name, confidence

    # ============================================================
    # SMOOTH LIVE PREDICTIONS
    # ============================================================

    def _smooth_prediction(
        self,
        chord: Optional[str],
        confidence: float,
    ) -> Tuple[Optional[str], float]:
        """
        Require a chord to appear repeatedly before changing
        the displayed chord.

        This reduces:
            C -> G -> C -> Am -> C

        false rapid changes.
        """

        # Silence or uncertain audio:
        # keep the previous stable chord.
        if chord is None:
            return (
                self.current_chord,
                self.current_confidence,
            )

        self.prediction_history.append(
            (chord, confidence)
        )

        # Need several predictions before changing.
        if len(self.prediction_history) < 3:
            if self.current_chord is None:
                self.current_chord = chord
                self.current_confidence = confidence

            return (
                self.current_chord,
                self.current_confidence,
            )

        chord_names = [
            item[0]
            for item in self.prediction_history
        ]

        counts = Counter(chord_names)

        most_common_chord, count = (
            counts.most_common(1)[0]
        )

        # Require majority agreement.
        required_votes = max(
            2,
            len(self.prediction_history) // 2 + 1,
        )

        if count >= required_votes:
            matching_confidences = [
                item[1]
                for item in self.prediction_history
                if item[0] == most_common_chord
            ]

            average_confidence = float(
                np.mean(matching_confidences)
            )

            self.current_chord = (
                most_common_chord
            )

            self.current_confidence = (
                average_confidence
            )

        return (
            self.current_chord,
            self.current_confidence,
        )
    
    # ============================================================
    # RECORD FIVE-SECOND CHORD SEQUENCE
    # ============================================================

    def record_chord_sequence(
        self,
        duration: float = 5.0,
        segment_duration: float = 1.0,
        device=None,
    ) -> List[str]:
        """
        Record microphone audio for a fixed duration and detect
        one chord for each segment.

        Default:

            5 seconds
                ↓
            1 second segments
                ↓
            5 detected chords

        Returns:
            A list containing the detected chords.

        Example:
            ["C", "F", "G", "Em", "F"]
        """

        if duration <= 0:
            raise ValueError(
                "Recording duration must be greater than 0."
            )

        if segment_duration <= 0:
            raise ValueError(
                "Segment duration must be greater than 0."
            )

        number_of_segments = int(
            duration / segment_duration
        )

        if number_of_segments <= 0:
            raise ValueError(
                "Duration must be at least one segment."
            )

        print(
            f"\n🎤 Recording {duration:.0f} seconds..."
        )

        print(
            "Play the chords continuously."
        )

        print()

        # --------------------------------------------------------
        # Clear anything left over from previous attempts.
        #
        # This means every new attempt overwrites the previous
        # recording in memory.
        # --------------------------------------------------------

        self.audio_buffer.clear()
        self.prediction_history.clear()

        # Clear old microphone queue.
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        recorded_audio = []

        start_time = time.time()

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
                device=device,
            ):

                while (
                    time.time() - start_time
                    < duration
                ):

                    try:
                        audio_block = (
                            self.audio_queue.get(
                                timeout=0.1
                            )
                        )

                    except queue.Empty:
                        continue

                    recorded_audio.append(
                        audio_block.copy()
                    )

                    elapsed = (
                        time.time() - start_time
                    )

                    remaining = max(
                        0.0,
                        duration - elapsed
                    )

                    print(
                        f"\rRecording: "
                        f"{elapsed:.1f}/{duration:.1f}s",
                        end="",
                        flush=True,
                    )

        except KeyboardInterrupt:
            print(
                "\n\nRecording cancelled."
            )

            return []

        except Exception as error:
            print(
                f"\nRecording error: {error}"
            )

            return []

        print("\n")

        # --------------------------------------------------------
        # Combine all recorded microphone blocks.
        # --------------------------------------------------------

        if not recorded_audio:
            print(
                "No microphone audio was recorded."
            )

            return []

        audio = np.concatenate(
            recorded_audio
        )

        expected_samples = int(
            self.sample_rate * duration
        )

        # Trim to exactly the requested duration.
        audio = audio[:expected_samples]

        # --------------------------------------------------------
        # Split recording into segments.
        # --------------------------------------------------------

        detected_chords = []

        segment_samples = int(
            self.sample_rate
            * segment_duration
        )

        for index in range(
            number_of_segments
        ):

            start = (
                index * segment_samples
            )

            end = (
                start + segment_samples
            )

            segment = audio[start:end]

            if len(segment) < segment_samples:
                break

            # --------------------------------------------
            # Extract chroma from this one-second section.
            # --------------------------------------------

            chroma = self._extract_chroma(
                segment
            )

            # --------------------------------------------
            # Detect chord directly.
            #
            # We intentionally don't use _smooth_prediction()
            # here because we want exactly one chord per
            # recording segment.
            # --------------------------------------------

            chord, confidence = (
                self._detect_chord(chroma)
            )

            if chord is None:
                print(
                    f"  {index + 1}. "
                    f"Unknown "
                    f"(confidence: "
                    f"{confidence:.0%})"
                )

                # Unknown means this recording cannot
                # reliably match a song.
                detected_chords.append(None)

            else:
                print(
                    f"  {index + 1}. "
                    f"{chord:<8} "
                    f"(confidence: "
                    f"{confidence:.0%})"
                )

                detected_chords.append(
                    chord
                )

        # --------------------------------------------------------
        # Validate result.
        # --------------------------------------------------------

        if len(detected_chords) != number_of_segments:
            print(
                "\nCould not obtain five complete "
                "chord segments."
            )

            return []

        if any(
            chord is None
            for chord in detected_chords
        ):
            print(
                "\n⚠ Could not confidently detect "
                "all five chords."
            )

            return []

        return detected_chords

    # ============================================================
    # START LIVE DETECTION
    # ============================================================

    def start_detection(
        self,
        duration: Optional[float] = None,
        device=None,
    ):
        """
        Start detecting chords from the microphone.

        Parameters
        ----------
        duration:
            Number of seconds to listen.
            None means run until Ctrl+C.

        device:
            Microphone device ID or None for the default microphone.
        """

        self.is_running = True

        self.audio_buffer.clear()
        self.prediction_history.clear()

        start_time = time.time()

        print("\n🎸 Live chord detection started.")
        print("Play your instrument into the microphone.")
        print("Press Ctrl+C to stop.\n")

        try:
            with sd.InputStream(
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                channels=1,
                dtype="float32",
                callback=self._audio_callback,
                device=device,
            ):
                while self.is_running:

                    # Stop after requested duration.
                    if (
                        duration is not None
                        and time.time() - start_time
                        >= duration
                    ):
                        break

                    try:
                        audio_block = (
                            self.audio_queue.get(
                                timeout=0.1
                            )
                        )

                    except queue.Empty:
                        continue

                    # Add microphone samples to rolling buffer.
                    self.audio_buffer.extend(
                        audio_block
                    )

                    required_samples = int(
                        self.sample_rate
                        * self.analysis_duration
                    )

                    # Wait until enough audio is available.
                    if (
                        len(self.audio_buffer)
                        < required_samples
                    ):
                        continue

                    audio = np.array(
                        self.audio_buffer,
                        dtype=np.float32,
                    )

                    # Extract chroma.
                    chroma = self._extract_chroma(
                        audio
                    )

                    # Detect chord.
                    chord, confidence = (
                        self._detect_chord(chroma)
                    )

                    # Smooth results.
                    stable_chord, stable_confidence = (
                        self._smooth_prediction(
                            chord,
                            confidence,
                        )
                    )

                    # Print periodically.
                    now = time.time()

                    if (
                        now - self.last_print_time
                        >= 0.25
                    ):
                        self.last_print_time = now

                        if stable_chord is not None:
                            print(
                                f"\r🎵 Chord: "
                                f"{stable_chord:<8} "
                                f"Confidence: "
                                f"{stable_confidence:.0%}",
                                end="",
                                flush=True,
                            )
                        else:
                            print(
                                "\r🎤 Listening...        ",
                                end="",
                                flush=True,
                            )

        except KeyboardInterrupt:
            print("\n\nStopping live chord detection...")

        except Exception as error:
            print(
                f"\nLive detection error: {error}"
            )

        finally:
            self.stop_detection()

    # ============================================================
    # STOP DETECTION
    # ============================================================

    def stop_detection(self):
        """Stop live microphone detection."""

        self.is_running = False

        print("\n🎸 Live chord detection stopped.")

    # ============================================================
    # GET CURRENT RESULT
    # ============================================================

    def get_current_chord(
        self,
    ) -> Tuple[Optional[str], float]:
        """Return the current stable chord."""

        return (
            self.current_chord,
            self.current_confidence,
        )

    # ============================================================
    # LIST AUDIO DEVICES
    # ============================================================

    @staticmethod
    def list_audio_devices():
        """Print available microphone devices."""

        print(sd.query_devices())
