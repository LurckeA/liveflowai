"""Shared feature extraction for chord-model training and inference."""

from typing import Optional

import librosa
import numpy as np


def extract_chroma_features(
    audio: np.ndarray,
    sample_rate: int,
) -> Optional[np.ndarray]:
    """Return a normalized 12-bin chroma vector, or None for unusable audio."""

    if len(audio) < 1024:
        return None

    audio = np.asarray(audio, dtype=np.float32)
    if float(np.sqrt(np.mean(audio ** 2))) < 1e-8:
        return None

    audio = audio - np.mean(audio)
    peak = np.max(np.abs(audio))
    if peak > 1e-8:
        audio = audio / peak

    harmonic_audio, _ = librosa.effects.hpss(audio)
    chroma = librosa.feature.chroma_stft(
        y=harmonic_audio,
        sr=sample_rate,
        n_fft=2048,
        hop_length=512,
        n_chroma=12,
    )
    features = np.mean(chroma, axis=1)
    total = float(np.sum(features))
    if total < 1e-8:
        return None

    return (features / total).astype(np.float32)