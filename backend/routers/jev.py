"""
VitalBand JEV Triage Route (/api/v1/jev-triage)
===============================================
Scores a telemetry window into a 0-100 Deterioration Index for the
nurse-facing co-pilot drawer.

The deterministic rule verdict is computed alongside and returned unchanged.
The index never suppresses it — a stable-looking index with an SOS or a
breached clinical threshold still comes back as LEVEL_1_EMERGENCY.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, status

from backend.schemas import JEVTriageRequest, JEVTriageResponse
from backend.services.deterioration import compute_deterioration_index, build_recommendation
from backend.services.jev_engine import jev_engine

router = APIRouter(tags=["JEV Triage"])


@router.post("/jev-triage", status_code=status.HTTP_200_OK, response_model=JEVTriageResponse)
async def jev_triage(payload: JEVTriageRequest):
    # Cap at the most recent 30 frames, as specified.
    hr = payload.heart_rate[-30:]
    spo2 = payload.spo2[-30:]
    motion = payload.motion[-30:]

    result = compute_deterioration_index(hr, spo2, motion)
    recommendation = build_recommendation(result, payload.patient_id)

    latest_hr = next((v for v in reversed(hr) if v is not None), None)
    latest_spo2 = next((v for v in reversed(spo2) if v is not None), None)

    deterministic = jev_engine.evaluate_triage(
        patient_id=payload.patient_id,
        heart_rate=latest_hr,
        spo2=latest_spo2,
        fall=payload.fall,
        sos=payload.sos,
    )

    return JEVTriageResponse(
        patient_id=payload.patient_id,
        deterioration_index=result["deterioration_index"],
        confidence_score=result["confidence_score"],
        warmed_up=result["warmed_up"],
        frames_analysed=result["frames_analysed"],
        contributors=result["contributors"],
        escalate=result["escalate"],
        severity=recommendation["severity"],
        clinical_rationale=recommendation["clinical_rationale"],
        recommended_action=recommendation["recommended_action"],
        deterministic_triage=deterministic,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
