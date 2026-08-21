import time
import queue
from collections import deque
from pathlib import Path

import librosa
import numpy as np
import sounddevice as sd


class LiveChordDetector:
    """
    Detect major and minor chords from an audio file or microphone input.

    This detector intentionally uses only simple major and minor chord
    templates to reduce false detections and chord over-classification.
    """

    def __init__(
        self,
        sample_rate=22050,
        block_size=4096,
        hop_length=512,
        confidence_threshold=0.35,
        silence_threshold=0.01,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.hop_length = hop_length
        self.confidence_threshold = confidence_threshold
        self.silence_threshold = silence_threshold

        self.audio_queue = queue.Queue()
        self.is_running = False

        self.n_chroma = 12
        self.n_fft = 2048

        self.pitch_classes = [
            "C", "C#", "D", "D#", "E", "F",
            "F#", "G", "G#", "A", "A#", "B"
        ]

        # Keep recent predictions for smoothing
        self.prediction_history = deque(maxlen=5)

        self.current_chord = "None"
        self.confidence = 0.0

        self.chord_templates = self._create_chord_templates()
        self.chord_names = list(self.chord_templates.keys())

        print("Live Chord Detector initialized!")
        print(f"Sample Rate: {self.sample_rate} Hz")
        print(f"Block Size: {self.block_size} samples")
        print(f"Chord Templates: {len(self.chord_templates)}")
        print("=" * 50)

    def _create_chord_templates(self):
        """
        Create templates for simple major and minor chords.

        Major chord:
            Root + major third + perfect fifth

        Minor chord:
            Root + minor third + perfect fifth
        """

        templates = {}

        chord_intervals = {
            "": [0, 4, 7],   # Major
            "m": [0, 3, 7],  # Minor
        }

        for root_index, root_name in enumerate(self.pitch_classes):
            for chord_type, intervals in chord_intervals.items():

                template = np.zeros(
                    self.n_chroma,
                    dtype=np.float32
                )

                for interval in intervals:
                    note_index = (
                        root_index + interval
                    ) % self.n_chroma

                    template[note_index] = 1.0

                chord_name = f"{root_name}{chord_type}"
                templates[chord_name] = template

        return templates

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status
    ):
        """Receive microphone audio."""

        if status:
            print(f"Audio callback status: {status}")

        audio_data = indata[:, 0].copy()
        self.audio_queue.put(audio_data)

    def _extract_chroma(self, audio_block):
        """
        Extract a normalized 12-note chroma vector.
        """

        try:
            audio_block = np.asarray(
                audio_block,
                dtype=np.float32
            )

            if len(audio_block) == 0:
                return None

            # Detect very quiet or silent audio
            rms = np.sqrt(np.mean(audio_block ** 2))

            if rms < self.silence_threshold:
                return None

            # Ensure enough samples for analysis
            if len(audio_block) < self.n_fft:
                audio_block = np.pad(
                    audio_block,
                    (0, self.n_fft - len(audio_block))
                )

            # Separate harmonic content from percussion
            harmonic_audio = librosa.effects.harmonic(
                audio_block
            )

            # Extract chroma using STFT
            chroma = librosa.feature.chroma_stft(
                y=harmonic_audio,
                sr=self.sample_rate,
                n_fft=self.n_fft,
                hop_length=self.hop_length,
                n_chroma=self.n_chroma,
            )

            if chroma.size == 0:
                return None

            # Median is more stable than a single frame
            chroma_vector = np.median(
                chroma,
                axis=1
            )

            total = np.sum(chroma_vector)

            if total <= 0:
                return None

            return chroma_vector / total

        except Exception as e:
            print(f"Error extracting chroma: {e}")
            return None

    def _score_chord(self, chroma_vector, template):
        """
        Score how well the chroma vector matches a chord template.

        The score rewards energy on the three expected chord notes and
        penalizes energy on other notes.
        """

        chord_note_mask = template > 0

        # Energy belonging to the expected chord notes
        chord_energy = np.sum(
            chroma_vector[chord_note_mask]
        )

        # Energy belonging to notes outside the chord
        non_chord_energy = np.sum(
            chroma_vector[~chord_note_mask]
        )

        # Calculate average strength of the three chord notes
        expected_notes = chroma_vector[
            chord_note_mask
        ]

        note_balance = np.mean(expected_notes)

        # Penalize weak chord-note balance
        minimum_note_strength = np.min(
            expected_notes
        )

        # Main score
        score = (
            chord_energy * 0.70
            + note_balance * 0.20
            + minimum_note_strength * 0.10
            - non_chord_energy * 0.20
        )

        return float(max(0.0, score))

    def _detect_chord(self, chroma_vector):
        """
        Find the best matching major or minor chord.
        """

        if chroma_vector is None:
            return "None", 0.0

        try:
            scores = {}

            for chord_name, template in (
                self.chord_templates.items()
            ):
                score = self._score_chord(
                    chroma_vector,
                    template
                )

                scores[chord_name] = score

            if not scores:
                return "None", 0.0

            best_chord = max(
                scores,
                key=scores.get
            )

            best_score = scores[best_chord]

            # Convert the score to a 0-1 confidence estimate
            confidence = min(
                1.0,
                best_score
            )

            if confidence < self.confidence_threshold:
                return "None", confidence

            return best_chord, confidence

        except Exception as e:
            print(f"Error detecting chord: {e}")
            return "None", 0.0

    def _smooth_predictions(
        self,
        chord,
        confidence
    ):
        """
        Smooth predictions using a majority vote.

        A chord must appear multiple times in the recent history before
        it is considered stable.
        """

        self.prediction_history.append(
            (chord, confidence)
        )

        # Do not smooth until enough predictions exist
        if len(self.prediction_history) < 3:
            return chord, confidence

        chord_counts = {}

        for detected_chord, _ in self.prediction_history:
            chord_counts[detected_chord] = (
                chord_counts.get(
                    detected_chord,
                    0
                ) + 1
            )

        most_common_chord = max(
            chord_counts,
            key=chord_counts.get
        )

        # Require at least 3 matching predictions
        if (
            most_common_chord != "None"
            and chord_counts[most_common_chord] >= 3
        ):
            confidences = [
                conf
                for detected_chord, conf
                in self.prediction_history
                if detected_chord == most_common_chord
            ]

            average_confidence = float(
                np.mean(confidences)
            )

            return (
                most_common_chord,
                average_confidence
            )

        return chord, confidence

    def start_detection(self, duration=None):
        """
        Start live chord detection from the microphone.
        """

        self.is_running = True
        self.prediction_history.clear()

        print("\nStarting live chord detection...")
        print("Press Ctrl+C to stop")
        print("=" * 50)

        last_printed_chord = None

        try:
            with sd.InputStream(
                callback=self._audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
                device=None,
            ):
                start_time = time.time()

                while self.is_running:

                    if (
                        duration is not None
                        and time.time() - start_time >= duration
                    ):
                        break

                    try:
                        audio_data = self.audio_queue.get(
                            timeout=0.1
                        )

                    except queue.Empty:
                        continue

                    chroma = self._extract_chroma(
                        audio_data
                    )

                    chord, confidence = self._detect_chord(
                        chroma
                    )

                    chord, confidence = (
                        self._smooth_predictions(
                            chord,
                            confidence
                        )
                    )

                    self.current_chord = chord
                    self.confidence = confidence

                    # Only print when the stable chord changes
                    if (
                        chord != "None"
                        and chord != last_printed_chord
                    ):
                        print(
                            f"Chord: {chord} | "
                            f"Confidence: {confidence:.2%}"
                        )

                        last_printed_chord = chord

        except KeyboardInterrupt:
            print("\nStopping chord detection...")

        except Exception as e:
            print(f"Error in live chord detection: {e}")

        finally:
            self.is_running = False
            print("=" * 50)
            print("Chord detection stopped")

    def stop_detection(self):
        """Stop live chord detection."""

        self.is_running = False

    def detect_from_file(self, audio_path):
        """
        Detect stable chords from an audio file.

        Compatible with your existing main.py:

            chords, timestamps = chord_detector.detect_from_file(
                file_path
            )
        """

        audio_path = Path(audio_path)

        if not audio_path.exists():
            raise FileNotFoundError(
                f"Audio file not found: {audio_path}"
            )

        print(
            f"\nDetecting chords from: {audio_path.name}"
        )
        print("=" * 50)

        try:
            audio, sr = librosa.load(
                audio_path,
                sr=self.sample_rate,
                mono=True
            )

            self.prediction_history.clear()

            # Use a 2-second window for better chord stability.
            # Move forward every 0.5 seconds.
            window_duration = 2.0
            hop_duration = 0.5

            window_size = int(
                self.sample_rate * window_duration
            )

            hop_size = int(
                self.sample_rate * hop_duration
            )

            raw_predictions = []

            # Analyze complete windows
            for start in range(
                0,
                len(audio) - window_size + 1,
                hop_size
            ):
                audio_chunk = audio[
                    start:start + window_size
                ]

                chroma = self._extract_chroma(
                    audio_chunk
                )

                chord, confidence = self._detect_chord(
                    chroma
                )

                timestamp = (
                    start / self.sample_rate
                )

                raw_predictions.append({
                    "timestamp": timestamp,
                    "chord": chord,
                    "confidence": confidence,
                })

            chords_detected = []
            timestamps = []

            current_chord = "None"
            candidate_chord = None
            candidate_count = 0
            candidate_start_time = 0.0

            # Require the same chord in 3 consecutive windows.
            minimum_stable_windows = 3

            for prediction in raw_predictions:

                chord = prediction["chord"]
                timestamp = prediction["timestamp"]

                # Ignore silence or low-confidence predictions
                if chord == "None":
                    candidate_chord = None
                    candidate_count = 0
                    continue

                if chord == candidate_chord:
                    candidate_count += 1

                else:
                    candidate_chord = chord
                    candidate_count = 1
                    candidate_start_time = timestamp

                # Add only confirmed chord changes
                if (
                    candidate_count >= minimum_stable_windows
                    and chord != current_chord
                ):
                    chords_detected.append(chord)
                    timestamps.append(
                        candidate_start_time
                    )

                    print(
                        f"Time: "
                        f"{candidate_start_time:.2f}s | "
                        f"Chord: {chord}"
                    )

                    current_chord = chord

            return chords_detected, timestamps

        except Exception as e:
            print(f"Error processing audio file: {e}")
            return [], []

    def analyze_file(self, audio_path):
        """
        Compatibility method for file-based analysis.
        """

        return self.detect_from_file(audio_path)

    def get_current_chord(self):
        """
        Return the current chord and confidence.
        """

        return {
            "chord": self.current_chord,
            "confidence": self.confidence,
        }

    def get_chord_list(self):
        """
        Return all supported chords.
        """

        return list(self.chord_templates.keys())


def detect_chords(audio_path, sample_rate=22050):
    """
    Convenience function for chord detection.
    """

    detector = LiveChordDetector(
        sample_rate=sample_rate
    )

    return detector.detect_from_file(audio_path)