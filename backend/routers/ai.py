"""
VitalBand AI stack routes (/api/ai/...)
=======================================
GET  /api/ai/status    what is actually live right now, stated honestly
POST /api/ai/explain   guardrailed Nemotron explanation of a triage verdict
"""

import logging
from typing import Dict, List, Optional

from fastapi import APIRouter
from pydantic import BaseModel, Field

from backend.services import nvidia_nim, guardrails
from backend.services.jev_engine import jev_engine

logger = logging.getLogger("vitalband.ai_router")

router = APIRouter(tags=["AI"])


class ExplainRequest(BaseModel):
    patient_id: str = "UNKNOWN"
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    fall: bool = False
    sos: bool = False
    deterioration_index: Optional[float] = None
    contributors: List[Dict] = Field(default_factory=list)


class ExplainResponse(BaseModel):
    patient_id: str
    triage_level: str
    deterministic_override: bool
    explanation: str
    source: str                      # nemotron | deterministic
    guardrail_passed: bool
    guardrail_violations: List[str] = []


@router.get("/ai/status")
async def ai_status():
    """
    Deliberately reports what is NOT running as well as what is.

    Triton/TensorRT-LLM and self-hosted NIM need a local NVIDIA GPU. Claiming
    them on a machine without one is the kind of thing that unravels under a
    single question, so the API says so plainly and the UI repeats it.
    """
    import shutil

    has_gpu = shutil.which("nvidia-smi") is not None

    return {
        "deterministic_engine": {
            "service": "Deterministic clinical rules + JEV index",
            "configured": True,
            "mode": "active",
            "role": "decides every triage level and every alert",
            "detail": "Pure Python. No GPU, no network, no model. Always available.",
        },
        "nim": nvidia_nim.status(),
        "guardrails": guardrails.status(),
        "riva": {
            "service": "NVIDIA Riva TTS",
            "configured": False,
            "mode": "fallback",
            "role": "multilingual spoken alerts",
            "detail": (
                "Riva needs a GPU server. Voice currently runs on pre-rendered "
                "gTTS audio cached on disk — works offline, no GPU required."
            ),
        },
        "triton": {
            "service": "NVIDIA Triton + TensorRT-LLM",
            "configured": False,
            "mode": "unavailable",
            "role": "sub-10ms edge inference",
            "detail": (
                "Requires a local NVIDIA GPU; none present on this host. "
                "MediaPipe pose runs on CPU instead."
            ),
        },
        "host_has_nvidia_gpu": has_gpu,
        "safety_note": (
            "No model in this stack can raise, lower or suppress an alert. "
            "Language models only describe decisions the rule engine already made."
        ),
    }


@router.post("/ai/explain", response_model=ExplainResponse)
async def ai_explain(payload: ExplainRequest):
    """
    Explain a triage verdict in nurse-facing language.

    Order matters: the verdict is computed FIRST by the deterministic engine,
    then handed to the LLM to describe. The LLM is never consulted about what
    the verdict should be.
    """
    verdict = jev_engine.evaluate_triage(
        patient_id=payload.patient_id,
        heart_rate=payload.heart_rate,
        spo2=payload.spo2,
        fall=payload.fall,
        sos=payload.sos,
    )

    fallback = f"{verdict.clinical_reasoning} {verdict.recommended_action}".strip()

    ctx = {
        "patient_id": payload.patient_id,
        "triage_level": verdict.triage_level,
        "deterministic_override": verdict.deterministic_override,
        "heart_rate": payload.heart_rate,
        "spo2": payload.spo2,
        "fall": payload.fall,
        "sos": payload.sos,
        "deterioration_index": payload.deterioration_index,
        "contributors": payload.contributors,
        "rule_reason": verdict.clinical_reasoning,
    }

    raw = await nvidia_nim.explain_triage(ctx)
    allowed, safe, violations = guardrails.validate_explanation(
        raw, verdict.triage_level, ctx
    )

    return ExplainResponse(
        patient_id=payload.patient_id,
        triage_level=verdict.triage_level,
        deterministic_override=verdict.deterministic_override,
        explanation=safe if allowed else fallback,
        source="nemotron" if allowed else "deterministic",
        guardrail_passed=allowed,
        guardrail_violations=violations,
    )
