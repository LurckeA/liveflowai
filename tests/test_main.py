# tests/test_main.py

import sys
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np


# Add the src directory to Python's import path.
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from liveflowai.main import main
from liveflowai.audio.tempo_analyzer import TempoAnalyzer
from liveflowai.detection.chord_detector import LiveChordDetector


class TestMainFunction(unittest.TestCase):
    """Tests for the main() function."""

    def setUp(self):
        self.expected_audio_path = (
            PROJECT_ROOT
            / "data"
            / "songs"
            / "Mary Had a Little Lamb.mp3"
        )

    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.TempoAnalyzer")
    def test_main_successful_execution(
        self,
        mock_tempo_analyzer,
        mock_chord_detector,
    ):
        """main() should run all analysis steps successfully."""

        mock_tempo_instance = MagicMock()

        mock_tempo_instance.detect_tempo.return_value = {
            "tempo_bpm": 120.0,
            "tempo_onset": 118.0,
            "duration": 30.0,
            "num_beats": 60,
        }

        mock_tempo_instance.get_beat_confidence.return_value = {
            "avg_beat_strength": 0.8,
            "beat_strength_std": 0.1,
            "confidence_score": 0.85,
        }

        mock_tempo_analyzer.return_value = mock_tempo_instance

        mock_chord_instance = MagicMock()

        mock_chord_instance.detect_from_file.return_value = (
            ["C", "G", "Am"],
            [0.0, 2.0, 4.0],
        )

        mock_chord_detector.return_value = mock_chord_instance

        with patch("builtins.print") as mock_print:
            with patch("liveflowai.main.sys.exit") as mock_exit:
                main()

        mock_exit.assert_not_called()

        mock_tempo_analyzer.assert_called_once_with(
            sample_rate=22050
        )

        mock_chord_detector.assert_called_once_with(
            sample_rate=22050
        )

        mock_tempo_instance.detect_tempo.assert_called_once_with(
            self.expected_audio_path
        )

        mock_tempo_instance.get_beat_confidence.assert_called_once_with(
            self.expected_audio_path
        )

        mock_tempo_instance.visualize_tempo.assert_called_once_with(
            self.expected_audio_path
        )

        mock_chord_instance.detect_from_file.assert_called_once_with(
            self.expected_audio_path
        )

        mock_print.assert_any_call(
            "Tempo: 120.00 BPM"
        )

        mock_print.assert_any_call(
            "Duration: 30.00 seconds"
        )

        mock_print.assert_any_call(
            "Number of beats: 60"
        )

        mock_print.assert_any_call(
            "Confidence score: 0.85"
        )

        mock_print.assert_any_call(
            "\nDetected chords:"
        )

        mock_print.assert_any_call(
            "0.00s: C"
        )

        mock_print.assert_any_call(
            "2.00s: G"
        )

        mock_print.assert_any_call(
            "4.00s: Am"
        )

    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.TempoAnalyzer")
    def test_main_handles_file_not_found(
        self,
        mock_tempo_analyzer,
        mock_chord_detector,
    ):
        """main() should print an error and exit when audio is missing."""

        mock_tempo_instance = MagicMock()

        mock_tempo_instance.detect_tempo.side_effect = (
            FileNotFoundError("Audio file not found")
        )

        mock_tempo_analyzer.return_value = mock_tempo_instance

        with patch("builtins.print") as mock_print:
            with patch("liveflowai.main.sys.exit") as mock_exit:
                main()

        mock_exit.assert_called_once_with(1)

        mock_print.assert_called_once_with(
            "Error: Audio file not found"
        )

        mock_chord_detector.return_value.detect_from_file.assert_not_called()

    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.TempoAnalyzer")
    def test_main_handles_general_exception(
        self,
        mock_tempo_analyzer,
        mock_chord_detector,
    ):
        """main() should handle unexpected exceptions."""

        mock_tempo_instance = MagicMock()

        mock_tempo_instance.detect_tempo.side_effect = Exception(
            "Unexpected error"
        )

        mock_tempo_analyzer.return_value = mock_tempo_instance

        with patch("builtins.print") as mock_print:
            with patch("liveflowai.main.sys.exit") as mock_exit:
                main()

        mock_exit.assert_called_once_with(1)

        mock_print.assert_called_once_with(
            "Error: Unexpected error"
        )

        mock_chord_detector.return_value.detect_from_file.assert_not_called()

    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.TempoAnalyzer")
    def test_main_handles_chord_detector_exception(
        self,
        mock_tempo_analyzer,
        mock_chord_detector,
    ):
        """main() should handle an exception from chord detection."""

        mock_tempo_instance = MagicMock()

        mock_tempo_instance.detect_tempo.return_value = {
            "tempo_bpm": 120.0,
            "tempo_onset": 120.0,
            "duration": 30.0,
            "num_beats": 60,
        }

        mock_tempo_instance.get_beat_confidence.return_value = {
            "avg_beat_strength": 0.8,
            "beat_strength_std": 0.1,
            "confidence_score": 0.85,
        }

        mock_tempo_analyzer.return_value = mock_tempo_instance

        mock_chord_instance = MagicMock()

        mock_chord_instance.detect_from_file.side_effect = Exception(
            "Chord detection failed"
        )

        mock_chord_detector.return_value = mock_chord_instance

        with patch("builtins.print") as mock_print:
            with patch("liveflowai.main.sys.exit") as mock_exit:
                main()

        mock_exit.assert_called_once_with(1)

        mock_print.assert_any_call(
            "Error: Chord detection failed"
        )


