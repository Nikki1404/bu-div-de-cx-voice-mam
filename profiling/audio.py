import io

import librosa
import numpy as np
import soundfile as sf

from biometrics.engine import decode_audio
from profiling.config import (
    MAX_AUDIO_SECONDS,
    MIN_AUDIO_SECONDS,
    MIN_RMS,
    SAMPLE_RATE,
    WINDOW_SAMPLES,
)


def load_audio(audio_bytes: bytes, filename: str = "") -> np.ndarray:
    """Upload bytes -> float32 mono waveform at SAMPLE_RATE. Raises ValueError."""
    if not audio_bytes:
        raise ValueError("Empty audio file.")
    try:
        waveform, sample_rate = sf.read(io.BytesIO(audio_bytes), dtype="float32", always_2d=True)
        waveform = waveform.mean(axis=1)
    except Exception as exc:
        # Browser recordings (webm/opus), mp3 and m4a go through ffmpeg.
        try:
            waveform, sample_rate = decode_audio(audio_bytes, filename)
        except Exception as fallback_exc:
            raise ValueError(f"Unable to decode audio: {fallback_exc}") from exc
    if waveform.size == 0:
        raise ValueError("Decoded audio is empty.")
    if sample_rate != SAMPLE_RATE:
        waveform = librosa.resample(waveform, orig_sr=sample_rate, target_sr=SAMPLE_RATE)
    waveform = np.ascontiguousarray(waveform, dtype=np.float32)
    duration = waveform.shape[0] / SAMPLE_RATE
    if duration < MIN_AUDIO_SECONDS:
        raise ValueError(f"Audio must be at least {MIN_AUDIO_SECONDS} seconds.")
    return waveform[:SAMPLE_RATE * MAX_AUDIO_SECONDS]


def rms(waveform: np.ndarray) -> float:
    return float(np.sqrt(np.mean(waveform ** 2))) if waveform.size else 0.0


def create_audio_windows(waveform: np.ndarray) -> list[np.ndarray]:
    windows = []
    for start in range(0, waveform.shape[0], WINDOW_SAMPLES):
        chunk = waveform[start:start + WINDOW_SAMPLES]
        if chunk.shape[0] / SAMPLE_RATE >= MIN_AUDIO_SECONDS and rms(chunk) >= MIN_RMS:
            windows.append(chunk)
    if not windows:
        if rms(waveform) < MIN_RMS:
            raise ValueError("Audio contains insufficient speech/audio energy.")
        windows.append(waveform)
    return windows
