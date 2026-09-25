"""
VitalBand Ingestion Routes (Device Ingestion Layer)
"""

from datetime import datetime, timezone
from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.schemas import SensorPayload, SensorResponse, SOSPayload, CameraEventPayload, RFIDPayload, JEVDecisionPayload
from backend.services.alert_service import (
    evaluate_vitals,
    handle_alert,
    upsert_patient_state,
    log_event,
    log_vitals_reading,
    now_iso
)
from backend.services.anomaly_scorer import anomaly_scorer
from backend.services.jev_engine import jev_engine
from backend.services import mlops
from backend.services import records as rec
from backend.websocket_manager import manager

router = APIRouter(tags=["Ingestion"])


@router.post("/sensor", status_code=status.HTTP_200_OK, response_model=SensorResponse)
async def receive_sensor(payload: SensorPayload, db: AsyncSession = Depends(get_db)):
    """
    Ingest wrist patch sensor data. Runs clinical rules, adaptive ML scoring, and JEV Decision Engine.
    """
    patient_id = payload.patient_id or "UNKNOWN"
    hospital_id = payload.hospital_id or "DEFAULT_HOSP"
    hr = payload.heart_rate
    spo2 = payload.spo2
    fall_flag = bool(payload.fall)

    # 1. Clinical rule threshold check
    abnormal, reasons = evaluate_vitals(hr, spo2)

    # 2. Adaptive ML z-score anomaly scoring
    ml_score = anomaly_scorer.score(patient_id, hr=hr, spo2=spo2)

    # 3. JEV Decision Engine (Deterministic Override + Trend Correlation)
    jev_triage = jev_engine.evaluate_triage(
        patient_id=patient_id,
        heart_rate=hr,
        spo2=spo2,
        fall=fall_flag,
        sos=bool(payload.sos)
    )

    # Escalate to WARNING/CRITICAL if ML scorer or JEV detects drift
    if not abnormal and (ml_score["anomaly_level"] in ("WARNING", "CRITICAL") or jev_triage.triage_level != "LEVEL_3_STABLE"):
        abnormal = True
        reasons.append(
            f"JEV Triage: {jev_triage.triage_level} ({jev_triage.clinical_reasoning})"
        )

    # 4. Update database patient state & record historical time-series
    await upsert_patient_state(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        device_id=payload.device_id,
        heart_rate=hr,
        spo2=spo2,
        fall_status="FALL DETECTED" if fall_flag else "NORMAL",
        wrist_connected=1
    )
    await log_vitals_reading(
        db,
        hospital_id=hospital_id,
        patient_id=patient_id,
        heart_rate=hr,
        spo2=spo2
    )

    # 4b. MLOps: once enough new readings have accumulated, refit the
    # population baseline. Wrapped so a training failure can never take down
    # ingestion or the deterministic alert path.
    await mlops.maybe_retrain(db, hospital_id)

    # 5. WebSocket Realtime Updates (vitals_update & jev_triage)
    vitals_payload = {
        "patient_id": patient_id,
        "heart_rate": hr,
        "spo2": spo2,
        "fall": fall_flag,
        "abnormal": abnormal,
        "reasons": reasons,
        "z_score": ml_score["z_score"],
        "anomaly_level": ml_score["anomaly_level"],
        "jev_triage": jev_triage.model_dump(),
        "timestamp": now_iso()
    }
    await manager.broadcast_to_hospital(hospital_id, "vitals_update", vitals_payload)

    # 6. Trigger Alerts if abnormal or fall detected
    if abnormal or fall_flag:
        severity = "CRITICAL" if fall_flag else "WARNING"
        detail = "Fall detected" if fall_flag else "; ".join(reasons)
        event_type = "FALL" if fall_flag else "ABNORMAL_VITALS"

        await handle_alert(
            db=db,
            hospital_id=hospital_id,
            patient_id=patient_id,
            event_type=event_type,
            detail=detail,
            severity=severity,
            voice_event=event_type
        )

    return SensorResponse(
        status="ok",
        abnormal=abnormal,
        reasons=reasons,
        z_score=ml_score["z_score"],
        anomaly_level=ml_score["anomaly_level"],
        warmed_up=ml_score["warmed_up"],
        jev_triage=jev_triage
    )