class TestTempoAnalyzer(unittest.TestCase):
    """Tests for TempoAnalyzer."""

    def setUp(self):
        self.analyzer = TempoAnalyzer(
            sample_rate=22050
        )

    def test_initialization(self):
        """TempoAnalyzer should initialize with expected values."""

        self.assertEqual(
            self.analyzer.sample_rate,
            22050,
        )

        self.assertIsNone(
            self.analyzer.tempo
        )

        self.assertIsNone(
            self.analyzer.beats
        )

        self.assertIsNone(
            self.analyzer.beat_times
        )

    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.load"
    )
    def test_load_audio_success(
        self,
        mock_load,
    ):
        """load_audio() should return audio and sample rate."""

        fake_audio = np.array(
            [0.1, 0.2, 0.3],
            dtype=np.float32,
        )

        mock_load.return_value = (
            fake_audio,
            22050,
        )

        audio, sample_rate = self.analyzer.load_audio(
            "song.mp3"
        )

        mock_load.assert_called_once_with(
            "song.mp3",
            sr=22050,
        )

        np.testing.assert_array_equal(
            audio,
            fake_audio,
        )

        self.assertEqual(
            sample_rate,
            22050,
        )

    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.load"
    )
    def test_load_audio_failure(
        self,
        mock_load,
    ):
        """load_audio() should wrap loading errors in ValueError."""

        mock_load.side_effect = FileNotFoundError(
            "File does not exist"
        )

        with self.assertRaisesRegex(
            ValueError,
            "Failed to load audio",
        ):
            self.analyzer.load_audio(
                "missing.mp3"
            )

    # IMPORTANT:
    # The mock arguments are in reverse order from the decorators.
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.get_duration"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.frames_to_time"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.feature.tempo"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.onset.onset_strength"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.beat.beat_track"
    )
    @patch.object(
        TempoAnalyzer,
        "load_audio",
    )
    def test_detect_tempo_success(
        self,
        mock_load_audio,
        mock_beat_track,
        mock_onset_strength,
        mock_feature_tempo,
        mock_frames_to_time,
        mock_get_duration,
    ):
        """detect_tempo() should return and store analysis results."""

        fake_audio = np.array(
            [0.1, 0.2, 0.3],
            dtype=np.float32,
        )

        fake_beats = np.array(
            [10, 20, 30]
        )

        fake_beat_times = np.array(
            [0.5, 1.0, 1.5]
        )

        mock_load_audio.return_value = (
            fake_audio,
            22050,
        )

        mock_beat_track.return_value = (
            np.array([120.0]),
            fake_beats,
        )

        mock_onset_strength.return_value = np.array(
            [0.1, 0.3, 0.5]
        )

        mock_feature_tempo.return_value = np.array(
            [118.0]
        )

        mock_frames_to_time.return_value = (
            fake_beat_times
        )

        mock_get_duration.return_value = 10.0

        result = self.analyzer.detect_tempo(
            "song.mp3"
        )

        mock_load_audio.assert_called_once_with(
            "song.mp3"
        )

        mock_beat_track.assert_called_once_with(
            y=fake_audio,
            sr=22050,
        )

        mock_onset_strength.assert_called_once_with(
            y=fake_audio,
            sr=22050,
        )

        mock_feature_tempo.assert_called_once_with(
            onset_envelope=mock_onset_strength.return_value,
            sr=22050,
        )

        mock_frames_to_time.assert_called_once_with(
            fake_beats,
            sr=22050,
        )

        mock_get_duration.assert_called_once_with(
            y=fake_audio,
            sr=22050,
        )

        self.assertEqual(
            result["tempo_bpm"],
            120.0,
        )

        self.assertEqual(
            result["tempo_onset"],
            118.0,
        )

        self.assertEqual(
            result["num_beats"],
            3,
        )

        self.assertEqual(
            result["duration"],
            10.0,
        )

        self.assertEqual(
            self.analyzer.tempo,
            120.0,
        )

        np.testing.assert_array_equal(
            self.analyzer.beats,
            fake_beats,
        )

        np.testing.assert_array_equal(
            self.analyzer.beat_times,
            fake_beat_times,
        )

    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.beat.beat_track"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.onset.onset_strength"
    )
    @patch.object(
        TempoAnalyzer,
        "load_audio",
    )
    def test_get_beat_confidence_no_beats(
        self,
        mock_load_audio,
        mock_onset_strength,
        mock_beat_track,
    ):
        """Confidence should be zero when no beats are detected."""

        mock_load_audio.return_value = (
            np.array([0.1, 0.2]),
            22050,
        )

        mock_onset_strength.return_value = np.array(
            [0.1, 0.2]
        )

        mock_beat_track.return_value = (
            120.0,
            np.array([]),
        )

        result = self.analyzer.get_beat_confidence(
            "song.mp3"
        )

        self.assertEqual(
            result["avg_beat_strength"],
            0.0,
        )

        self.assertEqual(
            result["beat_strength_std"],
            0.0,
        )

        self.assertEqual(
            result["confidence_score"],
            0.0,
        )

    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.time_to_frames"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.frames_to_time"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.beat.beat_track"
    )
    @patch(
        "liveflowai.audio.tempo_analyzer.librosa.onset.onset_strength"
    )
    @patch.object(
        TempoAnalyzer,
        "load_audio",
    )
    def test_get_beat_confidence_success(
        self,
        mock_load_audio,
        mock_onset_strength,
        mock_beat_track,
        mock_frames_to_time,
        mock_time_to_frames,
    ):
        """get_beat_confidence() should calculate confidence."""

        fake_audio = np.array(
            [0.1, 0.2, 0.3],
            dtype=np.float32,
        )

        fake_onset_env = np.array(
            [1.0, 2.0, 4.0, 2.0]
        )

        fake_beats = np.array(
            [1, 2]
        )

        fake_beat_positions = np.array(
            [0.5, 1.0]
        )

        fake_beat_frames = np.array(
            [1, 2]
        )

        mock_load_audio.return_value = (
            fake_audio,
            22050,
        )

        mock_onset_strength.return_value = (
            fake_onset_env
        )

        mock_beat_track.return_value = (
            120.0,
            fake_beats,
        )

        mock_frames_to_time.return_value = (
            fake_beat_positions
        )

        mock_time_to_frames.return_value = (
            fake_beat_frames
        )

        result = self.analyzer.get_beat_confidence(
            "song.mp3"
        )

        mock_load_audio.assert_called_once_with(
            "song.mp3"
        )

        mock_onset_strength.assert_called_once_with(
            y=fake_audio,
            sr=22050,
        )

        mock_beat_track.assert_called_once_with(
            y=fake_audio,
            sr=22050,
        )

        mock_frames_to_time.assert_called_once_with(
            fake_beats,
            sr=22050,
        )

        mock_time_to_frames.assert_called_once_with(
            fake_beat_positions,
            sr=22050,
        )

        self.assertEqual(
            result["avg_beat_strength"],
            3.0,
        )

        self.assertEqual(
            result["beat_strength_std"],
            1.0,
        )

        self.assertEqual(
            result["confidence_score"],
            0.75,
        )


