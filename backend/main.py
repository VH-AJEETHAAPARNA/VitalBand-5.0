"""
VitalBand Production FastAPI Entrypoint
"""

import logging
import asyncio
import time
from typing import Optional
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Depends, WebSocket, WebSocketDisconnect, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.database import get_db, init_db_models, AsyncSessionLocal
from backend.models import Hospital, User
from backend.auth import get_password_hash
from backend.websocket_manager import manager

# Routers
from backend.routers import auth_router, ingestion, patients, alerts, jev, voice, mlops, records, ai

# Logger configuration
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vitalband.main")

BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


async def seed_database():
    """Seeds the database with a default hospital and nurse user if not present."""
    async with AsyncSessionLocal() as db:
        # Check/create default hospital
        stmt = select(Hospital).where(Hospital.id == "DEFAULT_HOSP")
        result = await db.execute(stmt)
        default_hospital = result.scalar_one_or_none()

        if not default_hospital:
            default_hospital = Hospital(
                id="DEFAULT_HOSP",
                name="Government General Hospital",
                code="GGH01"
            )
            db.add(default_hospital)
            logger.info("Database Seeding: Default hospital created.")

        # Check/create the default staff accounts.
        # NOTE: the Login page + IntroSplashScreen both offer an "Admin Console"
        # preset, so the admin account must exist or that button 401s.
        DEFAULT_USERS = [
            ("nurse@vitalband.com", "Nurse Catherine", "nurse"),
            ("admin@vitalband.com", "Dr. Arun Prakash", "admin"),
        ]

        for email, full_name, role in DEFAULT_USERS:
            stmt = select(User).where(User.email == email)
            result = await db.execute(stmt)
            if result.scalar_one_or_none():
                continue

            db.add(User(
                email=email,
                hashed_password=get_password_hash("password"),
                full_name=full_name,
                role=role,
                hospital_id="DEFAULT_HOSP"
            ))
            logger.info(f"Database Seeding: {role} user created ({email} / password).")

        await db.commit()

        # Synthetic clinical records for the identified-patient view.
        from backend.services.records import seed_demo_records
        await seed_demo_records(db)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Init database tables and seed
    logger.info("Starting up VitalBand API. Creating schemas...")
    await init_db_models()
    await seed_database()

    # Restore the active trained model's calibrated thresholds, so a restart
    # does not silently revert the scorer to its factory defaults.
    try:
        from backend.services import mlops
        async with AsyncSessionLocal() as db:
            await mlops.apply_active_thresholds(db)
    except Exception as e:
        logger.warning("Could not restore trained thresholds, using defaults: %s", e)

    # Probe the camera in the background so the dashboard has an answer ready
    # without any request ever waiting on device enumeration.
    _ensure_probe_running()

    # Start Realtime sync manager (Redis Pub/Sub)
    await manager.start()
    yield
    # Shutdown
    logger.info("Shutting down VitalBand API...")
    await manager.stop()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files if directory exists
static_path = BASE_DIR / "static"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Mount API Routers
app.include_router(auth_router.router, prefix=settings.API_PREFIX)
app.include_router(ingestion.router, prefix=settings.API_PREFIX)
app.include_router(patients.router, prefix=settings.API_PREFIX)
app.include_router(alerts.router, prefix=settings.API_PREFIX)
# Versioned analytics surface — the JEV drawer talks to /api/v1.
app.include_router(jev.router, prefix=f"{settings.API_PREFIX}/v1")
# Pre-rendered multilingual alert audio (no OS voice pack required).
app.include_router(voice.router, prefix=settings.API_PREFIX)
# Continuous retraining registry for the secondary anomaly signal.
app.include_router(mlops.router, prefix=settings.API_PREFIX)
# Clinical records + RFID identity resolution.
app.include_router(records.router, prefix=settings.API_PREFIX)
# NVIDIA NIM / guardrails status + guardrailed explanations.
app.include_router(ai.router, prefix=settings.API_PREFIX)


