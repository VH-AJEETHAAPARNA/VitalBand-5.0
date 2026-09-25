"""
VitalBand Pydantic Schemas
"""

from typing import Optional, List
from pydantic import BaseModel, ConfigDict, Field, computed_field


# --- Ingestion Payloads (Backwards compatible with hardware & simulators) ---

class SensorPayload(BaseModel):
    device_id: Optional[str] = "wrist_01"
    patient_id: str = "UNKNOWN"
    hospital_id: Optional[str] = "DEFAULT_HOSP"
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    acc_x: Optional[float] = None
    acc_y: Optional[float] = None
    acc_z: Optional[float] = None
    fall: Optional[bool] = False
    sos: Optional[bool] = False
    timestamp: Optional[str] = None


class SensorResponse(BaseModel):
    """Response payload for POST /api/sensor — includes rule-based and ML anomaly scores."""
    status: str = "ok"
    abnormal: bool = False
    reasons: List[str] = []
    z_score: float = 0.0
    anomaly_level: str = "NORMAL"   # NORMAL | WARNING | CRITICAL
    warmed_up: bool = False
    jev_triage: Optional["JEVDecisionPayload"] = None


class JEVDecisionPayload(BaseModel):
    """Exact schema for Human-in-the-Loop JEV Triage Decisions."""
    patient_id: str
    triage_level: str               # LEVEL_1_EMERGENCY | LEVEL_2_URGENT | LEVEL_3_STABLE
    jev_confidence: float
    clinical_reasoning: str
    recommended_action: str
    deterministic_override: bool
    timestamp: str






class SOSPayload(BaseModel):
    device_id: Optional[str] = "scan_01"
    patient_id: str = "UNKNOWN"
    hospital_id: Optional[str] = "DEFAULT_HOSP"
    timestamp: Optional[str] = None


class CameraEventPayload(BaseModel):
    device_id: Optional[str] = "scan_01"
    patient_id: str = "UNKNOWN"
    hospital_id: Optional[str] = "DEFAULT_HOSP"
    fall_detected: Optional[bool] = False
    distress_detected: Optional[bool] = False
    confidence: Optional[float] = None
    timestamp: Optional[str] = None


class RFIDPayload(BaseModel):
    device_id: Optional[str] = "scan_01"
    patient_id: str = "UNKNOWN"
    hospital_id: Optional[str] = "DEFAULT_HOSP"
    rfid_uid: str


# --- API Responses ---

class PatientResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    patient_id: str
    hospital_id: str
    name: Optional[str] = None
    rfid_uid: Optional[str] = None
    device_id: Optional[str] = None
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    fall_status: str
    sos_status: str
    distress_status: str
    wrist_connected: int
    scan_connected: int
    last_updated: str

    @computed_field
    @property
    def fall(self) -> bool:
        return self.fall_status == "FALL DETECTED"

    @computed_field
    @property
    def sos(self) -> bool:
        return self.sos_status == "SOS TRIGGERED"

    @computed_field
    @property
    def distress(self) -> bool:
        return self.distress_status == "DISTRESS DETECTED"

    @computed_field
    @property
    def abnormal(self) -> bool:
        if self.heart_rate is not None and not (50 <= self.heart_rate <= 120):
            return True
        if self.spo2 is not None and self.spo2 < 92:
            return True
        return False


class EventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_id: str
    patient_id: str
    event_type: str
    details: Optional[str] = None
    severity: str
    timestamp: str


class VitalsReadingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    hospital_id: str
    patient_id: str
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    timestamp: str


# --- Auth & User Schemas ---

class LoginRequest(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str = "bearer"


class TokenData(BaseModel):
    email: Optional[str] = None
    user_id: Optional[str] = None
    hospital_id: Optional[str] = None
    role: Optional[str] = None


class UserCreate(BaseModel):
    email: str
    password: str
    full_name: str
    role: str = "nurse"  # nurse, admin, super_admin
    hospital_id: Optional[str] = "DEFAULT_HOSP"


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    email: str
    full_name: str
    role: str
    hospital_id: Optional[str] = None
    created_at: str


# --- JEV Deterioration Index (Human-in-the-Loop triage drawer) ---

class JEVTriageRequest(BaseModel):
    """Time-series telemetry window for POST /api/v1/jev-triage."""
    patient_id: str = "UNKNOWN"
    hospital_id: Optional[str] = "DEFAULT_HOSP"
    heart_rate: List[Optional[int]] = Field(default_factory=list)
    spo2: List[Optional[int]] = Field(default_factory=list)
    motion: List[Optional[float]] = Field(default_factory=list)
    # Current deterministic flags. Without these the rule path would always be
    # evaluated as "no fall, no SOS", so a pressed panic button would never be
    # reflected as a deterministic override in the drawer.
    fall: bool = False
    sos: bool = False


class JEVContributor(BaseModel):
    factor: str
    value: str
    weighted_points: float


class JEVTriageResponse(BaseModel):
    patient_id: str
    deterioration_index: float          # 0-100
    confidence_score: float
    warmed_up: bool
    frames_analysed: int
    contributors: List[JEVContributor] = []
    escalate: bool
    severity: str
    clinical_rationale: str
    recommended_action: str
    # Mirrors the deterministic rule verdict so the UI can show that the
    # safety path is independent of, and unblocked by, this score.
    deterministic_triage: Optional[JEVDecisionPayload] = None
    timestamp: str
