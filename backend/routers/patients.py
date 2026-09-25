"""
VitalBand Patients Router (Multi-Tenant)
"""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc

from backend.database import get_db
from backend.models import Patient, User, VitalsReading
from backend.schemas import PatientResponse, VitalsReadingResponse
from backend.auth import get_current_user

router = APIRouter(tags=["Patients"])


@router.get("/patients", response_model=List[PatientResponse])
async def list_patients(
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    List all patients for the caller's hospital.
    If anonymous, falls back to DEFAULT_HOSP to support the legacy dashboard.
    """
    hospital_id = current_user.hospital_id if current_user else "DEFAULT_HOSP"

    stmt = select(Patient).where(Patient.hospital_id == hospital_id)
    result = await db.execute(stmt)
    patients = result.scalars().all()
    return patients


@router.get("/patient/{patient_id}", response_model=PatientResponse)
async def get_patient(
    patient_id: str,
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get a single patient's state by patient_id, scoped to the caller's hospital.
    If anonymous, falls back to DEFAULT_HOSP.
    """
    hospital_id = current_user.hospital_id if current_user else "DEFAULT_HOSP"

    stmt = select(Patient).where(
        Patient.patient_id == patient_id,
        Patient.hospital_id == hospital_id
    )
    result = await db.execute(stmt)
    patient = result.scalar_one_or_none()

    if not patient:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Patient {patient_id} not found in hospital {hospital_id}"
        )
    return patient


@router.get("/patient/{patient_id}/history", response_model=List[VitalsReadingResponse])
async def get_patient_vitals_history(
    patient_id: str,
    limit: int = Query(default=60, ge=1, le=500),
    current_user: Optional[User] = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Get recent historical time-series vitals readings for charting.
    Returns the most recent readings in chronological order.
    """
    hospital_id = current_user.hospital_id if current_user else "DEFAULT_HOSP"

    stmt = (
        select(VitalsReading)
        .where(
            VitalsReading.patient_id == patient_id,
            VitalsReading.hospital_id == hospital_id
        )
        .order_by(desc(VitalsReading.id))
        .limit(limit)
    )
    result = await db.execute(stmt)
    readings = result.scalars().all()
    # Return in ascending chronological order for charts
    return list(reversed(readings))
