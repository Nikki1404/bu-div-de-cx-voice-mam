import os

SAMPLE_RATE = 16000
WINDOW_SECONDS = 5
WINDOW_SAMPLES = SAMPLE_RATE * WINDOW_SECONDS
MIN_AUDIO_SECONDS = 3
MAX_AUDIO_SECONDS = 30
MIN_RMS = 0.005

# Spectrogram settings used to train MaM (Age-Gender-Classification/src/model_utils.py).
# Changing them silently degrades accuracy: the weights only know this input.
N_FFT = 256
HOP_LENGTH = 128
SPECTROGRAM_SIZE = 64

# Directory holding age/, gender/, gender_age/ with best_model_<task>.h5 inside.
MODEL_ROOT = os.getenv("MODEL_ROOT", "/models")
# Comma-separated subset of age,gender,gender_age to load at startup.
LOAD_TASKS = [t.strip() for t in os.getenv("LOAD_TASKS", "age,gender,gender_age").split(",") if t.strip()]

# Label order is fixed by the training label encoders in the MaM repo (data_utils.py).
AGE_LABELS = ["teens", "twenties", "thirties", "fourties", "fifties", "sixties"]
MAM_GENDER_LABELS = ["male", "female"]
GENDER_AGE_LABELS = [f"{gender}-{age}" for gender in ("female", "male") for age in AGE_LABELS]
SEX_LABELS = ["Female", "Male"]
