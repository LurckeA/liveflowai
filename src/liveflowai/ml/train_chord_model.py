"""Train and evaluate the optional scikit-learn chord classifier."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any

import librosa
import numpy as np

from liveflowai.audio.chord_features import extract_chroma_features


FEATURE_VERSION = 1


def train_model(
    manifest_path: Path,
    output_path: Path,
    sample_rate: int = 22050,
    test_size: float = 0.25,
    random_state: int = 42,
) -> dict[str, Any]:
    """Train on manifest rows and evaluate on held-out recording groups."""

    manifest_path = manifest_path.expanduser().resolve()
    output_path = output_path.expanduser()
    if not 0 < test_size < 1:
        raise ValueError("test_size must be between 0 and 1.")

    try:
        import joblib
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            f1_score,
        )
        from sklearn.model_selection import GroupShuffleSplit
    except ImportError as error:
        raise RuntimeError(
            "Model training requires the 'ml' extra. "
            "Install it with: uv sync --extra ml"
        ) from error

    with manifest_path.open(newline="", encoding="utf-8") as manifest_file:
        reader = csv.DictReader(manifest_file)
        required_columns = {"audio_path", "chord", "recording_id"}
        if not required_columns.issubset(reader.fieldnames or []):
            raise ValueError(
                "Manifest must include audio_path, chord, and recording_id columns."
            )
        rows = list(reader)

    features: list[np.ndarray] = []
    labels: list[str] = []
    groups: list[str] = []
    for row_number, row in enumerate(rows, start=2):
        audio_path = Path(row["audio_path"]).expanduser()
        if not audio_path.is_absolute():
            audio_path = manifest_path.parent / audio_path
        label = row["chord"].strip()
        recording_id = row["recording_id"].strip()
        if not label or not recording_id:
            raise ValueError(
                f"Manifest row {row_number} needs a chord label and recording_id."
            )
        if not audio_path.is_file():
            raise FileNotFoundError(
                f"Audio file from manifest row {row_number} not found: {audio_path}"
            )

        audio, _ = librosa.load(str(audio_path), sr=sample_rate, mono=True)
        vector = extract_chroma_features(audio, sample_rate)
        if vector is None:
            continue
        features.append(vector)
        labels.append(label)
        groups.append(recording_id)

    if len(set(groups)) < 2:
        raise ValueError("At least two distinct recording_id groups are required.")
    if len(set(labels)) < 2:
        raise ValueError("At least two chord classes with usable audio are required.")

    feature_matrix = np.vstack(features)
    label_array = np.asarray(labels)
    group_array = np.asarray(groups)
    splitter = GroupShuffleSplit(
        n_splits=1,
        test_size=test_size,
        random_state=random_state,
    )
    train_indices, test_indices = next(
        splitter.split(feature_matrix, label_array, group_array)
    )
    train_labels = label_array[train_indices]
    if len(np.unique(train_labels)) < 2:
        raise ValueError(
            "The grouped split left fewer than two classes in training. "
            "Add more recording groups per chord or adjust --test-size."
        )

    model = RandomForestClassifier(
        n_estimators=300,
        class_weight="balanced_subsample",
        random_state=random_state,
        n_jobs=-1,
    )
    model.fit(feature_matrix[train_indices], train_labels)
    predictions = model.predict(feature_matrix[test_indices])
    classes = model.classes_.tolist()
    metrics = {
        "accuracy": float(accuracy_score(label_array[test_indices], predictions)),
        "macro_f1": float(
            f1_score(
                label_array[test_indices],
                predictions,
                labels=classes,
                average="macro",
                zero_division=0,
            )
        ),
        "classification_report": classification_report(
            label_array[test_indices],
            predictions,
            labels=classes,
            output_dict=True,
            zero_division=0,
        ),
        "confusion_matrix": confusion_matrix(
            label_array[test_indices], predictions, labels=classes
        ).tolist(),
        "classes": classes,
        "usable_examples": len(labels),
        "training_examples": int(len(train_indices)),
        "test_examples": int(len(test_indices)),
        "training_recordings": sorted(set(group_array[train_indices].tolist())),
        "test_recordings": sorted(set(group_array[test_indices].tolist())),
        "sample_rate": sample_rate,
        "feature_version": FEATURE_VERSION,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(
        {
            "model": model,
            "sample_rate": sample_rate,
            "feature_version": FEATURE_VERSION,
            "metrics": metrics,
        },
        output_path,
    )
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train and evaluate a chord classifier from labeled audio segments."
    )
    parser.add_argument("--manifest", required=True, type=Path)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/models/chord_classifier.joblib"),
    )
    parser.add_argument("--sample-rate", type=int, default=22050)
    parser.add_argument("--test-size", type=float, default=0.25)
    parser.add_argument("--random-state", type=int, default=42)
    args = parser.parse_args()

    metrics = train_model(
        args.manifest,
        args.output,
        sample_rate=args.sample_rate,
        test_size=args.test_size,
        random_state=args.random_state,
    )
    print(json.dumps(metrics, indent=2))
    print(f"Saved model artifact: {args.output}")