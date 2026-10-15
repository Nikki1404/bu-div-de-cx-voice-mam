import logging
import time

from fastapi import APIRouter, File, HTTPException, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from api.schemas import AgeGenderPrediction, HealthResponse
from models.age_gender_model import DEVICE, MODEL_ID, age_gender_model
from profiling.age.service import format_age_result
from profiling.audio import load_audio
from profiling.config import SAMPLE_RATE
from profiling.gender.service import format_gender_result

logger = logging.getLogger("age-gender")
router = APIRouter(prefix="/age-gender", tags=["Age & Gender"])


def make_prediction(audio_bytes: bytes, filename: str = "") -> dict:
    """Decode, run every loaded MaM head and format. Blocking: call off the event loop."""
    start = time.perf_counter()
    waveform = load_audio(audio_bytes, filename)
    model_result = age_gender_model.predict(waveform)
    gender_age = None
    if "gender_age" in model_result:
        label, confidence = max(model_result["gender_age"].items(), key=lambda item: item[1])
        gender_age = {"label": label, "confidence": round(confidence, 4)}
    return {
        "audio_duration_seconds": round(waveform.shape[0] / SAMPLE_RATE, 2),
        **format_age_result(model_result),
        **format_gender_result(model_result),
        "gender_age": gender_age,
        "processing_time_seconds": round(time.perf_counter() - start, 3),
    }


def _require_model():
    if not age_gender_model.is_ready:
        raise HTTPException(503, "MaM models are not loaded")


@router.get("/health", response_model=HealthResponse)
async def health():
    _require_model()
    return {
        "status": "healthy",
        "model": MODEL_ID,
        "device": DEVICE,
        "model_root": age_gender_model.model_root,
        "tasks_loaded": age_gender_model.loaded_tasks,
    }


@router.post("/predict", response_model=AgeGenderPrediction)
async def predict(file: UploadFile = File(...)):
    _require_model()
    try:
        result = await run_in_threadpool(make_prediction, await file.read(), file.filename or "")
        return {"status": "success", "filename": file.filename, **result}
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except Exception as exc:
        logger.exception("Prediction failed")
        raise HTTPException(500, "Prediction failed. Check server logs.") from exc


@router.websocket("/ws")
async def websocket_predict(websocket: WebSocket):
    await websocket.accept()
    await websocket.send_json({"status": "connected", "message": "Send audio as binary data."})
    try:
        while True:
            audio_bytes = await websocket.receive_bytes()
            try:
                result = await run_in_threadpool(make_prediction, audio_bytes)
                await websocket.send_json({"status": "success", **result})
            except Exception as exc:
                logger.exception("WebSocket prediction failed")
                await websocket.send_json({"status": "error", "message": str(exc)})
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
