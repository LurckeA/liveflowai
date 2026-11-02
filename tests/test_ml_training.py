import csv
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from liveflowai.ml.train_chord_model import train_model


class TestChordModelTraining(unittest.TestCase):
    def test_training_holds_out_recording_groups_and_saves_artifact(self):
        import joblib

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            manifest_path = root / "manifest.csv"
            output_path = root / "models" / "chords.joblib"
            rows = []
            feature_by_path = {}

            for recording_number in range(4):
                recording_id = f"recording-{recording_number}"
                for chord, active_bin in (("C", 0), ("Am", 9)):
                    relative_path = Path(
                        f"segments/{recording_id}-{chord}.wav"
                    )
                    audio_path = root / relative_path
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    audio_path.touch()
                    feature = np.full(12, 0.01, dtype=np.float32)
                    feature[active_bin] = 0.89
                    feature_by_path[str(audio_path)] = feature
                    rows.append(
                        {
                            "audio_path": str(relative_path),
                            "chord": chord,
                            "recording_id": recording_id,
                        }
                    )

            with manifest_path.open("w", newline="", encoding="utf-8") as csv_file:
                writer = csv.DictWriter(
                    csv_file,
                    fieldnames=("audio_path", "chord", "recording_id"),
                )
                writer.writeheader()
                writer.writerows(rows)

            def load_audio(path, sr, mono):
                return feature_by_path[path], sr

            with (
                patch("liveflowai.ml.train_chord_model.librosa.load", side_effect=load_audio),
                patch(
                    "liveflowai.ml.train_chord_model.extract_chroma_features",
                    side_effect=lambda audio, sample_rate: audio,
                ),
            ):
                metrics = train_model(manifest_path, output_path)

            self.assertTrue(output_path.is_file())
            self.assertEqual(metrics["usable_examples"], 8)
            self.assertTrue(
                set(metrics["training_recordings"]).isdisjoint(
                    metrics["test_recordings"]
                )
            )
            artifact = joblib.load(output_path)
            self.assertEqual(artifact["sample_rate"], 22050)
            self.assertEqual(artifact["feature_version"], 1)
            self.assertEqual(set(artifact["model"].classes_), {"C", "Am"})


if __name__ == "__main__":
    unittest.main()