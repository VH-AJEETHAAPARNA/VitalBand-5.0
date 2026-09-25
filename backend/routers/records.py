"""
VitalBand Clinical Record Routes
================================
GET /api/patient/{id}/record   full record + prior tests
GET /api/rfid/{uid}/resolve    RFID tag -> patient identity
"""

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.database import get_db
from backend.services import records as rec

router = APIRouter(tags=["Records"])


class MedicalTestResponse(BaseModel):
    id: int
    test_type: str
    result_summary: Optional[str] = None
    status: str
    taken_at: str


class PatientRecordResponse(BaseModel):
    patient_id: str
    identified: bool
    full_name: Optional[str] = None
    age: Optional[int] = None
    gender: Optional[str] = None
    relation: Optional[str] = None
    attendant_name: Optional[str] = None
    attendant_phone: Optional[str] = None
    blood_group: Optional[str] = None
    allergies: Optional[str] = None
    conditions: Optional[str] = None
    medications: Optional[str] = None
    notes: Optional[str] = None
    admitted_at: Optional[str] = None
    tests: List[MedicalTestResponse] = []


@router.get("/patient/{patient_id}/record", response_model=PatientRecordResponse)
async def get_patient_record(patient_id: str, db: AsyncSession = Depends(get_db)):
    """
    Returns identified=False rather than 404 when no record exists, so the UI
    can say "unidentified — no record on file" instead of showing an error.
    That distinction matters: a person with no record is still a person the
    camera is watching.
    """
    record = await rec.get_record(db, patient_id)
    if record is None:
        return PatientRecordResponse(patient_id=patient_id, identified=False)

    tests = await rec.get_tests(db, patient_id)
    return PatientRecordResponse(
        patient_id=patient_id,
        identified=True,
        full_name=record.full_name,
        age=record.age,
        gender=record.gender,
        relation=record.relation,
        attendant_name=record.attendant_name,
        attendant_phone=record.attendant_phone,
        blood_group=record.blood_group,
        allergies=record.allergies,
        conditions=record.conditions,
        medications=record.medications,
        notes=record.notes,
        admitted_at=record.admitted_at,
        tests=[
            MedicalTestResponse(
                id=t.id, test_type=t.test_type, result_summary=t.result_summary,
                status=t.status, taken_at=t.taken_at,
            )
            for t in tests
        ],
    )


@router.get("/rfid/{rfid_uid}/resolve")
async def resolve_rfid_tag(
    rfid_uid: str,
    hospital_id: str = "DEFAULT_HOSP",
    db: AsyncSession = Depends(get_db),
):
    """Resolve a scanned tag to a patient identity."""
    patient_id = await rec.resolve_rfid(db, rfid_uid, hospital_id)
    if patient_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"RFID tag '{rfid_uid}' is not assigned to any patient.",
        )
    return {"rfid_uid": rfid_uid, "patient_id": patient_id, "identified": True}
