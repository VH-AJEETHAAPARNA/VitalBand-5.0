"""
VitalBand SQLAlchemy Data Models (Multi-Tenant)
"""

from datetime import datetime, timezone
import uuid
from sqlalchemy import Column, String, Integer, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship

from backend.database import Base


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Hospital(Base):
    __tablename__ = "hospitals"

    id = Column(String(50), primary_key=True, default=lambda: f"hosp_{uuid.uuid4().hex[:8]}")
    name = Column(String(100), nullable=False)
    code = Column(String(20), unique=True, nullable=False)
    created_at = Column(String(50), default=now_iso)

    # Relationships
    users = relationship("User", back_populates="hospital")
    patients = relationship("Patient", back_populates="hospital")
    devices = relationship("Device", back_populates="hospital")
    events = relationship("Event", back_populates="hospital")


class User(Base):
    __tablename__ = "users"

    id = Column(String(50), primary_key=True, default=lambda: f"user_{uuid.uuid4().hex[:8]}")
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=True)  # Null for super-admin
    email = Column(String(100), unique=True, nullable=False, index=True)
    hashed_password = Column(String(255), nullable=False)
    full_name = Column(String(100), nullable=False)
    role = Column(String(20), nullable=False, default="nurse")  # nurse, admin, super_admin
    created_at = Column(String(50), default=now_iso)

    hospital = relationship("Hospital", back_populates="users")


class Device(Base):
    __tablename__ = "devices"

    device_id = Column(String(50), primary_key=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")
    device_type = Column(String(30), nullable=False)  # wrist_patch, scan_machine
    firmware_version = Column(String(20), default="1.0.0")
    last_seen = Column(String(50), default=now_iso)

    hospital = relationship("Hospital", back_populates="devices")


class Patient(Base):
    __tablename__ = "patients"

    patient_id = Column(String(50), primary_key=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")
    name = Column(String(100), default="General Patient")
    rfid_uid = Column(String(50), nullable=True)
    device_id = Column(String(50), nullable=True)
    heart_rate = Column(Integer, nullable=True)
    spo2 = Column(Integer, nullable=True)
    fall_status = Column(String(30), default="NORMAL")
    sos_status = Column(String(30), default="NORMAL")
    distress_status = Column(String(30), default="NORMAL")
    wrist_connected = Column(Integer, default=0)
    scan_connected = Column(Integer, default=0)
    last_updated = Column(String(50), default=now_iso)

    hospital = relationship("Hospital", back_populates="patients")


class Event(Base):
    __tablename__ = "events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")
    patient_id = Column(String(50), nullable=False)
    event_type = Column(String(50), nullable=False)
    details = Column(Text, nullable=True)
    severity = Column(String(20), default="INFO")  # INFO, WARNING, CRITICAL
    timestamp = Column(String(50), default=now_iso)

    hospital = relationship("Hospital", back_populates="events")


class VitalsReading(Base):
    __tablename__ = "vitals_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")
    patient_id = Column(String(50), nullable=False, index=True)
    heart_rate = Column(Integer, nullable=True)
    spo2 = Column(Integer, nullable=True)
    timestamp = Column(String(50), default=now_iso, index=True)



class ModelVersion(Base):
    """
    Registry of trained anomaly-baseline models (in-process MLOps).

    IMPORTANT SAFETY BOUNDARY: a model recorded here only ever tunes the
    SECONDARY statistical anomaly signal. It can never change the
    deterministic clinical thresholds or the SOS path — those stay fixed in
    config.py and jev_engine.py by design, so no amount of retraining can
    make VitalBand miss an emergency it would previously have caught.
    """
    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")
    version = Column(Integer, nullable=False, index=True)
    status = Column(String(20), nullable=False, default="active")  # active | archived
    trigger = Column(String(30), nullable=False, default="auto")   # auto | manual | rollback

    trained_on_rows = Column(Integer, nullable=False, default=0)
    params_json = Column(Text, nullable=True)    # learned distribution parameters
    metrics_json = Column(Text, nullable=True)   # flag rate, drift, coverage
    notes = Column(Text, nullable=True)

    created_at = Column(String(50), default=now_iso, index=True)


class PatientRecord(Base):
    """
    Clinical record shown when a patient is identified (RFID check-in, or a
    nurse opening their card).

    Deliberately a SEPARATE table from `patients`: that table is live device
    state written on every telemetry post, while this is slow-changing
    admissions data. Keeping them apart also means this can be added to an
    existing database without migrating the hot table.
    """
    __tablename__ = "patient_records"

    patient_id = Column(String(50), primary_key=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")

    full_name = Column(String(100), nullable=True)
    age = Column(Integer, nullable=True)
    gender = Column(String(20), nullable=True)
    # Who brought them in / who to call — the "role" in a family context.
    relation = Column(String(40), nullable=True)
    attendant_name = Column(String(100), nullable=True)
    attendant_phone = Column(String(30), nullable=True)

    blood_group = Column(String(10), nullable=True)
    allergies = Column(Text, nullable=True)
    conditions = Column(Text, nullable=True)      # ongoing diagnoses
    medications = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)

    admitted_at = Column(String(50), nullable=True)
    updated_at = Column(String(50), default=now_iso)


class MedicalTest(Base):
    """A prior investigation: blood, MRI, sugar, urine, X-ray and so on."""
    __tablename__ = "medical_tests"

    id = Column(Integer, primary_key=True, autoincrement=True)
    patient_id = Column(String(50), nullable=False, index=True)
    hospital_id = Column(String(50), ForeignKey("hospitals.id"), nullable=False, default="DEFAULT_HOSP")

    test_type = Column(String(40), nullable=False)   # BLOOD | MRI | SUGAR | URINE | XRAY | ECG
    result_summary = Column(Text, nullable=True)
    status = Column(String(20), default="COMPLETED")  # COMPLETED | PENDING | ABNORMAL
    taken_at = Column(String(50), default=now_iso)
