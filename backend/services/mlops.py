"""
VitalBand In-Process MLOps
==========================
Continuous retraining for the SECONDARY statistical anomaly signal.

What the "model" actually is — stated plainly, because overclaiming here is
the fastest way to lose a technical reviewer:

    It is a calibrated population baseline. From the vitals_history the system
    has actually accumulated, it fits a robust centre and spread for HR and
    SpO2 (median / MAD, so a handful of crashing patients cannot drag the
    baseline), then calibrates the z-thresholds so the WARNING flag rate lands
    near a target rate instead of being hardcoded at |z| >= 2.

    That is honest statistics fit from real stored data — not a neural network,
    and it needs no labelled dataset, which matches this project's stance that
    nothing here requires dataset collection.

SAFETY BOUNDARY (the point that matters clinically):
    Retraining tunes ONLY the secondary z-score signal. The deterministic path
    — fixed HR/SpO2 clinical limits, fall confirmation, and the SOS button —
    is untouched by anything in this file. A retrained model can raise extra
    attention; it can never stand down an alert the rules would have raised.
"""

import json
import logging
import math
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence

from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import ModelVersion, VitalsReading
from backend.services import anomaly_scorer as scorer_mod

logger = logging.getLogger("vitalband.mlops")

# Retrain automatically once this many new readings have landed.
RETRAIN_EVERY_N_READINGS = 50
# Below this, a fit would be noise dressed up as a model.
MIN_ROWS_TO_TRAIN = 30
# Fraction of readings we want the WARNING band to flag.
TARGET_WARNING_RATE = 0.10
TARGET_CRITICAL_RATE = 0.02

# Never let calibration wander outside clinically sane bounds.
Z_WARNING_FLOOR, Z_WARNING_CEIL = 1.5, 3.5
Z_CRITICAL_FLOOR, Z_CRITICAL_CEIL = 2.5, 5.0

