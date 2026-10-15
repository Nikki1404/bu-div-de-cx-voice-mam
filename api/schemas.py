from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str
    model: str
    device: str
    model_root: str
    tasks_loaded: list[str]


class GenderProbabilities(BaseModel):
    female: float
    male: float


class GenderAgePrediction(BaseModel):
    label: str
    confidence: float


class AgeGenderPrediction(BaseModel):
    status: str
    filename: str | None = None
    audio_duration_seconds: float
    age_group: str
    age_bucket: str
    age_confidence: float
    age_probabilities: dict[str, float]
    gender: str
    gender_confidence: float
    gender_probabilities: GenderProbabilities
    gender_age: GenderAgePrediction | None = None
    processing_time_seconds: float