@app.get("/", response_class=HTMLResponse)
async def get_dashboard(request: Request):
    """Serve the nurse dashboard page."""
    return templates.TemplateResponse(request=request, name="index.html")


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, hospital_id: str = "DEFAULT_HOSP"):
    """
    WebSocket endpoint for live dashboard updates.
    Scoped by hospital_id to support multi-tenancy.
    """
    await manager.connect(websocket, hospital_id)
    try:
        while True:
            # We only expect heartbeat or client-sent tokens if needed
            # Keep connection alive by reading message stream
            _ = await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket, hospital_id)
    except Exception as e:
        logger.error(f"WebSocket error for hospital {hospital_id}: {e}")
        manager.disconnect(websocket, hospital_id)


# ── MJPEG Video Feed for Scan Camera ──────────────────────────────────────────
# Shared camera state so multiple browser tabs don't fight over the device
_camera_lock = asyncio.Lock()
_active_camera = None  # will hold cv2.VideoCapture once opened

# When no camera is present, remember that for a while instead of re-probing.
# Why this matters: with no camera the MJPEG stream ends after one placeholder
# frame, so the dashboard's <img> retries — and every retry used to re-run the
# full native probe (3 device indices x 3 capture backends). That repeated
# native device enumeration is capable of taking the whole backend process
# down, which is exactly what happened during testing. A cooldown turns a
# probe storm into one probe per COOLDOWN window.
# A C270 needs about 1.1s before it stops returning black frames; 4s gives
# slower USB hubs headroom without stalling the probe on a dead device.
WARMUP_BUDGET_SECONDS = 4.0

_CAMERA_PROBE_COOLDOWN_SECONDS = 2.0
_camera_absent_until = 0.0

# Cached probe verdict: None = never probed, True/False = last known.
_camera_known: Optional[bool] = None
_camera_probe_task: Optional[asyncio.Task] = None


async def _refresh_camera_state(force: bool = False) -> None:
    global _camera_known
    cam = await _get_camera(force=force)
    _camera_known = cam is not None


def _ensure_probe_running(force: bool = False) -> None:
    """Kick off a probe if one is not already in flight."""
    global _camera_probe_task
    if _camera_probe_task is not None and not _camera_probe_task.done():
        return
    _camera_probe_task = asyncio.create_task(_refresh_camera_state(force))


def _open_camera():
    """Try to open a working camera (built-in webcam or USB camera). Returns cv2.VideoCapture or None."""
    import cv2
    # Try backends: DirectShow (CAP_DSHOW) first for fast Windows enumeration, then default CAP_ANY
    for api in (cv2.CAP_DSHOW, cv2.CAP_ANY):
        for idx in (0, 1, 2):
            try:
                cap = cv2.VideoCapture(idx, api)
                if not cap.isOpened():
                    continue

                warmup_deadline = time.monotonic() + WARMUP_BUDGET_SECONDS
                got_image = False

                while time.monotonic() < warmup_deadline:
                    ok, test_frame = cap.read()
                    if ok and test_frame is not None and test_frame.size > 0:
                        got_image = True
                        break
                    time.sleep(0.05)

                if got_image:
                    logger.info(
                        "Camera opened on index %s with backend %s after warm-up", idx, api
                    )
                    return cap

                logger.debug(
                    "Camera idx %s backend %s opened but produced no frame",
                    idx, api,
                )
                cap.release()
            except Exception as e:
                logger.debug(f"Camera open attempt failed on idx {idx}: {e}")

    logger.warning("No active camera producing valid video frames found.")
    return None


def _safe_open_camera():
    """_open_camera, but never raises into the event loop."""
    try:
        return _open_camera()
    except BaseException as e:  # noqa: BLE001 - native failures are not always Exception
        logger.error("Camera probe raised, treating as no camera: %s", e)
        return None


