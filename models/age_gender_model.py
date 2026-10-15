"""MaM (Multi-Attention Module CNN) age/gender classifiers.

Weights come from the Age-Gender-Classification repo and are not bundled in the
image: MODEL_ROOT holds either the training layout (age/best_model_age.h5, ...) or
the author's pretrained files (age_classification_acc_81.h5, gender_classification_acc_96.h5,
gender_age_classification_acc_80.h5). Age and gender each use their own
head when loaded; otherwise they are derived from the joint gender_age head.
"""
import glob
import logging
import os
import threading

os.environ.setdefault("TF_CPP_MIN_LOG_LEVEL", "3")

import numpy as np
from keras.models import load_model

from profiling.age.service import age_from_gender_age
from profiling.audio import create_audio_windows
from profiling.config import (
    AGE_LABELS,
    GENDER_AGE_LABELS,
    LOAD_TASKS,
    MAM_GENDER_LABELS,
    MODEL_ROOT,
)
from profiling.gender.service import gender_from_gender_age
from profiling.spectrogram import waveform_to_spectrogram

MODEL_ID = "mam-cnn"
DEVICE = "cpu"
TASK_LABELS = {"age": AGE_LABELS, "gender": MAM_GENDER_LABELS, "gender_age": GENDER_AGE_LABELS}

logger = logging.getLogger("age-gender")


class MamAgeGenderModel:
    def __init__(self, model_root: str = MODEL_ROOT, tasks: list[str] = LOAD_TASKS):
        self.model_root = model_root
        self.tasks = [t for t in tasks if t in TASK_LABELS]
        self.models = {}
        self._lock = threading.Lock()

    @property
    def loaded_tasks(self) -> list[str]:
        return sorted(self.models)

    @property
    def is_ready(self) -> bool:
        return "gender_age" in self.models or {"age", "gender"} <= self.models.keys()

    def model_path(self, task: str) -> str | None:
        """Training-repo layout (<task>/best_model_<task>.h5) first, then the names the
        author's pretrained download uses (<task>_classification_acc_NN.h5)."""
        candidates = [os.path.join(self.model_root, task, f"best_model_{task}.h5")]
        candidates += sorted(glob.glob(os.path.join(self.model_root, f"{task}_classification*.h5")))
        return next((p for p in candidates if os.path.isfile(p) and os.path.getsize(p) > 0), None)

    def load(self):
        if self.models:
            return
        for task in self.tasks:
            path = self.model_path(task)
            if path is None:
                logger.warning("Skipping missing MaM model task=%s root=%s", task, self.model_root)
                continue
            logger.info("Loading MaM model task=%s path=%s", task, path)
            self.models[task] = load_model(path, compile=False)
        if not self.is_ready:
            raise RuntimeError(
                f"MaM models in {self.model_root} cannot predict both age and gender "
                f"(loaded: {self.loaded_tasks or 'none'}). Provide gender_age, or both age "
                f"and gender, as <task>/best_model_<task>.h5 or <task>_classification*.h5.")
        logger.info("Loaded MaM tasks: %s", ", ".join(self.loaded_tasks))

    def unload(self):
        self.models.clear()

    def predict(self, waveform: np.ndarray) -> dict:
        """Score each window, average class probabilities, return per-task label->prob."""
        batch = np.stack([waveform_to_spectrogram(w) for w in create_audio_windows(waveform)])
        with self._lock:
            raw = {
                task: model(batch, training=False).numpy().mean(axis=0)
                for task, model in self.models.items()
            }
        result = {task: dict(zip(TASK_LABELS[task], map(float, probs))) for task, probs in raw.items()}
        if "age" not in result:
            result["age"] = age_from_gender_age(result["gender_age"])
        if "gender" not in result:
            result["gender"] = gender_from_gender_age(result["gender_age"])
        return result


age_gender_model = MamAgeGenderModel()
