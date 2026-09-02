import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import librosa.beat
import librosa.feature
import librosa.onset


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))


from liveflowai.audio.audio_file_selector import AudioFileSelector
from liveflowai.audio.tempo_analyzer import TempoAnalyzer, round_half_up
from liveflowai.detection.chord_detector import LiveChordDetector
from liveflowai.main import main


class TestMain(unittest.TestCase):
    @patch("liveflowai.main.IEMManager")
    @patch("liveflowai.main.SongPredictor")
    @patch("liveflowai.main.DatabaseLogic")
    @patch("liveflowai.main.AudioFileSelector")
    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.ChordAnalyzer")
    @patch("liveflowai.main.TempoAnalyzer")
    @patch("builtins.input", return_value="4")
    def test_main_initializes_components_and_exits(
        self,
        _mock_input,
        mock_tempo_analyzer,
        mock_chord_analyzer,
        mock_chord_detector,
        mock_audio_selector,
        mock_database,
        mock_song_predictor,
        mock_iem_manager,
    ):
        main()

        mock_tempo_analyzer.assert_called_once_with(sample_rate=22050)
        mock_chord_analyzer.assert_called_once_with(sample_rate=22050)
        mock_chord_detector.assert_called_once_with(sample_rate=22050)
        mock_audio_selector.assert_called_once()
        mock_database.return_value.MakeDB.assert_called_once_with()
        mock_iem_manager.return_value.shutdown.assert_called_once_with()
        mock_song_predictor.assert_called_once_with(
            chord_detector=mock_chord_detector.return_value,
            db=mock_database.return_value,
            recording_duration=15.0,
            segment_duration=1.0,
            iem_manager=mock_iem_manager.return_value,
        )


class TestTempoAnalyzer(unittest.TestCase):
    def test_initialization(self):
        analyzer = TempoAnalyzer(sample_rate=16000)

        self.assertEqual(analyzer.sample_rate, 16000)
        self.assertIsNone(analyzer.tempo)
        self.assertIsNone(analyzer.beats)
        self.assertIsNone(analyzer.beat_times)

    def test_round_half_up(self):
        self.assertEqual(round_half_up(128.5), 129)
        self.assertEqual(round_half_up(128.4), 128)
        self.assertEqual(round_half_up(128.45, 1), 128.5)

    @patch("liveflowai.audio.tempo_analyzer.librosa.load")
    def test_load_audio_wraps_errors(self, mock_load):
        mock_load.side_effect = FileNotFoundError("missing")
        analyzer = TempoAnalyzer()

        with self.assertRaisesRegex(ValueError, "Failed to load audio"):
            analyzer.load_audio("missing.mp3")

    @patch.object(TempoAnalyzer, "load_audio")
    @patch("liveflowai.audio.tempo_analyzer.librosa.beat.beat_track")
    @patch("liveflowai.audio.tempo_analyzer.librosa.onset.onset_strength")
    @patch("liveflowai.audio.tempo_analyzer.librosa.feature.tempo")
    @patch("liveflowai.audio.tempo_analyzer.librosa.frames_to_time")
    @patch("liveflowai.audio.tempo_analyzer.librosa.get_duration")
    def test_detect_tempo_stores_results(
        self,
        mock_duration,
        mock_frames_to_time,
        mock_feature_tempo,
        mock_onset_strength,
        mock_beat_track,
        mock_load_audio,
    ):
        analyzer = TempoAnalyzer()
        beats = np.array([10, 20])
        beat_times = np.array([0.5, 1.0])
        audio = np.array([0.1, 0.2], dtype=np.float32)

        mock_load_audio.return_value = audio, 22050
        mock_beat_track.return_value = np.array([128.5]), beats
        mock_onset_strength.return_value = np.array([1.0, 2.0])
        mock_feature_tempo.return_value = np.array([127.5])
        mock_frames_to_time.return_value = beat_times
        mock_duration.return_value = 2.0

        result = analyzer.detect_tempo("song.mp3")

        self.assertEqual(result["tempo_bpm"], 129)
        self.assertEqual(result["tempo_onset"], 128)
        self.assertEqual(result["num_beats"], 2)
        self.assertEqual(result["duration"], 2.0)
        np.testing.assert_array_equal(analyzer.beats, beats)
        np.testing.assert_array_equal(analyzer.beat_times, beat_times)


class TestLiveChordDetector(unittest.TestCase):
    def setUp(self):
        with patch("builtins.print"):
            self.detector = LiveChordDetector(sample_rate=22050)

    def test_initialization(self):
        self.assertEqual(self.detector.sample_rate, 22050)
        self.assertEqual(self.detector.block_size, 2048)
        self.assertEqual(self.detector.analysis_duration, 1.0)
        self.assertEqual(self.detector.silence_threshold, 0.01)
        self.assertEqual(self.detector.minimum_confidence, 0.45)
        self.assertIsNone(self.detector.current_chord)
        self.assertEqual(self.detector.current_confidence, 0.0)

    def test_extract_chroma_rejects_silence_and_short_audio(self):
        self.assertIsNone(
            self.detector._extract_chroma(np.zeros(4096, dtype=np.float32))
        )
        self.assertIsNone(
            self.detector._extract_chroma(np.zeros(1000, dtype=np.float32))
        )

    def test_detect_chord_rejects_missing_chroma(self):
        chord, confidence = self.detector._detect_chord(None)

        self.assertIsNone(chord)
        self.assertEqual(confidence, 0.0)

    def test_smooth_prediction_requires_consistent_history(self):
        first = self.detector._smooth_prediction("C", 0.8)
        second = self.detector._smooth_prediction("G", 0.7)
        stable = self.detector._smooth_prediction("C", 0.9)

        self.assertEqual(first, ("C", 0.8))
        self.assertEqual(second, ("C", 0.8))
        self.assertEqual(stable[0], "C")
        self.assertAlmostEqual(stable[1], 0.85)

    def test_stop_detection_clears_running_state(self):
        self.detector.is_running = True

        with patch("builtins.print"):
            self.detector.stop_detection()

        self.assertFalse(self.detector.is_running)


class TestAudioFileSelector(unittest.TestCase):
    def test_get_audio_files_filters_and_sorts_supported_files(self):
        with tempfile.TemporaryDirectory() as directory:
            songs_directory = Path(directory) / "data" / "songs"
            songs_directory.mkdir(parents=True)
            (songs_directory / "zeta.WAV").touch()
            (songs_directory / "Alpha.mp3").touch()
            (songs_directory / "notes.txt").touch()

            selector = AudioFileSelector(directory)

            self.assertEqual(
                [path.name for path in selector.get_audio_files()],
                ["Alpha.mp3", "zeta.WAV"],
            )

    def test_get_audio_files_returns_empty_when_directory_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            selector = AudioFileSelector(directory)

            with patch("builtins.print"):
                files = selector.get_audio_files()

            self.assertEqual(files, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