@router.post("/sos", status_code=status.HTTP_200_OK)
async def receive_sos(payload: SOSPayload, db: AsyncSession = Depends(get_db)):
    """
    Ingest SOS trigger from Scan Machine button. Unconditional, immediate critical alert.
    """
    patient_id = payload.patient_id or "UNKNOWN"
    hospital_id = payload.hospital_id or "DEFAULT_HOSP"

    # 1. Update patient state
    await upsert_patient_state(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        sos_status="SOS TRIGGERED",
        scan_connected=1
    )

    # 2. Trigger SOS Alert
    await handle_alert(
        db=db,
        hospital_id=hospital_id,
        patient_id=patient_id,
        event_type="SOS",
        detail="Patient pressed SOS button",
        severity="CRITICAL",
        voice_event="SOS"
    )

    return {"status": "ok"}


@router.post("/fall", status_code=status.HTTP_200_OK)
async def receive_fall_or_distress(payload: CameraEventPayload, db: AsyncSession = Depends(get_db)):
    """
    Ingest camera events (fall or facial distress) from CV pipeline.
    """
    patient_id = payload.patient_id or "UNKNOWN"
    hospital_id = payload.hospital_id or "DEFAULT_HOSP"
    fall_detected = bool(payload.fall_detected)
    distress_detected = bool(payload.distress_detected)
    confidence = payload.confidence

    # 1. Update patient state
    fields = {"scan_connected": 1}
    if fall_detected:
        fields["fall_status"] = "FALL DETECTED"
    if distress_detected:
        fields["distress_status"] = "DISTRESS DETECTED"

    await upsert_patient_state(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        **fields
    )

    # 2. Trigger alerts
    if fall_detected or distress_detected:
        event_name = "FALL (camera)" if fall_detected else "DISTRESS (camera)"
        voice_event = "FALL" if fall_detected else "DISTRESS"
        detail = f"{event_name} - confidence {confidence}" if confidence else event_name

        await handle_alert(
            db=db,
            hospital_id=hospital_id,
            patient_id=patient_id,
            event_type=event_name,
            detail=detail,
            severity="CRITICAL",
            voice_event=voice_event
        )

    return {"status": "ok"}


@router.post("/rfid", status_code=status.HTTP_200_OK)
async def receive_rfid(payload: RFIDPayload, db: AsyncSession = Depends(get_db)):
    """
    Ingest Scan Machine RFID scans.
    """
    hospital_id = payload.hospital_id or "DEFAULT_HOSP"
    rfid_uid = payload.rfid_uid

    # 1. Resolve the tag to a real identity.
    # The scan machine physically only knows the UID it just read — it has no
    # idea who that is. This lookup is the check-in step that turns an
    # anonymous camera detection into a named patient with a clinical record.
    # If the firmware did send a patient_id we trust it; otherwise we resolve,
    # and if the tag is unknown we keep it UNKNOWN rather than guessing.
    patient_id = payload.patient_id or "UNKNOWN"
    resolved = await rec.resolve_rfid(db, rfid_uid, hospital_id)

    if patient_id in ("", "UNKNOWN", None):
        patient_id = resolved or "UNKNOWN"

    identified = patient_id != "UNKNOWN"

    # 2. Update patient state
    await upsert_patient_state(
        db,
        patient_id=patient_id,
        hospital_id=hospital_id,
        rfid_uid=rfid_uid,
        scan_connected=1
    )

    # 3. Log event
    await log_event(
        db=db,
        hospital_id=hospital_id,
        patient_id=patient_id,
        event_type="RFID_SCAN",
        details=(
            f"RFID {rfid_uid} scanned - identified as {patient_id}"
            if identified else
            f"RFID {rfid_uid} scanned - tag not assigned to any patient"
        ),
        severity="INFO" if identified else "WARNING"
    )

    # 4. Broadcast rfid_scan WebSocket update
    rfid_payload = {
        "patient_id": patient_id,
        "rfid_uid": rfid_uid,
        "identified": identified,
        "timestamp": now_iso()
    }
    await manager.broadcast_to_hospital(hospital_id, "rfid_scan", rfid_payload)

    return {"status": "ok", "patient_id": patient_id, "identified": identified}
