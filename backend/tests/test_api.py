"""
VitalBand Backend API Integration Tests
"""

import os
import asyncio
import pytest
from fastapi.testclient import TestClient

# Override DB path for testing to an isolated SQLite DB
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./vitalband_test.db"

from backend.main import app
from backend.database import Base, engine

client = TestClient(app)


@pytest.fixture(autouse=True, scope="module")
def setup_test_db():
    """Initializes the database before running tests synchronously using asyncio.run."""
    async def _init():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def _cleanup():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)

    # Run DB setup synchronously
    loop = asyncio.get_event_loop_policy().get_event_loop()
    if loop.is_closed():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    loop.run_until_complete(_init())
    yield
    loop.run_until_complete(_cleanup())


def test_auth_login_fail():
    """Test login failure with incorrect credentials."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nurse@vitalband.com", "password": "wrongpassword"}
    )
    assert response.status_code == 401
    assert "detail" in response.json()


def test_sensor_ingestion_normal():
    """Test /api/sensor telemetry ingestion with normal vitals."""
    payload = {
        "device_id": "wrist_test_01",
        "patient_id": "P_TEST_01",
        "hospital_id": "DEFAULT_HOSP",
        "heart_rate": 75,
        "spo2": 98,
        "fall": False,
        "timestamp": "2026-08-28T14:00:00Z"
    }
    response = client.post("/api/sensor", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    assert res_data["abnormal"] is False
    # SensorResponse now includes ML score fields
    assert "z_score" in res_data
    assert "anomaly_level" in res_data
    assert "warmed_up" in res_data


def test_anomaly_scorer_warmup():
    """During warm-up (<10 readings), scorer must always return NORMAL regardless of values."""
    from backend.services.anomaly_scorer import PatientBaselineTracker

    tracker = PatientBaselineTracker()
    # Push 9 readings (below MIN_READINGS=10)
    for _ in range(9):
        result = tracker.score("WARMUP_P", hr=75, spo2=98)
    assert result["warmed_up"] is False
    assert result["anomaly_level"] == "NORMAL"
    assert result["z_score"] == 0.0


def test_anomaly_scorer_drift():
    """After warm-up, a sudden extreme reading must trigger WARNING or CRITICAL."""
    from backend.services.anomaly_scorer import PatientBaselineTracker

    tracker = PatientBaselineTracker()
    # Establish a stable baseline of 75 bpm
    for _ in range(15):
        tracker.score("DRIFT_P", hr=75, spo2=98)

    # Inject a wildly different HR (e.g., 150 bpm) — should trigger WARNING/CRITICAL
    result = tracker.score("DRIFT_P", hr=150, spo2=98)
    assert result["warmed_up"] is True
    assert result["anomaly_level"] in ("WARNING", "CRITICAL")
    assert result["z_score"] > 2.0




def test_sensor_ingestion_abnormal_hr():
    """Test /api/sensor telemetry with high heart rate."""
    payload = {
        "device_id": "wrist_test_01",
        "patient_id": "P_TEST_01",
        "hospital_id": "DEFAULT_HOSP",
        "heart_rate": 135,  # Threshold > 120
        "spo2": 98,
        "fall": False,
        "timestamp": "2026-08-28T14:00:05Z"
    }
    response = client.post("/api/sensor", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    assert res_data["abnormal"] is True


def test_sensor_ingestion_low_spo2():
    """Test /api/sensor telemetry with low SpO2."""
    payload = {
        "device_id": "wrist_test_01",
        "patient_id": "P_TEST_02",
        "hospital_id": "DEFAULT_HOSP",
        "heart_rate": 80,
        "spo2": 88,  # Threshold < 92
        "fall": False,
        "timestamp": "2026-08-28T14:00:10Z"
    }
    response = client.post("/api/sensor", json=payload)
    assert response.status_code == 200
    res_data = response.json()
    assert res_data["status"] == "ok"
    assert res_data["abnormal"] is True


def test_sos_ingestion():
    """Test SOS button trigger endpoint."""
    payload = {
        "device_id": "scan_test_01",
        "patient_id": "P_TEST_01",
        "hospital_id": "DEFAULT_HOSP",
        "timestamp": "2026-08-28T14:00:15Z"
    }
    response = client.post("/api/sos", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_camera_event_fall():
    """Test computer vision fall detection ingestion."""
    payload = {
        "device_id": "scan_test_01",
        "patient_id": "P_TEST_01",
        "hospital_id": "DEFAULT_HOSP",
        "fall_detected": True,
        "distress_detected": False,
        "confidence": 0.95
    }
    response = client.post("/api/fall", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_rfid_scan():
    """Test RFID check-in endpoint."""
    payload = {
        "device_id": "scan_test_01",
        "patient_id": "P_TEST_01",
        "hospital_id": "DEFAULT_HOSP",
        "rfid_uid": "E004B2C3"
    }
    response = client.post("/api/rfid", json=payload)
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_query_patients():
    """Test fetching patient list and patient details."""
    response = client.get("/api/patients")
    assert response.status_code == 200
    patients = response.json()
    assert len(patients) >= 2
    
    # Check that computed properties are properly serialized
    patient_ids = [p["patient_id"] for p in patients]
    assert "P_TEST_01" in patient_ids
    assert "P_TEST_02" in patient_ids

    # Detail view
    response_detail = client.get("/api/patient/P_TEST_01")
    assert response_detail.status_code == 200
    p_data = response_detail.json()
    assert p_data["patient_id"] == "P_TEST_01"
    assert p_data["rfid_uid"] == "E004B2C3"


def test_query_alerts_and_history():
    """Test fetching event history and active alerts."""
    response_alerts = client.get("/api/alerts")
    assert response_alerts.status_code == 200
    alerts = response_alerts.json()
    assert len(alerts) > 0
    # Alerts should contain only WARNING or CRITICAL severities
    for a in alerts:
        assert a["severity"] in ["WARNING", "CRITICAL"]

    response_hist = client.get("/api/history")
    assert response_hist.status_code == 200
    hist = response_hist.json()
    assert len(hist) > 0
    # Full history contains all events, including INFO level (like RFID_SCAN)
    severities = [h["severity"] for h in hist]
    assert "INFO" in severities


def test_patient_vitals_history():
    """Test retrieving chronological vitals time-series for charts."""
    response = client.get("/api/patient/P_TEST_01/history")
    assert response.status_code == 200
    readings = response.json()
    assert len(readings) >= 2
    assert all("heart_rate" in r and "spo2" in r for r in readings)
    assert all(r["patient_id"] == "P_TEST_01" for r in readings)


def test_cv_pipeline_evaluation():
    """Test the computer vision detection engine logic."""
    from backend.services.cv_pipeline import cv_pipeline

    # Horizontal pose (fall: angle > 45 deg)
    landmarks = {
        "left_shoulder": (0.2, 0.5, 0.9),
        "right_shoulder": (0.3, 0.5, 0.9),
        "left_hip": (0.7, 0.5, 0.9),
        "right_hip": (0.8, 0.5, 0.9),
    }
    emotions = {"fear": 0.8, "happy": 0.1, "neutral": 0.1}

    result = cv_pipeline.process_telemetry_event(landmarks, emotions)
    assert result["fall_detected"] is True
    assert result["distress_detected"] is True
    assert result["confidence"] > 0.7


def test_jev_decision_engine_override():
    """Test JEV Decision Engine deterministic safety override on critical vitals."""
    from backend.services.jev_engine import jev_engine

    # Critical low SpO2 (84%) + high HR (142) -> LEVEL_1_EMERGENCY with deterministic_override=True
    triage = jev_engine.evaluate_triage("P_JEV_01", heart_rate=142, spo2=84, fall=False, sos=False)
    assert triage.patient_id == "P_JEV_01"
    assert triage.triage_level == "LEVEL_1_EMERGENCY"
    assert triage.deterministic_override is True
    assert triage.jev_confidence >= 0.94
    assert "ICU bed dispatch" in triage.recommended_action


def test_jev_decision_engine_trend():
    """Test JEV Decision Engine trend correlation on progressive vitals drift."""
    from backend.services.jev_engine import jev_engine

    # Establish baseline trajectory
    jev_engine.evaluate_triage("P_JEV_02", heart_rate=75, spo2=98)
    jev_engine.evaluate_triage("P_JEV_02", heart_rate=85, spo2=96)
    triage = jev_engine.evaluate_triage("P_JEV_02", heart_rate=115, spo2=91)

    assert triage.patient_id == "P_JEV_02"
    assert triage.triage_level in ("LEVEL_2_URGENT", "LEVEL_1_EMERGENCY")
    assert "timestamp" in triage.model_dump()