# Fallback used before any model has been trained. Matches the original
# hardcoded scorer, so behaviour on a cold database is unchanged.
DEFAULT_PARAMS: Dict = {
    "hr_center": 78.0,
    "hr_scale": 12.0,
    "spo2_center": 97.0,
    "spo2_scale": 2.0,
    "z_warning": 2.0,
    "z_critical": 3.0,
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _median(xs: Sequence[float]) -> float:
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return 0.0
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _mad_scale(xs: Sequence[float], center: float) -> float:
    """
    Median absolute deviation, scaled to be comparable to a standard
    deviation (x1.4826 for normal data). Robust: a few extreme readings from
    genuinely deteriorating patients will not inflate the baseline and blind
    the detector, which is exactly the failure mode a plain std would have.
    """
    if not xs:
        return 1.0
    mad = _median([abs(x - center) for x in xs])
    scale = mad * 1.4826
    return scale if scale > 1e-6 else 1.0


def _quantile(xs: Sequence[float], q: float) -> float:
    if not xs:
        return 0.0
    s = sorted(xs)
    pos = (len(s) - 1) * q
    lo, hi = int(math.floor(pos)), int(math.ceil(pos))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (pos - lo)


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def fit_params(hr: List[float], spo2: List[float]) -> Dict:
    """Fit robust centres/scales and calibrate z-thresholds to target rates."""
    hr_center = _median(hr) if hr else DEFAULT_PARAMS["hr_center"]
    hr_scale = _mad_scale(hr, hr_center) if hr else DEFAULT_PARAMS["hr_scale"]
    spo2_center = _median(spo2) if spo2 else DEFAULT_PARAMS["spo2_center"]
    spo2_scale = _mad_scale(spo2, spo2_center) if spo2 else DEFAULT_PARAMS["spo2_scale"]

    # Composite |z| for every observed reading, then read the thresholds off
    # the empirical distribution so the flag rate is what we actually asked
    # for on THIS population, rather than assuming normality.
    zs: List[float] = []
    for v in hr:
        zs.append(abs(v - hr_center) / hr_scale)
    for v in spo2:
        zs.append(abs(v - spo2_center) / spo2_scale)

    clamped = False
    if zs:
        raw_warning = _quantile(zs, 1 - TARGET_WARNING_RATE)
        raw_critical = _quantile(zs, 1 - TARGET_CRITICAL_RATE)
        z_warning = _clamp(raw_warning, Z_WARNING_FLOOR, Z_WARNING_CEIL)
        z_critical = _clamp(raw_critical, Z_CRITICAL_FLOOR, Z_CRITICAL_CEIL)
        # When the data wants a threshold outside clinically sane bounds we keep
        # the bound and RECORD that we did. Silently shipping a clamped model as
        # if it were well calibrated is how an ML pipeline quietly goes wrong.
        clamped = (
            abs(raw_warning - z_warning) > 1e-6 or abs(raw_critical - z_critical) > 1e-6
        )
        if z_critical <= z_warning:
            z_critical = _clamp(z_warning + 0.75, Z_CRITICAL_FLOOR, Z_CRITICAL_CEIL)
    else:
        z_warning = DEFAULT_PARAMS["z_warning"]
        z_critical = DEFAULT_PARAMS["z_critical"]

    return {
        "hr_center": round(hr_center, 2),
        "hr_scale": round(hr_scale, 3),
        "spo2_center": round(spo2_center, 2),
        "spo2_scale": round(spo2_scale, 3),
        "z_warning": round(z_warning, 3),
        "z_critical": round(z_critical, 3),
        "calibration_clamped": clamped,
    }


def evaluate(params: Dict, hr: List[float], spo2: List[float]) -> Dict:
    """Measure what this fit would actually do to the data it was fit on."""
    zs: List[float] = []
    for v in hr:
        zs.append(abs(v - params["hr_center"]) / max(params["hr_scale"], 1e-6))
    for v in spo2:
        zs.append(abs(v - params["spo2_center"]) / max(params["spo2_scale"], 1e-6))

    n = len(zs) or 1
    warn = sum(1 for z in zs if z >= params["z_warning"])
    crit = sum(1 for z in zs if z >= params["z_critical"])

    warning_rate = warn / n
    # "Healthy" means the realised flag rate is near what we asked for. A model
    # flagging 2x its target is noisy enough that a nurse would start ignoring
    # it, which is worse than no secondary signal at all.
    within_target = warning_rate <= TARGET_WARNING_RATE * 2.0

    return {
        "samples": len(zs),
        "warning_rate": round(warning_rate, 4),
        "critical_rate": round(crit / n, 4),
        "mean_abs_z": round(sum(zs) / n, 3),
        "p95_abs_z": round(_quantile(zs, 0.95), 3),
        "target_warning_rate": TARGET_WARNING_RATE,
        "calibration_clamped": bool(params.get("calibration_clamped", False)),
        "calibration_healthy": bool(within_target and not params.get("calibration_clamped", False)),
    }


def population_drift(prev: Optional[Dict], curr: Dict) -> Dict:
    """
    How far the population moved since the last model, expressed in units of
    the PREVIOUS model's own scale. Anything past ~1.0 means the new cohort
    barely resembles what the old model was calibrated on.
    """
    if not prev:
        return {"hr_shift": 0.0, "spo2_shift": 0.0, "max_shift": 0.0, "significant": False}

    hr_shift = abs(curr["hr_center"] - prev["hr_center"]) / max(prev["hr_scale"], 1e-6)
    spo2_shift = abs(curr["spo2_center"] - prev["spo2_center"]) / max(prev["spo2_scale"], 1e-6)
    max_shift = max(hr_shift, spo2_shift)

    return {
        "hr_shift": round(hr_shift, 3),
        "spo2_shift": round(spo2_shift, 3),
        "max_shift": round(max_shift, 3),
        "significant": max_shift >= 1.0,
    }


# ── Registry access ──────────────────────────────────────────────────────────

async def get_active_model(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP") -> Optional[ModelVersion]:
    stmt = (
        select(ModelVersion)
        .where(ModelVersion.hospital_id == hospital_id, ModelVersion.status == "active")
        .order_by(desc(ModelVersion.version))
        .limit(1)
    )
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_active_params(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP") -> Dict:
    model = await get_active_model(db, hospital_id)
    if not model or not model.params_json:
        return dict(DEFAULT_PARAMS)
    try:
        return json.loads(model.params_json)
    except json.JSONDecodeError:
        logger.warning("Model v%s has unreadable params; using defaults", model.version)
        return dict(DEFAULT_PARAMS)


async def list_runs(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP", limit: int = 20) -> List[ModelVersion]:
    stmt = (
        select(ModelVersion)
        .where(ModelVersion.hospital_id == hospital_id)
        .order_by(desc(ModelVersion.version))
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def _load_training_rows(db: AsyncSession, hospital_id: str, limit: int = 2000):
    stmt = (
        select(VitalsReading)
        .where(VitalsReading.hospital_id == hospital_id)
        .order_by(desc(VitalsReading.id))
        .limit(limit)
    )
    rows = list((await db.execute(stmt)).scalars().all())
    hr = [float(r.heart_rate) for r in rows if r.heart_rate is not None]
    spo2 = [float(r.spo2) for r in rows if r.spo2 is not None]
    return rows, hr, spo2


async def train_new_version(
    db: AsyncSession,
    hospital_id: str = "DEFAULT_HOSP",
    trigger: str = "auto",
) -> Optional[ModelVersion]:
    """Fit a new model from stored history and make it the active version."""
    rows, hr, spo2 = await _load_training_rows(db, hospital_id)

    if len(rows) < MIN_ROWS_TO_TRAIN:
        logger.info("MLOps: only %d rows, need %d to train", len(rows), MIN_ROWS_TO_TRAIN)
        return None

    params = fit_params(hr, spo2)
    metrics = evaluate(params, hr, spo2)

    prev = await get_active_model(db, hospital_id)
    prev_params = None
    if prev and prev.params_json:
        try:
            prev_params = json.loads(prev.params_json)
        except json.JSONDecodeError:
            prev_params = None

    metrics["drift"] = population_drift(prev_params, params)

    next_version = (prev.version + 1) if prev else 1
    if prev:
        prev.status = "archived"

    model = ModelVersion(
        hospital_id=hospital_id,
        version=next_version,
        status="active",
        trigger=trigger,
        trained_on_rows=len(rows),
        params_json=json.dumps(params),
        metrics_json=json.dumps(metrics),
        notes=(
            f"Calibrated on {len(rows)} readings. "
            f"Warning band |z|>={params['z_warning']} "
            f"(flag rate {metrics['warning_rate']:.1%} vs {TARGET_WARNING_RATE:.0%} target)."
            + (" Threshold hit a safety bound — calibration not met." if metrics["calibration_clamped"] else "")
        ),
        created_at=now_iso(),
    )
    db.add(model)
    await db.commit()
    await db.refresh(model)

    # Put the newly calibrated thresholds into service immediately. Without
    # this the registry would be decorative — models trained but never used.
    scorer_mod.set_thresholds(params["z_warning"], params["z_critical"])

    logger.info(
        "MLOps: trained v%d on %d rows (trigger=%s, drift=%.2f)",
        next_version, len(rows), trigger, metrics["drift"]["max_shift"],
    )
    return model


async def rollback_to(db: AsyncSession, version: int, hospital_id: str = "DEFAULT_HOSP") -> Optional[ModelVersion]:
    """
    Re-activate an earlier version by copying its parameters into a NEW
    version rather than flipping the old row back to active. The registry
    stays append-only, so the audit trail always shows that a rollback
    happened and when.
    """
    stmt = select(ModelVersion).where(
        ModelVersion.hospital_id == hospital_id, ModelVersion.version == version
    )
    target = (await db.execute(stmt)).scalar_one_or_none()
    if not target:
        return None

    current = await get_active_model(db, hospital_id)
    if current and current.version == version:
        return current
    if current:
        current.status = "archived"

    next_version = (current.version + 1) if current else version + 1

    restored = ModelVersion(
        hospital_id=hospital_id,
        version=next_version,
        status="active",
        trigger="rollback",
        trained_on_rows=target.trained_on_rows,
        params_json=target.params_json,
        metrics_json=target.metrics_json,
        notes=f"Rollback: restored the parameters of v{version}.",
        created_at=now_iso(),
    )
    db.add(restored)
    await db.commit()
    await db.refresh(restored)

    try:
        restored_params = json.loads(target.params_json or "{}")
        scorer_mod.set_thresholds(
            restored_params.get("z_warning", DEFAULT_PARAMS["z_warning"]),
            restored_params.get("z_critical", DEFAULT_PARAMS["z_critical"]),
        )
    except json.JSONDecodeError:
        logger.warning("Rollback target v%s had unreadable params", version)

    logger.info("MLOps: rolled back to v%d as new v%d", version, next_version)
    return restored


# ── Auto-retrain trigger ─────────────────────────────────────────────────────

class _RetrainCounter:
    """Counts ingested readings per hospital and reports when a retrain is due."""

    def __init__(self):
        self._counts: Dict[str, int] = {}

    def record_and_check(self, hospital_id: str) -> bool:
        n = self._counts.get(hospital_id, 0) + 1
        if n >= RETRAIN_EVERY_N_READINGS:
            self._counts[hospital_id] = 0
            return True
        self._counts[hospital_id] = n
        return False

    def pending(self, hospital_id: str) -> int:
        return self._counts.get(hospital_id, 0)


retrain_counter = _RetrainCounter()


async def maybe_retrain(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP") -> Optional[ModelVersion]:
    """Called on every ingested reading. Cheap until the threshold trips."""
    if not retrain_counter.record_and_check(hospital_id):
        return None
    try:
        return await train_new_version(db, hospital_id, trigger="auto")
    except Exception as e:
        # A failed retrain must never break ingestion — the deterministic
        # alert path has to keep working no matter what the ML side does.
        logger.error("MLOps auto-retrain failed (ingestion unaffected): %s", e)
        return None


async def apply_active_thresholds(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP") -> Dict:
    """Load the active model's thresholds into the live scorer (used at startup)."""
    params = await get_active_params(db, hospital_id)
    scorer_mod.set_thresholds(params["z_warning"], params["z_critical"])
    return params
