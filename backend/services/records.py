"""
VitalBand Patient Records & RFID Identity
=========================================
Turns a detection into an identified patient with a clinical record.

The gap this closes: the camera can see that *someone* has collapsed, but
without a check-in it can only call them `unidentified_person_2` — a position
label within a session, not a person. An RFID tap binds that tag to a real
patient id, so the nurse gets a name, age, conditions and prior tests instead
of a bounding box.

Honest boundary: the tap identifies the WRISTBAND, not the face. If the wrong
band is on the wrong wrist this resolves to the wrong person, exactly as a
paper wristband would. The camera is not doing biometric identification and
nothing here claims it is.
"""

import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from backend.models import Patient, PatientRecord, MedicalTest

logger = logging.getLogger("vitalband.records")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def get_record(db: AsyncSession, patient_id: str) -> Optional[PatientRecord]:
    stmt = select(PatientRecord).where(PatientRecord.patient_id == patient_id)
    return (await db.execute(stmt)).scalar_one_or_none()


async def get_tests(db: AsyncSession, patient_id: str, limit: int = 20) -> List[MedicalTest]:
    stmt = (
        select(MedicalTest)
        .where(MedicalTest.patient_id == patient_id)
        .order_by(desc(MedicalTest.taken_at))
        .limit(limit)
    )
    return list((await db.execute(stmt)).scalars().all())


async def resolve_rfid(db: AsyncSession, rfid_uid: str, hospital_id: str = "DEFAULT_HOSP") -> Optional[str]:
    """
    RFID tag -> patient_id, by looking at who currently wears that tag.
    Returns None when the tag is unknown, which the caller must treat as
    "unidentified", never as a default patient.
    """
    stmt = select(Patient).where(
        Patient.rfid_uid == rfid_uid,
        Patient.hospital_id == hospital_id,
    )
    patient = (await db.execute(stmt)).scalar_one_or_none()
    return patient.patient_id if patient else None


async def upsert_record(db: AsyncSession, patient_id: str, hospital_id: str = "DEFAULT_HOSP", **fields) -> PatientRecord:
    record = await get_record(db, patient_id)
    if record is None:
        record = PatientRecord(patient_id=patient_id, hospital_id=hospital_id)
        db.add(record)

    for key, value in fields.items():
        if value is not None and hasattr(record, key):
            setattr(record, key, value)

    record.updated_at = now_iso()
    await db.commit()
    await db.refresh(record)
    return record


async def add_test(
    db: AsyncSession,
    patient_id: str,
    test_type: str,
    result_summary: str,
    status: str = "COMPLETED",
    hospital_id: str = "DEFAULT_HOSP",
    taken_at: Optional[str] = None,
) -> MedicalTest:
    test = MedicalTest(
        patient_id=patient_id,
        hospital_id=hospital_id,
        test_type=test_type.upper(),
        result_summary=result_summary,
        status=status,
        taken_at=taken_at or now_iso(),
    )
    db.add(test)
    await db.commit()
    await db.refresh(test)
    return test


# ── Demo seed ────────────────────────────────────────────────────────────────
# Synthetic records for demonstration. No real patient data is used anywhere in
# this project, which is also why it needs no dataset collection or consent.

_SEED: List[Dict] = [
    {
        "patient_id": "P001",
        "full_name": "Ramesh Kumar",
        "age": 57, "gender": "Male", "relation": "Father",
        "attendant_name": "Lakshmi Kumar", "attendant_phone": "+91 98400 11223",
        "blood_group": "B+",
        "allergies": "Penicillin",
        "conditions": "Type 2 diabetes (8 yrs); hypertension",
        "medications": "Metformin 1000mg BD; Amlodipine 5mg OD",
        "notes": "Chest discomfort on arrival. Not yet formally admitted.",
        "tests": [
            ("BLOOD", "Hb 12.1 g/dL, WBC 9.4k, platelets normal", "COMPLETED"),
            ("SUGAR", "Fasting 168 mg/dL - above target", "ABNORMAL"),
            ("ECG", "Sinus tachycardia, no ST elevation", "COMPLETED"),
            ("XRAY", "Chest PA - mild cardiomegaly", "COMPLETED"),
        ],
    },
    {
        "patient_id": "P004",
        "full_name": "Anitha Selvam",
        "age": 34, "gender": "Female", "relation": "Mother",
        "attendant_name": "Selvam R", "attendant_phone": "+91 99620 55871",
        "blood_group": "O+",
        "allergies": "None known",
        "conditions": "Iron-deficiency anaemia",
        "medications": "Ferrous sulphate OD",
        "notes": "Reported dizziness in the waiting area.",
        "tests": [
            ("BLOOD", "Hb 9.2 g/dL - low", "ABNORMAL"),
            ("URINE", "Routine - no growth", "COMPLETED"),
        ],
    },
    {
        "patient_id": "P007",
        "full_name": "Iqbal Ahmed",
        "age": 68, "gender": "Male", "relation": "Grandfather",
        "attendant_name": "Sameer Ahmed", "attendant_phone": "+91 90030 44182",
        "blood_group": "A-",
        "allergies": "Sulfa drugs",
        "conditions": "COPD; prior MI (2023)",
        "medications": "Salbutamol inhaler PRN; Aspirin 75mg OD",
        "notes": "Breathless on exertion. Desaturating - priority review.",
        "tests": [
            ("BLOOD", "Hb 13.4 g/dL, CRP elevated", "ABNORMAL"),
            ("XRAY", "Hyperinflated lung fields", "COMPLETED"),
            ("MRI", "Brain - no acute infarct", "COMPLETED"),
            ("SUGAR", "Random 112 mg/dL", "COMPLETED"),
        ],
    },
    {
        "patient_id": "P010",
        "full_name": "Meena Devi",
        "age": 45, "gender": "Female", "relation": "Mother",
        "attendant_name": "Karthik D", "attendant_phone": "+91 94440 27310",
        "blood_group": "AB+",
        "allergies": "None known",
        "conditions": "Migraine",
        "medications": "Sumatriptan PRN",
        "notes": "Waiting-room patient, no wearable. Camera coverage only.",
        "tests": [
            ("MRI", "Brain - normal study", "COMPLETED"),
            ("URINE", "Routine - normal", "COMPLETED"),
        ],
    },
]


async def seed_demo_records(db: AsyncSession, hospital_id: str = "DEFAULT_HOSP") -> int:
    """Idempotent: only writes records that do not already exist."""
    created = 0
    for entry in _SEED:
        pid = entry["patient_id"]
        if await get_record(db, pid):
            continue

        tests = entry.pop("tests", [])
        fields = {k: v for k, v in entry.items() if k != "patient_id"}
        await upsert_record(db, pid, hospital_id=hospital_id, **fields)
        entry["tests"] = tests  # restore so a second call is identical

        for test_type, summary, status in tests:
            await add_test(db, pid, test_type, summary, status, hospital_id=hospital_id)
        created += 1

    if created:
        logger.info("Seeded %d demo clinical records", created)
    return created
