import numpy as np
import librosa
from collections import Counter


class LiveChordDetector:
    """
    Analyze chord changes from an audio file.

    Detects 12 major chords and 12 minor chords and attempts
    to produce clean, non-overlapping chord sections.
    """

    def __init__(
        self,
        sample_rate=22050,
        window_seconds=1.5,
        hop_seconds=0.5,
        confidence_threshold=0.35,
        min_chord_duration=1.0,
    ):
        self.sample_rate = sample_rate
        self.window_seconds = window_seconds
        self.hop_seconds = hop_seconds
        self.confidence_threshold = confidence_threshold
        self.min_chord_duration = min_chord_duration

        self.n_fft = 2048
        self.hop_length = 512

        self.pitch_classes = [
            "C", "C#", "D", "D#", "E", "F",
            "F#", "G", "G#", "A", "A#", "B"
        ]

        self.chord_templates = self._create_chord_templates()

        print("Chord Analyzer initialized!")
        print(f"Sample Rate: {self.sample_rate} Hz")
        print(f"Chord Templates: {len(self.chord_templates)}")

    def _create_chord_templates(self):
        """
        Create templates for:

        - 12 major chords
        - 12 minor chords
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

                # Normalize the template
                norm = np.linalg.norm(template)

                if norm > 0:
                    template /= norm

                chord_name = f"{root_name}{suffix}"

                templates[chord_name] = template

        return templates

    def _detect_chord(self, chroma_vector):
        """
        Compare one chroma vector against all chord templates.
        """

        if chroma_vector is None:
            return "None", 0.0

        norm = np.linalg.norm(chroma_vector)

        if norm == 0:
            return "None", 0.0

        chroma_vector = chroma_vector / norm

        scores = {}

        for chord_name, template in self.chord_templates.items():

            score = np.dot(chroma_vector, template)

            scores[chord_name] = float(score)

        best_chord = max(scores, key=scores.get)
        best_score = scores[best_chord]

        # Reject weak matches
        if best_score < self.confidence_threshold:
            return "None", best_score

        return best_chord, best_score

    def _get_window_chroma(self, audio_window):
        """
        Extract the average chroma vector from one audio window.
        """

        if len(audio_window) == 0:
            return None

        # Ignore silence
        rms = np.sqrt(np.mean(audio_window ** 2))

        if rms < 0.01:
            return None

        # Make sure the window is large enough for STFT
        if len(audio_window) < self.n_fft:

            audio_window = np.pad(
                audio_window,
                (0, self.n_fft - len(audio_window)),
            )

        # Keep mainly harmonic content
        harmonic_audio = librosa.effects.harmonic(
            audio_window
        )

        chroma = librosa.feature.chroma_stft(
            y=harmonic_audio,
            sr=self.sample_rate,
            n_fft=self.n_fft,
            hop_length=self.hop_length,
            n_chroma=12,
        )

        if chroma.size == 0:
            return None

        chroma_vector = np.mean(chroma, axis=1)

        return chroma_vector

    def _smooth_predictions(self, predictions):
        """
        Smooth noisy chord predictions.

        Each prediction is replaced by the most common chord
        in its nearby neighborhood.
        """

        if not predictions:
            return []

        smoothed = []

        radius = 2

        for index, prediction in enumerate(predictions):

            start = max(0, index - radius)
            end = min(
                len(predictions),
                index + radius + 1,
            )

            neighborhood = predictions[start:end]

            valid_chords = [
                item["chord"]
                for item in neighborhood
                if item["chord"] != "None"
            ]

            if not valid_chords:

                smoothed.append({
                    **prediction,
                    "chord": "None",
                    "confidence": 0.0,
                })

                continue

            chord_counts = Counter(valid_chords)

            most_common_chord, count = (
                chord_counts.most_common(1)[0]
            )

            # Get confidence scores for this chord
            matching_confidences = [
                item["confidence"]
                for item in neighborhood
                if item["chord"] == most_common_chord
            ]

            average_confidence = float(
                np.mean(matching_confidences)
            )

            smoothed.append({
                **prediction,
                "chord": most_common_chord,
                "confidence": average_confidence,
            })

        return smoothed

    def _create_non_overlapping_sections(
        self,
        predictions,
        audio_duration,
    ):
        """
        Convert overlapping analysis windows into clean,
        non-overlapping chord sections.
        """

        if not predictions:
            return []

        sections = []

        current_chord = predictions[0]["chord"]
        current_start = predictions[0]["center_time"]
        confidence_values = [
            predictions[0]["confidence"]
        ]

        for prediction in predictions[1:]:

            chord = prediction["chord"]
            center_time = prediction["center_time"]

            if chord == current_chord:

                confidence_values.append(
                    prediction["confidence"]
                )

            else:

                # Save previous section
                if current_chord != "None":

                    average_confidence = float(
                        np.mean(confidence_values)
                    )

                    sections.append({
                        "start_time": current_start,
                        "end_time": center_time,
                        "chord": current_chord,
                        "confidence": average_confidence,
                    })

                # Start new section
                current_chord = chord
                current_start = center_time

                confidence_values = [
                    prediction["confidence"]
                ]

        # Add final section
        if current_chord != "None":

            average_confidence = float(
                np.mean(confidence_values)
            )

            sections.append({
                "start_time": current_start,
                "end_time": audio_duration,
                "chord": current_chord,
                "confidence": average_confidence,
            })

        return sections

    def _remove_short_sections(self, sections):
        """
        Remove very short chord changes.

        A short section is treated as noise and merged with
        the previous or next chord when possible.
        """

        if len(sections) <= 1:
            return sections

        cleaned = []

        index = 0

        while index < len(sections):

            section = sections[index]

            duration = (
                section["end_time"]
                - section["start_time"]
            )

            # Keep sections that are long enough
            if duration >= self.min_chord_duration:

                cleaned.append(section.copy())

                index += 1
                continue

            # Short section: try to merge with previous
            if cleaned:

                cleaned[-1]["end_time"] = (
                    section["end_time"]
                )

                cleaned[-1]["confidence"] = (
                    cleaned[-1]["confidence"]
                    + section["confidence"]
                ) / 2

                index += 1
                continue

            # If this is the first section, keep it
            cleaned.append(section.copy())

            index += 1

        return cleaned

    def _fix_section_boundaries(self, sections):
        """
        Ensure every section connects cleanly to the next section.
        """

        if not sections:
            return []

        for index in range(len(sections) - 1):

            boundary = sections[index]["end_time"]

            sections[index + 1]["start_time"] = boundary

        return sections

    def analyze_file(
        self,
        audio_path,
        window_seconds=None,
    ):
        """
        Analyze an audio file and return clean chord changes.

        Returns a list like:

        [
            {
                "start_time": 0.0,
                "end_time": 3.5,
                "chord": "C",
                "confidence": 0.82
            },
            ...
        ]
        """

        if window_seconds is None:
            window_seconds = self.window_seconds

        print(f"\nAnalyzing chord changes from: {audio_path}")

        # Load the audio file
        y, sr = librosa.load(
            audio_path,
            sr=self.sample_rate,
            mono=True,
        )

        audio_duration = len(y) / sr

        window_samples = int(
            window_seconds * sr
        )

        hop_samples = int(
            self.hop_seconds * sr
        )

        predictions = []

        # ----------------------------------------------------------
        # Analyze the song in overlapping windows
        # ----------------------------------------------------------
        for start_sample in range(
            0,
            len(y),
            hop_samples,
        ):

            end_sample = (
                start_sample + window_samples
            )

            audio_window = y[
                start_sample:end_sample
            ]

            # Stop if the final chunk is too small
            if len(audio_window) < sr * 0.5:
                break

            chroma_vector = self._get_window_chroma(
                audio_window
            )

            chord, confidence = self._detect_chord(
                chroma_vector
            )

            start_time = start_sample / sr

            actual_end_sample = min(
                end_sample,
                len(y),
            )

            end_time = actual_end_sample / sr

            center_time = (
                start_time + end_time
            ) / 2

            predictions.append({
                "start_time": start_time,
                "end_time": end_time,
                "center_time": center_time,
                "chord": chord,
                "confidence": confidence,
            })

        # ----------------------------------------------------------
        # Smooth noisy chord predictions
        # ----------------------------------------------------------
        predictions = self._smooth_predictions(
            predictions
        )

        # ----------------------------------------------------------
        # Convert windows into non-overlapping sections
        # ----------------------------------------------------------
        sections = (
            self._create_non_overlapping_sections(
                predictions,
                audio_duration,
            )
        )

        # ----------------------------------------------------------
        # Remove short noisy sections
        # ----------------------------------------------------------
        sections = self._remove_short_sections(
            sections
        )

        # ----------------------------------------------------------
        # Ensure clean boundaries
        # ----------------------------------------------------------
        sections = self._fix_section_boundaries(
            sections
        )

        return sections