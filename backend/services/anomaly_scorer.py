"""
VitalBand Adaptive Anomaly Scorer (Phase 4 – MLOps)
=====================================================
Per-patient sliding-window z-score model that learns each patient's
personal HR/SpO2 baseline from their recent readings.

Design:
- Window size: last 50 readings (configurable).
- Warm-up guard: returns "NORMAL" + z_score=0.0 until >= MIN_READINGS accumulated.
- Z-score thresholds:
    |z| < 2.0  → NORMAL
    |z| < 3.0  → WARNING
    |z| >= 3.0 → CRITICAL

This is a pure in-memory service (no DB writes). It is supplementary to
the existing rule-based evaluate_vitals() and does NOT replace it.
"""

import math
import logging
from collections import deque
from typing import Dict, Optional, Tuple

logger = logging.getLogger("vitalband.anomaly_scorer")

# Thresholds
WINDOW_SIZE = 50       # Number of readings to keep per patient per metric
MIN_READINGS = 10      # Minimum readings before scoring begins
Z_WARNING = 2.0        # |z| >= this → WARNING
Z_CRITICAL = 3.0       # |z| >= this → CRITICAL


class _MetricWindow:
    """Sliding window of numeric readings with rolling mean and std."""

    def __init__(self, maxlen: int = WINDOW_SIZE):
        self._window: deque = deque(maxlen=maxlen)

    def push(self, value: float) -> None:
        self._window.append(value)

    def __len__(self) -> int:
        return len(self._window)

    def mean(self) -> float:
        return sum(self._window) / len(self._window)

    def std(self) -> float:
        n = len(self._window)
        if n < 2:
            return 0.0
        mu = self.mean()
        variance = sum((x - mu) ** 2 for x in self._window) / (n - 1)
        return math.sqrt(variance)

    def z_score(self, value: float) -> float:
        if len(self._window) < MIN_READINGS:
            return 0.0
        mu = self.mean()
        s = self.std()
        if s == 0.0:
            # Flat baseline — flag if new value deviates by >10% of mean
            if mu == 0.0:
                return 0.0
            pct_deviation = abs(value - mu) / abs(mu)
            # Map percentage deviation to a pseudo z-score: 10% → z≈2, 20% → z≈4
            return round(pct_deviation * 20.0, 3)
        return (value - mu) / s



class _PatientRecord:
    """Per-patient sliding windows for HR and SpO2."""

    def __init__(self):
        self.hr_window = _MetricWindow()
        self.spo2_window = _MetricWindow()


# Live thresholds. These start at the original hardcoded values and are
# replaced by the active trained model's calibrated values at startup and
# after every retrain. Kept mutable at module level so the retraining loop
# has one obvious place to write to.
_active_thresholds = {"z_warning": Z_WARNING, "z_critical": Z_CRITICAL}


def set_thresholds(z_warning: float, z_critical: float) -> None:
    """Apply calibrated thresholds from the active trained model."""
    _active_thresholds["z_warning"] = float(z_warning)
    _active_thresholds["z_critical"] = float(z_critical)
    logger.info(
        "Anomaly thresholds updated from trained model: warning>=%.2f critical>=%.2f",
        z_warning, z_critical,
    )


def get_thresholds() -> dict:
    return dict(_active_thresholds)


def _level_from_z(z: float) -> str:
    abs_z = abs(z)
    if abs_z >= _active_thresholds["z_critical"]:
        return "CRITICAL"
    elif abs_z >= _active_thresholds["z_warning"]:
        return "WARNING"
    return "NORMAL"


class PatientBaselineTracker:
    """
    Thread-safe (GIL-protected) singleton that tracks per-patient vitals baselines.

    Usage:
        score = tracker.score("P001", hr=78, spo2=98)
        # returns {"z_score": 0.12, "anomaly_level": "NORMAL", "warm": True}
    """

    def __init__(self):
        self._patients: Dict[str, _PatientRecord] = {}

    def _get_or_create(self, patient_id: str) -> _PatientRecord:
        if patient_id not in self._patients:
            self._patients[patient_id] = _PatientRecord()
        return self._patients[patient_id]

    def score(
        self,
        patient_id: str,
        hr: Optional[int] = None,
        spo2: Optional[int] = None
    ) -> dict:
        """
        Push a new reading and compute the composite anomaly score.

        Returns:
            {
                "z_score": float,        # max absolute z among available metrics
                "anomaly_level": str,    # "NORMAL" | "WARNING" | "CRITICAL"
                "warmed_up": bool,       # False until MIN_READINGS accumulated
                "hr_z": float,           # HR z-score (0.0 if not available)
                "spo2_z": float,         # SpO2 z-score (0.0 if not available)
            }
        """
        record = self._get_or_create(patient_id)

        hr_z = 0.0
        spo2_z = 0.0
        warmed_up = False

        if hr is not None:
            hr_z = record.hr_window.z_score(float(hr))
            record.hr_window.push(float(hr))

        if spo2 is not None:
            spo2_z = record.spo2_window.z_score(float(spo2))
            record.spo2_window.push(float(spo2))

        # Determine if we have enough data (use whichever window has data)
        hr_ready = len(record.hr_window) >= MIN_READINGS
        spo2_ready = len(record.spo2_window) >= MIN_READINGS
        warmed_up = hr_ready or spo2_ready

        # Composite z is the maximum absolute deviation across metrics
        composite_z = max(abs(hr_z), abs(spo2_z))
        level = _level_from_z(composite_z) if warmed_up else "NORMAL"

        return {
            "z_score": round(composite_z, 3),
            "anomaly_level": level,
            "warmed_up": warmed_up,
            "hr_z": round(hr_z, 3),
            "spo2_z": round(spo2_z, 3),
        }

    def reset_patient(self, patient_id: str) -> None:
        """Clear baseline data for a patient (e.g., on ward transfer)."""
        self._patients.pop(patient_id, None)

    def patient_count(self) -> int:
        return len(self._patients)


# Global singleton — import and use this directly
anomaly_scorer = PatientBaselineTracker()