async def _get_camera(force: bool = False):
    """
    Lazily open the camera (thread-safe), with a negative-result cooldown.

    Pass force=True to bypass the cooldown, e.g. after the user has plugged a
    camera in and wants the panel to pick it up without waiting.
    """
    global _active_camera, _camera_absent_until

    async with _camera_lock:
        if _active_camera is not None and _active_camera.isOpened():
            return _active_camera

        now = time.monotonic()
        if not force and now < _camera_absent_until:
            # We probed recently and found nothing; do not touch the hardware.
            return None

        _active_camera = await asyncio.to_thread(_safe_open_camera)
        if _active_camera is None:
            _camera_absent_until = now + _CAMERA_PROBE_COOLDOWN_SECONDS
            logger.info(
                "No camera found; suppressing further probes for %.0fs",
                _CAMERA_PROBE_COOLDOWN_SECONDS,
            )
        else:
            _camera_absent_until = 0.0

    return _active_camera


async def _mjpeg_generator():
    """Yields MJPEG frames with MediaPipe Pose keypoints and fall detection."""
    import cv2
    from backend.services.vision_stream import generate_mediapipe_mjpeg_stream

    cam = await _get_camera(force=True)
    if cam is None:
        blank = __import__("numpy").zeros((480, 640, 3), dtype="uint8")
        cv2.putText(blank, "No Camera Detected", (120, 240),
                    cv2.FONT_HERSHEY_SIMPLEX, 1.2, (255, 255, 255), 2)
        _, buf = cv2.imencode(".jpg", blank, [cv2.IMWRITE_JPEG_QUALITY, 80])
        yield (b"--frame\r\n"
               b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
        return

    async def _on_fall_trigger(patient_id: str, event_type: str):
        """Async callback when MediaPipe confirms a fall on video stream."""
        logger.info(f"MediaPipe confirmed fall for {patient_id} via vision stream!")
        try:
            async with AsyncSessionLocal() as db:
                from backend.services.alert_service import handle_alert, upsert_patient_state
                await upsert_patient_state(db, patient_id=patient_id, hospital_id="DEFAULT_HOSP", fall_status="FALL DETECTED")
                await handle_alert(
                    db=db,
                    hospital_id="DEFAULT_HOSP",
                    patient_id=patient_id,
                    event_type="FALL (camera)",
                    detail="MediaPipe visual fall confirmed (33-point posture collapsed)",
                    severity="CRITICAL",
                    voice_event="FALL"
                )
        except Exception as e:
            logger.error(f"Failed to process MediaPipe fall alert: {e}")

    async for frame_bytes in generate_mediapipe_mjpeg_stream(cam, _on_fall_trigger):
        yield frame_bytes


@app.get("/video_status")
async def video_status(recheck: bool = False):
    """
    Whether a camera is producing frames. Answers immediately from cache.

    The dashboard needs this because the MJPEG fallback frame ("No Camera
    Detected") is a VALID image: the browser loads it successfully, so an
    <img> onError handler never fires and the UI would happily claim it is
    scanning while showing a placeholder.

    This never blocks: probing absent devices takes tens of seconds, so the
    first call reports checking=true and a background task fills in the answer.
    """
    if recheck:
        _ensure_probe_running(force=True)
        return {"available": _camera_known is True, "checking": True,
                "message": "Re-checking for a camera…"}

    if _camera_known is None:
        _ensure_probe_running()
        return {"available": False, "checking": True,
                "message": "Checking for a camera…"}

    if _camera_known:
        return {"available": True, "checking": False,
                "message": "Scan Machine camera streaming."}

    return {"available": False, "checking": False,
            "message": "No USB camera detected. Connect the Scan Machine camera, then retry."}


@app.get("/video_feed")
async def video_feed():
    """MJPEG video stream for the Scan Camera panel in the Dashboard."""
    return StreamingResponse(
        _mjpeg_generator(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)
