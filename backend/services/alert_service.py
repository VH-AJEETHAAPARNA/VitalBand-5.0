"""
VitalBand Rules Engine and Alert Service
"""

import sys
import time
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from backend.config import settings
from backend.models import Patient, Event, VitalsReading
from backend.websocket_manager import manager

logger = logging.getLogger("vitalband.alert_service")

# Safe import of the voice alerts module
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))
try:
    from voice.voice_alerts import speak_alert
    VOICE_ENABLED = True
except ImportError:
    VOICE_ENABLED = False
    speak_alert = None
    logger.warning("Voice alerts module not found. Spoken notifications are disabled.")

# Memory fallback for alert cooldown
_last_alert_time: Dict[Tuple[str, str, str], float] = {}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def check_cooldown(patient_id: str, event_type: str, hospital_id: str) -> bool:
    """
    Checks if an alert for this patient, event type, and hospital is allowed to fire.
    SOS button triggers ALWAYS bypass cooldown unconditionally (zero delay).
    """
    if event_type == "SOS":
        return True

    now = time.time()
    cooldown = settings.ALERT_COOLDOWN_SECONDS

    # Try Redis cooldown first
    if manager.redis_client:
        try:
            key = f"cooldown:{hospital_id}:{patient_id}:{event_type}"
            # Check if key exists
            last_val = await manager.redis_client.get(key)
            if last_val is not None:
                return False
            # Set key with TTL of cooldown
            await manager.redis_client.setex(key, cooldown, str(now))
            return True
        except Exception as e:
            logger.error(f"Redis cooldown check error: {e}. Falling back to memory cooldown.")

    # Local fallback cooldown
    key = (hospital_id, patient_id, event_type)
    last = _last_alert_time.get(key, 0.0)
    if now - last >= cooldown:
        _last_alert_time[key] = now
        return True
    return False


async def log_event(
    db: AsyncSession,
    hospital_id: str,
    patient_id: str,
    event_type: str,
    details: str,
    severity: str = "INFO"
) -> Event:
    """Creates a persistent event log in the database."""
    db_event = Event(
        hospital_id=hospital_id,
        patient_id=patient_id,
        event_type=event_type,
        details=details,
        severity=severity,
        timestamp=now_iso()
    )
    db.add(db_event)
    await db.commit()
    await db.refresh(db_event)
    return db_event


async def log_vitals_reading(
    db: AsyncSession,
    hospital_id: str,
    patient_id: str,
    heart_rate: Optional[int],
    spo2: Optional[int]
) -> VitalsReading:
    """Logs a time-series vitals entry for historical charting."""
    reading = VitalsReading(
        hospital_id=hospital_id,
        patient_id=patient_id,
        heart_rate=heart_rate,
        spo2=spo2,
        timestamp=now_iso()
    )
    db.add(reading)
    await db.commit()
    await db.refresh(reading)
    return reading


async def upsert_patient_state(
    db: AsyncSession,
    patient_id: str,
    hospital_id: str,
    **fields
) -> Patient:
    """Inserts or updates the patient state in the database."""
    stmt = select(Patient).where(
        Patient.patient_id == patient_id,
        Patient.hospital_id == hospital_id
    )
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    fields["last_updated"] = now_iso()

    if patient:
        for key, val in fields.items():
            setattr(patient, key, val)
    else:
        patient = Patient(patient_id=patient_id, hospital_id=hospital_id, **fields)
        db.add(patient)

    await db.commit()
    await db.refresh(patient)
    return patient


def evaluate_vitals(hr: Optional[int], spo2: Optional[int]) -> Tuple[bool, List[str]]:
    """Evaluates vitals against strict clinical rule thresholds."""
    abnormal = False
    reasons = []

    if hr is not None:
        if hr < settings.HR_LOW or hr > settings.HR_HIGH:
            abnormal = True
            reasons.append(f"HR {hr} out of range ({settings.HR_LOW}-{settings.HR_HIGH})")

    if spo2 is not None:
        if spo2 < settings.SPO2_LOW:
            abnormal = True
            reasons.append(f"SpO2 {spo2}% low (<{settings.SPO2_LOW}%)")

    return abnormal, reasons


async def handle_alert(
    db: AsyncSession,
    hospital_id: str,
    patient_id: str,
    event_type: str,
    detail: str,
    severity: str,
    voice_event: Optional[str] = None
):
    """
    Checks the cooldown and, if allowed, logs the event, broadcasts the alert
    over WebSockets, and plays the local multi-language audio notification.
    """
    # 1. Log all events unconditionally to database
    await log_event(db, hospital_id, patient_id, event_type, detail, severity)

    # 2. Check cooldown for WebSocket broadcast and TTS audio
    if await check_cooldown(patient_id, event_type, hospital_id):
        alert_payload = {
            "patient_id": patient_id,
            "event": event_type,
            "detail": detail,
            "severity": severity,
            "timestamp": now_iso()
        }

        # Live broadcast (WebSocket)
        await manager.broadcast_to_hospital(hospital_id, "alert", alert_payload)

        # Spoken audio notification
        if VOICE_ENABLED and speak_alert and voice_event:
            speak_alert(voice_event, patient_id=patient_id, lang=settings.VOICE_LANGUAGE)