class TestLiveChordDetector(unittest.TestCase):
    """Tests for LiveChordDetector."""

    def setUp(self):
        with patch("builtins.print"):
            self.detector = LiveChordDetector(
                sample_rate=22050
            )

    def test_initialization(self):
        """Detector should initialize with expected defaults."""

        self.assertEqual(
            self.detector.sample_rate,
            22050,
        )

        self.assertEqual(
            self.detector.block_size,
            4096,
        )

        self.assertEqual(
            self.detector.hop_length,
            512,
        )

        self.assertEqual(
            self.detector.confidence_threshold,
            0.35,
        )

        self.assertEqual(
            self.detector.silence_threshold,
            0.01,
        )

        self.assertEqual(
            len(self.detector.pitch_classes),
            12,
        )

        self.assertEqual(
            len(self.detector.chord_templates),
            24,
        )

        self.assertEqual(
            self.detector.current_chord,
            "None",
        )

        self.assertEqual(
            self.detector.confidence,
            0.0,
        )

    def test_create_chord_templates(self):
        """Chord templates should contain 12 major and 12 minor chords."""

        templates = self.detector._create_chord_templates()

        self.assertEqual(
            len(templates),
            24,
        )

        self.assertIn(
            "C",
            templates,
        )

        self.assertIn(
            "Cm",
            templates,
        )

        self.assertIn(
            "G#",
            templates,
        )

        self.assertIn(
            "A#m",
            templates,
        )

        c_major = templates["C"]

        self.assertEqual(c_major[0], 1.0)
        self.assertEqual(c_major[4], 1.0)
        self.assertEqual(c_major[7], 1.0)

        c_minor = templates["Cm"]

        self.assertEqual(c_minor[0], 1.0)
        self.assertEqual(c_minor[3], 1.0)
        self.assertEqual(c_minor[7], 1.0)

    def test_chord_names(self):
        """All expected major and minor chord names should exist."""

        expected_chords = [
            "C", "Cm",
            "C#", "C#m",
            "D", "Dm",
            "D#", "D#m",
            "E", "Em",
            "F", "Fm",
            "F#", "F#m",
            "G", "Gm",
            "G#", "G#m",
            "A", "Am",
            "A#", "A#m",
            "B", "Bm",
        ]

        self.assertEqual(
            sorted(self.detector.chord_names),
            sorted(expected_chords),
        )

    def test_extract_chroma_silence(self):
        """Silent audio should return None."""

        silence = np.zeros(
            4096,
            dtype=np.float32,
        )

        result = self.detector._extract_chroma(
            silence
        )

        self.assertIsNone(result)

    def test_extract_chroma_empty_input(self):
        """Empty audio should return None."""

        result = self.detector._extract_chroma(
            np.array(
                [],
                dtype=np.float32,
            )
        )

        self.assertIsNone(result)

    def test_score_chord(self):
        """C major chroma should score higher for C than Cm."""

        chroma = np.zeros(
            12,
            dtype=np.float32,
        )

        chroma[0] = 1.0
        chroma[4] = 0.8
        chroma[7] = 0.6

        c_major_score = self.detector._score_chord(
            chroma,
            self.detector.chord_templates["C"],
        )

        c_minor_score = self.detector._score_chord(
            chroma,
            self.detector.chord_templates["Cm"],
        )

        self.assertGreater(
            c_major_score,
            0.5,
        )

        self.assertGreater(
            c_major_score,
            c_minor_score,
        )

    def test_detect_chord_returns_none_for_low_confidence(
        self,
    ):
        """Low-confidence chroma should not produce a chord."""

        chroma = np.ones(
            12,
            dtype=np.float32,
        )

        chroma /= np.sum(chroma)

        chord, confidence = (
            self.detector._detect_chord(
                chroma
            )
        )

        self.assertEqual(
            chord,
            "None",
        )

        self.assertLess(
            confidence,
            self.detector.confidence_threshold,
        )

    def test_smooth_predictions_before_three_predictions(
        self,
    ):
        """Smoothing should return raw predictions initially."""

        self.detector.prediction_history.clear()

        chord, confidence = (
            self.detector._smooth_predictions(
                "C",
                0.8,
            )
        )

        self.assertEqual(
            chord,
            "C",
        )

        self.assertEqual(
            confidence,
            0.8,
        )

    def test_smooth_predictions_stable_chord(
        self,
    ):
        """Three identical predictions should stabilize the chord."""

        self.detector.prediction_history.clear()

        result = None

        for _ in range(3):
            result = self.detector._smooth_predictions(
                "C",
                0.8,
            )

        chord, confidence = result

        self.assertEqual(
            chord,
            "C",
        )

        self.assertAlmostEqual(
            confidence,
            0.8,
        )

    def test_smooth_predictions_does_not_update_state(
        self,
    ):
        """
        _smooth_predictions() returns values but does not update
        current_chord or confidence itself.
        """

        self.detector.prediction_history.clear()

        for _ in range(3):
            self.detector._smooth_predictions(
                "C",
                0.8,
            )

        self.assertEqual(
            self.detector.current_chord,
            "None",
        )

        self.assertEqual(
            self.detector.confidence,
            0.0,
        )

    def test_detect_from_file_nonexistent_raises_error(
        self,
    ):
        """A nonexistent audio file should raise FileNotFoundError."""

        with self.assertRaises(
            FileNotFoundError
        ):
            self.detector.detect_from_file(
                "non_existent_file.mp3"
            )

    def test_detect_from_file_load_error_returns_empty_lists(
        self,
    ):
        """
        If the file exists but librosa processing fails,
        detect_from_file() should return empty lists.
        """

        fake_path = Path(
            "test_song.mp3"
        )

        with patch.object(
            Path,
            "exists",
            return_value=True,
        ):
            with patch(
                "liveflowai.detection.chord_detector.librosa.load",
                side_effect=Exception(
                    "Cannot decode audio"
                ),
            ):
                with patch("builtins.print"):
                    chords, timestamps = (
                        self.detector.detect_from_file(
                            fake_path
                        )
                    )

        self.assertEqual(
            chords,
            [],
        )

        self.assertEqual(
            timestamps,
            [],
        )

    def test_get_current_chord(self):
        """get_current_chord() should return current state."""

        result = self.detector.get_current_chord()

        self.assertEqual(
            result["chord"],
            "None",
        )

        self.assertEqual(
            result["confidence"],
            0.0,
        )

    def test_get_chord_list(self):
        """get_chord_list() should return all 24 supported chords."""

        chords = self.detector.get_chord_list()

        self.assertEqual(
            len(chords),
            24,
        )

        self.assertIn(
            "C",
            chords,
        )

        self.assertIn(
            "Cm",
            chords,
        )

    def test_stop_detection(self):
        """stop_detection() should set is_running to False."""

        self.detector.is_running = True

        self.detector.stop_detection()

        self.assertFalse(
            self.detector.is_running
        )

    def test_analyze_file_delegates_to_detect_from_file(
        self,
    ):
        """analyze_file() should call detect_from_file()."""

        with patch.object(
            self.detector,
            "detect_from_file",
            return_value=(
                ["C"],
                [0.0],
            ),
        ) as mock_detect:

            result = self.detector.analyze_file(
                "song.mp3"
            )

        mock_detect.assert_called_once_with(
            "song.mp3"
        )

        self.assertEqual(
            result,
            (
                ["C"],
                [0.0],
            ),
        )


if __name__ == "__main__":
    unittest.main(
        verbosity=2
    )
