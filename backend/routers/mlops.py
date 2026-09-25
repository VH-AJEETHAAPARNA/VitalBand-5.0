"""
VitalBand MLOps Routes (/api/mlops/...)
=======================================
Inspect, trigger and roll back the continuously-retrained anomaly baseline.
"""

import json
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.models import ModelVersion
from backend.services import mlops

logger = logging.getLogger("vitalband.mlops_router")

router = APIRouter(tags=["MLOps"])


class ModelRunResponse(BaseModel):
    version: int
    status: str
    trigger: str
    trained_on_rows: int
    created_at: str
    notes: Optional[str] = None
    params: dict = {}
    metrics: dict = {}


def _to_response(m: ModelVersion) -> ModelRunResponse:
    def _load(raw: Optional[str]) -> dict:
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    return ModelRunResponse(
        version=m.version,
        status=m.status,
        trigger=m.trigger,
        trained_on_rows=m.trained_on_rows,
        created_at=m.created_at,
        notes=m.notes,
        params=_load(m.params_json),
        metrics=_load(m.metrics_json),
    )


@router.get("/mlops/status")
async def mlops_status(hospital_id: str = "DEFAULT_HOSP", db: AsyncSession = Depends(get_db)):
    """Current active model plus how close the next auto-retrain is."""
    active = await mlops.get_active_model(db, hospital_id)
    return {
        "active": _to_response(active) if active else None,
        "using_defaults": active is None,
        "retrain_every_n_readings": mlops.RETRAIN_EVERY_N_READINGS,
        "readings_since_last_retrain": mlops.retrain_counter.pending(hospital_id),
        "min_rows_to_train": mlops.MIN_ROWS_TO_TRAIN,
        # Stated in the payload so any client shows the boundary, not just our UI.
        "safety_note": (
            "Retraining tunes only the secondary statistical signal. "
            "Deterministic clinical thresholds and the SOS path are never modified."
        ),
    }


@router.get("/mlops/runs", response_model=List[ModelRunResponse])
async def mlops_runs(
    hospital_id: str = "DEFAULT_HOSP",
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    runs = await mlops.list_runs(db, hospital_id, limit)
    return [_to_response(m) for m in runs]


@router.post("/mlops/retrain", response_model=ModelRunResponse)
async def mlops_retrain(hospital_id: str = "DEFAULT_HOSP", db: AsyncSession = Depends(get_db)):
    model = await mlops.train_new_version(db, hospital_id, trigger="manual")
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                f"Not enough stored readings to train "
                f"(need at least {mlops.MIN_ROWS_TO_TRAIN})."
            ),
        )
    return _to_response(model)


@router.post("/mlops/rollback/{version}", response_model=ModelRunResponse)
async def mlops_rollback(
    version: int,
    hospital_id: str = "DEFAULT_HOSP",
    db: AsyncSession = Depends(get_db),
):
    model = await mlops.rollback_to(db, version, hospital_id)
    if model is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No model version {version} found for this hospital.",
        )
    return _to_response(model)
