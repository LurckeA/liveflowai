# src/liveflowai/audio/tempo_analyzer.py

import math

import librosa
import librosa.display
import numpy as np
import matplotlib.pyplot as plt

from typing import Tuple, Dict, Any


def round_half_up(value: float, decimals: int = 0) -> float:
    """
    Round a value using "round half up" semantics instead of
    Python's default banker's rounding (round half to even).

    Example:
        round_half_up(128.5) -> 129
        round_half_up(128.4) -> 128
        round_half_up(128.45, 1) -> 128.5
    """
    factor = 10 ** decimals
    return math.floor(value * factor + 0.5) / factor


class TempoAnalyzer:
    """Tempo analysis class for music files."""

    def __init__(self, sample_rate: int = 22050):
        self.sample_rate = sample_rate
        self.tempo = None
        self.beats = None
        self.beat_times = None

    def load_audio(self, file_path: str) -> Tuple[np.ndarray, int]:
        """Load audio file with resampling."""
        try:
            y, sr = librosa.load(
                file_path,
                sr=self.sample_rate
            )
            return y, sr

        except Exception as e:
            raise ValueError(
                f"Failed to load audio: {e}"
            ) from e

    def detect_tempo(self, file_path: str) -> Dict[str, Any]:
        """Detect tempo from an audio file."""

        y, sr = self.load_audio(file_path)

        # Beat tracking
        tempo, beats = librosa.beat.beat_track(
            y=y,
            sr=sr
        )

        # Convert possible ndarray to scalar
        tempo = float(np.asarray(tempo).squeeze())

        # Round the tempo up when the first decimal digit is >= 5
        # (e.g. 128.5 -> 129, 128.4 -> 128), instead of relying on
        # Python's default round-half-to-even behavior.
        tempo = round_half_up(tempo)

        # Onset strength
        onset_env = librosa.onset.onset_strength(
            y=y,
            sr=sr
        )

        # Alternative tempo estimation
        tempo_onset = librosa.feature.tempo(
            onset_envelope=onset_env,
            sr=sr
        )

        tempo_onset = float(
            np.asarray(tempo_onset).squeeze()
        )

        tempo_onset = round_half_up(tempo_onset)

        # Beat timestamps
        beat_times = librosa.frames_to_time(
            beats,
            sr=sr
        )

        # Store results
        self.tempo = tempo
        self.beats = beats
        self.beat_times = beat_times

        return {
            "tempo_bpm": tempo,
            "tempo_onset": tempo_onset,
            "num_beats": len(beats),
            "duration": float(
                librosa.get_duration(y=y, sr=sr)
            ),
        }

    def get_beat_confidence(
        self,
        file_path: str
    ) -> Dict[str, float]:
        """Calculate simple confidence metrics."""

        y, sr = self.load_audio(file_path)

        onset_env = librosa.onset.onset_strength(
            y=y,
            sr=sr
        )

        _, beats = librosa.beat.beat_track(
            y=y,
            sr=sr
        )

        if len(beats) == 0 or len(onset_env) == 0:
            return {
                "avg_beat_strength": 0.0,
                "beat_strength_std": 0.0,
                "confidence_score": 0.0,
            }

        beat_positions = librosa.frames_to_time(
            beats,
            sr=sr
        )

        beat_frames = librosa.time_to_frames(
            beat_positions,
            sr=sr
        )

        beat_frames = np.clip(
            beat_frames,
            0,
            len(onset_env) - 1
        )

        beat_strength = onset_env[beat_frames]

        max_strength = np.max(onset_env)

        confidence_score = (
            float(np.mean(beat_strength) / max_strength)
            if max_strength > 0
            else 0.0
        )

        return {
            "avg_beat_strength": float(
                np.mean(beat_strength)
            ),
            "beat_strength_std": float(
                np.std(beat_strength)
            ),
            "confidence_score": confidence_score,
        }

    def visualize_tempo(self, file_path: str):
        """Visualize tempo and detected beats."""

        y, sr = self.load_audio(file_path)

        tempo, beats = librosa.beat.beat_track(
            y=y,
            sr=sr
        )

        tempo = float(np.asarray(tempo).squeeze())
        tempo = round_half_up(tempo)

        beat_times = librosa.frames_to_time(
            beats,
            sr=sr
        )

        fig, (ax1, ax2) = plt.subplots(
            2,
            1,
            figsize=(12, 8)
        )

        # Waveform
        librosa.display.waveshow(
            y,
            sr=sr,
            ax=ax1
        )

        ax1.vlines(
            beat_times,
            -1,
            1,
            alpha=0.5,
            label="Beats"
        )

        ax1.set_title(
            f"Waveform with Beat Detection "
            f"(Tempo: {tempo:.1f} BPM)"
        )

        ax1.legend()

        # Onset strength
        onset_env = librosa.onset.onset_strength(
            y=y,
            sr=sr
        )

        times = librosa.times_like(
            onset_env,
            sr=sr
        )

        ax2.plot(
            times,
            onset_env,
            label="Onset Strength"
        )

        if len(onset_env) > 0:
            ax2.vlines(
                beat_times,
                0,
                np.max(onset_env),
                alpha=0.5,
                label="Beats"
            )

        ax2.set_xlabel("Time (s)")
        ax2.set_ylabel("Strength")
        ax2.set_title("Onset Strength Curve")
        ax2.legend()

        plt.tight_layout()
        plt.show()

        return fig
