"""Waveform -> 64x64 RGB spectrogram image, exactly as MaM was trained.

The training pipeline (Age-Gender-Classification) renders the dB spectrogram
through matplotlib's default colormap to a PNG, then reloads it with Keras at
64x64. The weights learned that rendered image, so it is reproduced step by
step here. The Figure API replaces pyplot's global state so concurrent requests
cannot draw into each other's figure.
"""
import io

import librosa
import numpy as np
from keras.utils import img_to_array, load_img
from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure

from profiling.config import HOP_LENGTH, N_FFT, SPECTROGRAM_SIZE


def scale_minmax(x: np.ndarray, min_v: float = 0.0, max_v: float = 255.0) -> np.ndarray:
    x_min, x_max = float(x.min()), float(x.max())
    if x_max - x_min < 1e-12:
        return np.zeros_like(x, dtype=np.float32)
    return (x - x_min) / (x_max - x_min) * (max_v - min_v) + min_v


def _render_png(image: np.ndarray) -> io.BytesIO:
    fig = Figure()
    FigureCanvasAgg(fig)
    ax = fig.add_subplot()
    ax.axis("off")
    ax.imshow(image, aspect="auto", origin="lower", interpolation="none")
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    fig.tight_layout()
    buffer = io.BytesIO()
    fig.savefig(buffer, format="png", bbox_inches="tight", pad_inches=0)
    buffer.seek(0)
    return buffer


def waveform_to_spectrogram(waveform: np.ndarray) -> np.ndarray:
    """Mono 16 kHz waveform -> float32 array (64, 64, 3) scaled to [0, 1]."""
    spec = librosa.stft(waveform, n_fft=N_FFT, hop_length=HOP_LENGTH)
    spec_db = librosa.amplitude_to_db(np.abs(spec))
    image = scale_minmax(spec_db).astype(np.uint8)
    size = (SPECTROGRAM_SIZE, SPECTROGRAM_SIZE)
    return img_to_array(load_img(_render_png(image), target_size=size)) / 255.0
