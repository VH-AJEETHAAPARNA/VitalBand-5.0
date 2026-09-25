"""
VitalBand Deterioration Index
=============================
Turns a short window of telemetry into a single 0–100 "how fast is this
patient getting worse" number for the nurse-facing JEV drawer.

Design constraints that matter for this project:

* This is a SCORE, not a gate. It can only ever *raise* attention. The
  deterministic rule path in jev_engine.py fires independently and is never
  consulted by, or blocked by, anything in this file.
* It is transparent arithmetic, not a learned model. Every point of the score
  traces back to a named clinical contributor, so the drawer can explain
  itself and a clinician can disagree with a specific term.
* Recent frames dominate via exponential decay: a patient who was bad 90s ago
  but is recovering should not score the same as one crashing right now.
"""

import math
from typing import Dict, List, Optional, Sequence

# Exponential decay applied by frame age (0 = newest).
# 0.35 gives the newest frame ~33x the weight of one 10 frames back. Tuned
# deliberately steep: at 0.12 the window was so flat that a patient at
# HR 142 / SpO2 84 scored only 56/100, because their own healthy readings
# from 45s earlier dragged the average down. The index must describe the
# patient's state NOW, not the average of the last minute.
DECAY_LAMBDA = 0.35

# Clinically comfortable mid-points and the deviation that counts as "full scale".
HR_COMFORT_LOW, HR_COMFORT_HIGH = 60, 100
HR_FULL_SCALE_DEV = 45.0     # 45 BPM outside the comfort band ⇒ that term maxes out
SPO2_COMFORT = 96
SPO2_FULL_SCALE_DEV = 12.0   # 12 points below 96 ⇒ that term maxes out

# Term weights (sum = 1.0).
W_HR_LEVEL = 0.26
W_SPO2_LEVEL = 0.34
W_INVERSE_TREND = 0.28       # HR climbing while SpO2 falls — the compensation signature
W_MOTION = 0.12

ESCALATION_THRESHOLD = 75.0


def _decay_weights(n: int) -> List[float]:
    """Newest-first exponential weights, normalised to sum to 1."""
    if n <= 0:
        return []
    raw = [math.exp(-DECAY_LAMBDA * age) for age in range(n)]
    total = sum(raw)
    return [w / total for w in raw]


def _weighted_recent(series: Sequence[float]) -> float:
    """Decay-weighted average with the LAST element treated as newest."""
    vals = [v for v in series if v is not None]
    if not vals:
        return 0.0
    newest_first = list(reversed(vals))
    weights = _decay_weights(len(newest_first))
    return sum(v * w for v, w in zip(newest_first, weights))


