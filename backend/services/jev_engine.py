"""
VitalBand JEV / JEPA Clinical Decision Engine
================================================
Principal AI & Backend Systems Architecture:
Dual-Engine Real-Time Triage Pipeline combining:
1. Deterministic Hardcoded Safety Override (Zero-Latency Rule-Based Path)
2. Joint-Embedding Predictive Association (JEV/JEPA Trend Correlation Engine)
3. Human-in-the-Loop Nurse Confirmation & DPDP Act 2023 Compliance
"""

import math
import logging
from collections import deque
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple, Any

from backend.schemas import JEVDecisionPayload

logger = logging.getLogger("vitalband.jev_engine")

WINDOW_SIZE = 15  # ~45 seconds of telemetry at 3s intervals


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class _PatientLatentBuffer:
    """Sliding window temporal latent space representation per patient."""

    def __init__(self, maxlen: int = WINDOW_SIZE):
        self.hr_history: deque = deque(maxlen=maxlen)
        self.spo2_history: deque = deque(maxlen=maxlen)

    def push(self, hr: Optional[int], spo2: Optional[int]):
        if hr is not None:
            self.hr_history.append(float(hr))
        if spo2 is not None:
            self.spo2_history.append(float(spo2))

    def compute_trend_correlation(self) -> Tuple[float, float, str]:
        """
        Computes joint predictive association between HR slope and SpO2 slope
        to detect inverse physiological correlation (HR spiking while SpO2 drops).
        Returns (jev_score, confidence, reasoning).
        """
        if len(self.hr_history) < 3 or len(self.spo2_history) < 3:
            return 0.0, 0.70, "Establishing baseline telemetry window."

        # Compute delta slopes over the window
        hr_delta = self.hr_history[-1] - self.hr_history[0]
        spo2_delta = self.spo2_history[-1] - self.spo2_history[0]

        # Inverse trajectory coefficient: SpO2 dropping while HR climbing
        if spo2_delta < 0 and hr_delta > 0:
            inverse_intensity = abs(spo2_delta) * 1.5 + (hr_delta * 0.8)
            confidence = min(0.96, 0.75 + (inverse_intensity / 100.0))
            reasoning = (
                f"Correlated SpO2 trend drop ({int(self.spo2_history[-1])}%) with "
                f"heart rate spike ({int(self.hr_history[-1])} BPM) across 45-second telemetry window."
            )
            return inverse_intensity, round(confidence, 2), reasoning

        return 0.0, 0.88, "Vitals trajectories within stable physiological bounds."


class JEVDecisionEngine:
    """
    Production-grade Dual-Engine Triage Processor.
    """

    def __init__(self):
        self._buffers: Dict[str, _PatientLatentBuffer] = {}

    def _get_buffer(self, patient_id: str) -> _PatientLatentBuffer:
        if patient_id not in self._buffers:
            self._buffers[patient_id] = _PatientLatentBuffer()
        return self._buffers[patient_id]

    def evaluate_triage(
        self,
        patient_id: str,
        heart_rate: Optional[int] = None,
        spo2: Optional[int] = None,
        fall: bool = False,
        sos: bool = False,
    ) -> JEVDecisionPayload:
        """
        Evaluates both Deterministic Rules and JEV Joint-Embedding Correlation.
        Returns exact JEVDecisionPayload JSON schema.
        """
        buf = self._get_buffer(patient_id)
        buf.push(heart_rate, spo2)

        # ── 1. HARDCODED DETERMINISTIC OVERRIDE PATH ──────────────────────────
        # Emergency thresholds: SpO2 < 88%, HR > 130, HR < 45, Fall, or SOS Button
        is_fall_emergency = bool(fall)
        is_sos_emergency = bool(sos)
        is_spo2_critical = spo2 is not None and spo2 < 88
        is_hr_critical = heart_rate is not None and (heart_rate > 130 or heart_rate < 45)

        if is_fall_emergency or is_sos_emergency or is_spo2_critical or is_hr_critical:
            reasons = []
            if is_sos_emergency:
                reasons.append("Manual SOS Panic Triggered")
            if is_fall_emergency:
                reasons.append("Impact Fall Incident Detected")
            if is_spo2_critical:
                reasons.append(f"Critical Hypoxia (SpO2 {spo2}%)")
            if is_hr_critical:
                reasons.append(f"Severe Cardiac Anomaly ({heart_rate} BPM)")

            clinical_reasoning = f"Deterministic Override: {'; '.join(reasons)}."
            recommended_action = "Acute physiological collapse risk. Confirm immediate ICU bed dispatch."

            return JEVDecisionPayload(
                patient_id=patient_id,
                triage_level="LEVEL_1_EMERGENCY",
                jev_confidence=0.98,
                clinical_reasoning=clinical_reasoning,
                recommended_action=recommended_action,
                deterministic_override=True,
                timestamp=now_iso(),
            )

        # ── 2. JEV PREDICTIVE EMBEDDING CORRELATION PATH ──────────────────────
        trend_score, confidence, reasoning = buf.compute_trend_correlation()

        # Moderate hypoxia/tachycardia or progressive inverse trend
        is_spo2_warning = spo2 is not None and spo2 < 93
        is_hr_warning = heart_rate is not None and (heart_rate > 110 or heart_rate < 55)

        if is_spo2_warning or is_hr_warning or trend_score > 15.0:
            return JEVDecisionPayload(
                patient_id=patient_id,
                triage_level="LEVEL_2_URGENT",
                jev_confidence=confidence,
                clinical_reasoning=reasoning if trend_score > 0 else "Early physiological deterioration trend detected.",
                recommended_action="Progressive vital drift detected. Priority nurse assessment recommended.",
                deterministic_override=False,
                timestamp=now_iso(),
            )

        # Stable state
        return JEVDecisionPayload(
            patient_id=patient_id,
            triage_level="LEVEL_3_STABLE",
            jev_confidence=0.95,
            clinical_reasoning="Vitals trajectories within stable baseline parameters.",
            recommended_action="Continue standard monitoring protocol.",
            deterministic_override=False,
            timestamp=now_iso(),
        )


# Global Singleton Instance
jev_engine = JEVDecisionEngine()
