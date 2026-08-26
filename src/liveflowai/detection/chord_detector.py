import queue
from collections import deque

import librosa
import numpy as np
import sounddevice as sd


class LiveChordDetector:
    """
    Live microphone chord detector.

    Detects simple major and minor chords from microphone audio.
    """

    def __init__(
        self,
        sample_rate=22050,
        block_size=4096,
        confidence_threshold=0.30,
        silence_threshold=0.01,
    ):
        self.sample_rate = sample_rate
        self.block_size = block_size
        self.confidence_threshold = confidence_threshold
        self.silence_threshold = silence_threshold

        # Microphone audio waiting to be processed
        self.audio_queue = queue.Queue()

        # Controls the live detection loop
        self.is_running = False

        # Current detected result
        self.current_chord = "None"
        self.confidence = 0.0

        # Store recent predictions to make detection more stable
        self.prediction_history = deque(maxlen=5)

        # The 12 musical pitch classes
        self.pitch_classes = [
            "C", "C#", "D", "D#", "E", "F",
            "F#", "G", "G#", "A", "A#", "B"
        ]

        # Create 12 major + 12 minor chord templates
        self.chord_templates = self._create_chord_templates()

        print("Live Chord Detector initialized!")
        print(f"Sample Rate: {self.sample_rate} Hz")
        print(f"Block Size: {self.block_size} samples")
        print(f"Chord Templates: {len(self.chord_templates)}")
        print("=" * 50)

    def _create_chord_templates(self):
        """
        Create templates for 12 major and 12 minor chords.

        Major chord intervals: 0, 4, 7
        Minor chord intervals: 0, 3, 7
        """

        templates = {}

        chord_types = {
            "": [0, 4, 7],   # Major
            "m": [0, 3, 7],  # Minor
        }

        for root_index, root_name in enumerate(self.pitch_classes):

            for suffix, intervals in chord_types.items():

                template = np.zeros(12, dtype=np.float32)

                for interval in intervals:
                    note_index = (root_index + interval) % 12
                    template[note_index] = 1.0

                chord_name = f"{root_name}{suffix}"
                templates[chord_name] = template

        return templates

    def _audio_callback(
        self,
        indata,
        frames,
        time_info,
        status,
    ):
        """
        Receive live audio from the microphone.
        """

        if status:
            print(f"Microphone status: {status}")

        # Use the first microphone channel
        audio_data = indata[:, 0].copy()

        # Add the microphone audio to the processing queue
        self.audio_queue.put(audio_data)

    def _extract_chroma(self, audio_data):
        """
        Convert microphone audio into a 12-note chroma vector.
        """

        try:
            audio_data = np.asarray(
                audio_data,
                dtype=np.float32,
            )

            if len(audio_data) == 0:
                return None

            # Calculate microphone volume
            rms = np.sqrt(np.mean(audio_data ** 2))

            # Ignore very quiet audio / silence
            if rms < self.silence_threshold:
                return None

            # Pad short audio blocks if necessary
            n_fft = 2048

            if len(audio_data) < n_fft:
                audio_data = np.pad(
                    audio_data,
                    (0, n_fft - len(audio_data)),
                )

            # Focus on harmonic musical content
            harmonic_audio = librosa.effects.harmonic(
                audio_data
            )

            # Extract the 12 musical pitch classes
            chroma = librosa.feature.chroma_stft(
                y=harmonic_audio,
                sr=self.sample_rate,
                n_fft=n_fft,
                hop_length=512,
                n_chroma=12,
            )

            if chroma.size == 0:
                return None

            # Average all chroma frames
            chroma_vector = np.mean(
                chroma,
                axis=1,
            )

            total = np.sum(chroma_vector)

            if total <= 0:
                return None

            # Normalize so the values add up to 1
            chroma_vector = chroma_vector / total

            return chroma_vector

        except Exception as e:
            print(f"Chroma extraction error: {e}")
            return None

    def _score_chord(self, chroma_vector, template):
        """
        Calculate how well the detected notes match a chord.
        """

        chord_notes = template > 0

        # Energy belonging to the three notes of this chord
        chord_energy = np.sum(
            chroma_vector[chord_notes]
        )

        # Energy belonging to notes outside this chord
        other_energy = np.sum(
            chroma_vector[~chord_notes]
        )

        # Get the weakest note in the chord
        note_strengths = chroma_vector[chord_notes]

        weakest_chord_note = np.min(
            note_strengths
        )

        # Calculate final score
        score = (
            chord_energy
            - (other_energy * 0.10)
            + (weakest_chord_note * 0.20)
        )

        return float(max(0.0, score))

    def _detect_chord(self, chroma_vector):
        """
        Find the best matching major or minor chord.
        """

        if chroma_vector is None:
            return "None", 0.0

        scores = {}

        # Score every chord
        for chord_name, template in self.chord_templates.items():

            score = self._score_chord(
                chroma_vector,
                template,
            )

            scores[chord_name] = score

        # Find the highest-scoring chord
        best_chord = max(
            scores,
            key=scores.get,
        )

        best_score = scores[best_chord]

        # Keep confidence between 0 and 1
        confidence = min(1.0, best_score)

        # Reject weak matches
        if confidence < self.confidence_threshold:
            return "None", confidence

        return best_chord, confidence

    def _smooth_prediction(
        self,
        chord,
        confidence,
    ):
        """
        Smooth predictions using recent detections.

        This helps reduce random flickering between chords.
        """

        self.prediction_history.append(
            (chord, confidence)
        )

        # Need at least 3 predictions before smoothing
        if len(self.prediction_history) < 3:
            return chord, confidence

        chord_counts = {}

        # Count how often each chord appears
        for detected_chord, _ in self.prediction_history:

            if detected_chord != "None":
                chord_counts[detected_chord] = (
                    chord_counts.get(detected_chord, 0) + 1
                )

        # No valid chords recently
        if not chord_counts:
            return "None", 0.0

        # Find the most common recent chord
        most_common_chord = max(
            chord_counts,
            key=chord_counts.get,
        )

        count = chord_counts[most_common_chord]

        # Require the chord to appear at least twice
        if count < 2:
            return chord, confidence

        # Get confidence values for that chord
        matching_confidences = [
            conf
            for detected_chord, conf in self.prediction_history
            if detected_chord == most_common_chord
        ]

        average_confidence = float(
            np.mean(matching_confidences)
        )

        return most_common_chord, average_confidence

    def start_detection(self):
        """
        Start continuous live microphone chord detection.

        Press Ctrl+C to stop.
        """

        self.is_running = True
        self.prediction_history.clear()

        # Remove old audio from previous runs
        while not self.audio_queue.empty():
            try:
                self.audio_queue.get_nowait()
            except queue.Empty:
                break

        print("\nStarting LIVE microphone chord detection...")
        print("Play a chord near your microphone.")
        print("Press Ctrl+C to stop.")
        print("=" * 50)

        try:
            with sd.InputStream(
                callback=self._audio_callback,
                channels=1,
                samplerate=self.sample_rate,
                blocksize=self.block_size,
            ):

                # CONTINUOUS LIVE DETECTION LOOP
                while self.is_running:

                    try:
                        # Wait for microphone audio
                        audio_data = self.audio_queue.get(
                            timeout=0.5
                        )

                    except queue.Empty:
                        continue

                    # Convert microphone audio into musical notes
                    chroma_vector = self._extract_chroma(
                        audio_data
                    )

                    # Find the best chord
                    chord, confidence = self._detect_chord(
                        chroma_vector
                    )

                    # Smooth the result
                    chord, confidence = self._smooth_prediction(
                        chord,
                        confidence
                    )

                    # Save the latest result
                    self.current_chord = chord
                    self.confidence = confidence

                    # Print EVERY successful detection
                    # This lets you confirm the live loop is running.
                    if chord != "None":
                        print(
                            f"Chord: {chord} | "
                            f"Confidence: {confidence:.2%}"
                        )

        except KeyboardInterrupt:
            print("\nStopping microphone detection...")

        except Exception as e:
            print(f"\nMicrophone error: {e}")

        finally:
            self.is_running = False
            print("Live chord detection stopped.")

    def stop_detection(self):
        """
        Stop the live microphone detection loop.
        """

        self.is_running = False

    def get_current_chord(self):
        """
        Return the most recently detected chord.
        """

        return {
            "chord": self.current_chord,
            "confidence": self.confidence,
        }