def _slope(series: Sequence[float]) -> float:
    """Least-squares slope per frame. Positive = rising."""
    vals = [v for v in series if v is not None]
    n = len(vals)
    if n < 3:
        return 0.0
    mean_x = (n - 1) / 2.0
    mean_y = sum(vals) / n
    num = sum((i - mean_x) * (v - mean_y) for i, v in enumerate(vals))
    den = sum((i - mean_x) ** 2 for i in range(n))
    return num / den if den else 0.0


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def compute_deterioration_index(
    heart_rate: Sequence[Optional[float]],
    spo2: Sequence[Optional[float]],
    motion: Optional[Sequence[Optional[float]]] = None,
) -> Dict:
    """
    Returns the index plus the per-term breakdown that produced it, so the UI
    can show *why* rather than just a number.
    """
    hr = [float(v) for v in heart_rate if v is not None]
    sp = [float(v) for v in spo2 if v is not None]
    mo = [float(v) for v in (motion or []) if v is not None]

    frames = max(len(hr), len(sp))
    if frames < 2:
        return {
            "deterioration_index": 0.0,
            "confidence_score": 0.35,
            "warmed_up": False,
            "frames_analysed": frames,
            "contributors": [],
            "escalate": False,
        }

    contributors: List[Dict] = []

    # ── Term 1: how far the recent HR sits outside the comfort band ──────────
    hr_recent = _weighted_recent(hr) if hr else 0.0
    if hr_recent > HR_COMFORT_HIGH:
        hr_dev = hr_recent - HR_COMFORT_HIGH
    elif hr_recent and hr_recent < HR_COMFORT_LOW:
        hr_dev = HR_COMFORT_LOW - hr_recent
    else:
        hr_dev = 0.0
    hr_term = _clamp01(hr_dev / HR_FULL_SCALE_DEV)
    if hr_term > 0.01:
        contributors.append({
            "factor": "Heart rate deviation",
            "value": f"{hr_recent:.0f} BPM",
            "weighted_points": round(hr_term * W_HR_LEVEL * 100, 1),
        })

    # ── Term 2: sustained hypoxia ───────────────────────────────────────────
    spo2_recent = _weighted_recent(sp) if sp else 0.0
    spo2_dev = max(0.0, SPO2_COMFORT - spo2_recent) if sp else 0.0
    spo2_term = _clamp01(spo2_dev / SPO2_FULL_SCALE_DEV)
    if spo2_term > 0.01:
        contributors.append({
            "factor": "Oxygen saturation deficit",
            "value": f"{spo2_recent:.0f}%",
            "weighted_points": round(spo2_term * W_SPO2_LEVEL * 100, 1),
        })

    # ── Term 3: the inverse trend — HR climbing while SpO2 falls ────────────
    # This is the physiological compensation signature: the heart working
    # harder to move less oxygen. Either trend alone is far less alarming.
    hr_slope = _slope(hr)
    spo2_slope = _slope(sp)
    trend_term = 0.0
    if hr_slope > 0 and spo2_slope < 0:
        # Normalise: 1.5 BPM/frame rise and 0.6 %/frame fall ⇒ full scale.
        trend_term = _clamp01((hr_slope / 1.5) * 0.5 + (abs(spo2_slope) / 0.6) * 0.5)
        contributors.append({
            "factor": "Inverse HR/SpO₂ trajectory",
            "value": f"HR {hr_slope:+.2f}/frame, SpO₂ {spo2_slope:+.2f}/frame",
            "weighted_points": round(trend_term * W_INVERSE_TREND * 100, 1),
        })

    # ── Term 4: motion. Both extremes are informative ───────────────────────
    # Near-zero variation after a drop = unresponsive; very high = agitation.
    motion_term = 0.0
    if len(mo) >= 3:
        # Judge motion on the RECENT tail, not the whole window. A patient
        # progressively going still (0.9 -> 0.004) has high whole-window
        # variance, so a naive variance check scores them as calm — exactly
        # backwards for the most dangerous pattern there is.
        tail = mo[-5:]
        t_mean = sum(tail) / len(tail)
        t_var = sum((v - t_mean) ** 2 for v in tail) / len(tail)

        label = ""
        if t_mean < 0.05 and t_var < 0.02:
            motion_term = 0.9
            label = "Near-zero movement (possible unresponsiveness)"
        elif t_var > 4.0:
            motion_term = 0.6
            label = "Erratic movement (agitation / distress)"

        if label:
            contributors.append({
                "factor": label,
                "value": f"recent mean {t_mean:.3f}, variance {t_var:.3f}",
                "weighted_points": round(motion_term * W_MOTION * 100, 1),
            })

    index = 100.0 * (
        hr_term * W_HR_LEVEL
        + spo2_term * W_SPO2_LEVEL
        + trend_term * W_INVERSE_TREND
        + motion_term * W_MOTION
    )
    index = round(max(0.0, min(100.0, index)), 1)

    # Confidence tracks how much telemetry backs the number, not how bad it is.
    warmed_up = frames >= 10
    confidence = 0.55 + min(0.40, frames * 0.015)
    if not mo:
        confidence -= 0.05  # no motion channel = one term blind
    confidence = round(max(0.35, min(0.97, confidence)), 2)

    contributors.sort(key=lambda c: c["weighted_points"], reverse=True)

    return {
        "deterioration_index": index,
        "confidence_score": confidence,
        "warmed_up": warmed_up,
        "frames_analysed": frames,
        "contributors": contributors,
        "escalate": index > ESCALATION_THRESHOLD,
    }


def build_recommendation(result: Dict, patient_id: str) -> Dict:
    """Structured, human-readable recommendation derived from the index."""
    idx = result["deterioration_index"]
    contributors = result.get("contributors", [])
    top = contributors[0]["factor"] if contributors else "no single dominant factor"

    if idx > ESCALATION_THRESHOLD:
        severity = "CRITICAL"
        action = "Escalate now — assign ICU bed and dispatch the rapid response team."
    elif idx > 50:
        severity = "HIGH"
        action = "Priority bedside assessment within 5 minutes; recheck vitals manually."
    elif idx > 25:
        severity = "MODERATE"
        action = "Increase observation frequency; keep the patient in direct line of sight."
    else:
        severity = "LOW"
        action = "Continue standard monitoring protocol."

    detail = "; ".join(
        f"{c['factor']} ({c['value']}) contributing {c['weighted_points']} pts"
        for c in contributors[:3]
    ) or "All monitored terms within baseline."

    return {
        "patient_id": patient_id,
        "severity": severity,
        "clinical_rationale": (
            f"Deterioration Index {idx}/100 over {result['frames_analysed']} telemetry frames, "
            f"led by {top}. {detail}."
        ),
        "recommended_action": action,
        "confidence_score": result["confidence_score"],
    }
