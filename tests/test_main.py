import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

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
from liveflowai.detection.chord_detector import LiveChordDetector, _sounddevice
from liveflowai.detection.song_predictor import SongPredictor
from liveflowai.main import (
    analyze_audio_file,
    analyze_audio_files,
    cli_main,
    main,
    show_audio_files,
    start_performance,
)
from liveflowai.ui import ConsoleUI


class TestConsoleUI(unittest.TestCase):
    def setUp(self):
        self.ui = ConsoleUI()
        self.ui._enabled = False

    def test_format_duration_handles_minutes_and_negative_values(self):
        self.assertEqual(self.ui.format_duration(0), "0:00")
        self.assertEqual(self.ui.format_duration(65.2), "1:05")
        self.assertEqual(self.ui.format_duration(-10), "0:00")

    @patch("builtins.print")
    def test_table_renders_generator_rows(self, mock_print):
        self.ui.table(("SONG", "BPM"), (("demo.mp3", "128") for _ in range(1)))

        rendered_lines = [call.args[0] for call in mock_print.call_args_list]
        self.assertIn("SONG      BPM", rendered_lines)
        self.assertIn("demo.mp3  128", rendered_lines)

    @patch("builtins.input", return_value="  2  ")
    def test_prompt_strips_input(self, mock_input):
        self.assertEqual(self.ui.prompt("Choose:"), "2")
        mock_input.assert_called_once_with("Choose: ")


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
        cli_main()

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

    @patch("liveflowai.main.start_performance")
    @patch("liveflowai.main.show_audio_files")
    @patch("liveflowai.main.analyze_audio_files")
    @patch("liveflowai.main.IEMManager")
    @patch("liveflowai.main.SongPredictor")
    @patch("liveflowai.main.DatabaseLogic")
    @patch("liveflowai.main.AudioFileSelector")
    @patch("liveflowai.main.LiveChordDetector")
    @patch("liveflowai.main.ChordAnalyzer")
    @patch("liveflowai.main.TempoAnalyzer")
    @patch("builtins.input", side_effect=["1", "2", "3", "4"])
    def test_main_routes_each_dashboard_action(
        self,
        _mock_input,
        _mock_tempo,
        _mock_chord_analyzer,
        _mock_detector,
        _mock_selector,
        mock_database,
        _mock_predictor,
        _mock_iem,
        mock_analyze,
        mock_show,
        mock_performance,
    ):
        cli_main()

        mock_analyze.assert_called_once()
        mock_show.assert_called_once_with(mock_database.return_value)
        mock_performance.assert_called_once()

    @patch("liveflowai.gui.launch_app")
    def test_main_launches_desktop_application(self, mock_launch_app):
        main()

        mock_launch_app.assert_called_once_with()


class TestGuiLauncher(unittest.TestCase):
    @patch("liveflowai.gui.LiveFlowApp")
    @patch("liveflowai.gui.Tk")
    def test_launch_app_builds_and_runs_tk_application(self, mock_tk, mock_app):
        from liveflowai.gui import launch_app

        launch_app()

        mock_app.assert_called_once_with(mock_tk.return_value)
        mock_tk.return_value.mainloop.assert_called_once_with()


class TestMainWorkflows(unittest.TestCase):
    @patch("liveflowai.main.ConsoleUI")
    def test_analyze_audio_file_stores_and_announces_results(self, mock_ui):
        file_path = Path("set-one.mp3")
        analyzer = MagicMock()
        analyzer.detect_tempo.return_value = {
            "tempo_bpm": 128.0,
            "duration": 245.0,
            "num_beats": 521,
        }
        analyzer.get_beat_confidence.return_value = {"confidence_score": 0.91}
        chord = MagicMock(timestamp=1.0, duration=2.0, confidence=0.8)
        chord.__str__.return_value = "Am"
        chord_analyzer = MagicMock()
        chord_analyzer.analyze_chords.return_value = [chord]
        database = MagicMock()
        iem_manager = MagicMock()

        success = analyze_audio_file(
            file_path, analyzer, chord_analyzer, database, iem_manager
        )

        self.assertTrue(success)
        analyzer.visualize_tempo.assert_called_once_with(file_path)
        database.PushDB.assert_called_once_with("set-one.mp3", 245.0, 128.0, "Am")
        iem_manager.announce_next_song.assert_called_once()
        mock_ui.return_value.table.assert_called()

    @patch("liveflowai.main.ConsoleUI")
    def test_analyze_audio_files_returns_without_selection(self, mock_ui):
        selector = MagicMock()
        selector.select_multiple.return_value = []

        analyze_audio_files(selector, MagicMock(), MagicMock(), MagicMock(), MagicMock())

        mock_ui.return_value.status.assert_called_with("No audio files selected.", "warning")

    @patch("liveflowai.main.ConsoleUI")
    def test_show_audio_files_displays_a_library_table(self, mock_ui):
        mock_ui.return_value.format_duration.return_value = "4:05"
        database = MagicMock()
        database.FetchAllDB.return_value = [
            ("set-one.mp3", 245.0, 128.0, "Am, F", "2026-01-01"),
        ]
        database.FetchFirstFiveChords.return_value = ["Am", "F"]

        show_audio_files(database)

        headers, rows = mock_ui.return_value.table.call_args.args
        self.assertEqual(headers, ("#", "SONG", "BPM", "LENGTH", "OPENING CHORDS"))
        self.assertEqual(rows, [("1", "set-one.mp3", "128", "4:05", "Am, F")])

    @patch("liveflowai.main.ConsoleUI")
    def test_start_performance_always_stops_the_metronome(self, _mock_ui):
        predictor = MagicMock()
        manager = MagicMock()

        start_performance(predictor, manager)

        predictor.run_performance.assert_called_once_with()
        manager.stop_metronome.assert_called_once_with()


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

    @patch.dict(sys.modules, {"sounddevice": MagicMock()})
    def test_sounddevice_is_loaded_only_when_requested(self):
        backend = _sounddevice()

        self.assertTrue(hasattr(backend, "InputStream"))

    @patch("builtins.__import__", side_effect=ImportError("backend missing"))
    def test_sounddevice_reports_a_clear_optional_dependency_error(self, _mock_import):
        with self.assertRaisesRegex(RuntimeError, "optional sounddevice backend"):
            _sounddevice()


class TestSongPredictor(unittest.TestCase):
    def test_stop_performance_sets_a_stop_request(self):
        predictor = SongPredictor(MagicMock(), MagicMock())

        predictor.stop_performance()

        self.assertTrue(predictor._stop_requested.is_set())


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
