"""
Wrist Patch Simulator (Device 1)
=================================
Fakes what the real ESP32 wrist patch (MAX30102 + MPU6050) will eventually
send. Posts to the SAME /api/sensor endpoint the real hardware will use later
-- so when the real ESP32 is ready, you just point it at this URL and change
nothing in the backend.

Usage:
    python wrist_simulator.py                           # normal patient, loops forever
    python wrist_simulator.py --scenario fall
    python wrist_simulator.py --scenario high_hr
    python wrist_simulator.py --scenario low_spo2
    python wrist_simulator.py --scenario drift          # gradual HR drift to trigger ML scorer
    python wrist_simulator.py --patient P002
    python wrist_simulator.py --url https://<ngrok>.ngrok-free.app/api/sensor
"""

import argparse
import random
import time
from datetime import datetime, timezone

import requests

DEFAULT_URL = "http://localhost:5000/api/sensor"


def make_reading(patient_id: str, scenario: str, step: int) -> dict:
    hr   = random.randint(65, 90)
    spo2 = random.randint(96, 99)
    fall = False
    acc  = {
        "acc_x": round(random.uniform(-0.2, 0.2), 2),
        "acc_y": round(random.uniform(-0.2, 0.2), 2),
        "acc_z": round(random.uniform(9.5, 9.9), 2),
    }

    if scenario == "high_hr":
        hr = random.randint(125, 150)

    elif scenario == "low_spo2":
        spo2 = random.randint(80, 90)

    elif scenario == "fall":
        fall = True
        acc  = {
            "acc_x": round(random.uniform(-3, 3), 2),
            "acc_y": round(random.uniform(-3, 3), 2),
            "acc_z": round(random.uniform(0, 2), 2),
        }

    elif scenario == "drift":
        # First 15 readings: stable baseline (70–75 bpm)
        # After step 15:     HR gradually climbs → triggers ML anomaly scorer
        if step < 15:
            hr = random.randint(70, 75)
        else:
            # Drift: adds ~5 bpm per step above baseline
            drift = min((step - 15) * 5, 80)
            hr = random.randint(75 + drift, 80 + drift)

    return {
        "device_id":  "wrist_01",
        "patient_id": patient_id,
        "heart_rate": hr,
        "spo2":       spo2,
        "fall":       fall,
        "sos":        False,
        "timestamp":  datetime.now(timezone.utc).isoformat(),
        **acc,
    }


def print_response(reading: dict, resp_json: dict) -> None:
    """Pretty-print the enriched SensorResponse from the backend."""
    tag      = "ALERT" if resp_json.get("abnormal") or reading["fall"] else "ok"
    z        = resp_json.get("z_score", 0.0)
    level    = resp_json.get("anomaly_level", "N/A")
    warmed   = "✓" if resp_json.get("warmed_up") else "…warming"
    hr       = reading["heart_rate"]
    spo2     = reading["spo2"]
    reasons  = "; ".join(resp_json.get("reasons", [])) or "none"

    tag_col = "\033[91m" if tag == "ALERT" else "\033[92m"  # red / green ANSI
    reset   = "\033[0m"

    print(
        f"{tag_col}[{tag:5s}]{reset} "
        f"HR={hr:3d}  SpO2={spo2}%  fall={str(reading['fall']):5s}  "
        f"z={z:+.2f}  level={level:8s}  ml={warmed}  reasons={reasons}"
    )


def run(patient_id: str, scenario: str, interval: float, url: str) -> None:
    print(f"Wrist simulator → patient={patient_id}  scenario={scenario}")
    print(f"Posting to {url} every {interval}s.  Ctrl+C to stop.\n")
    step = 0
    while True:
        reading = make_reading(patient_id, scenario, step)
        step += 1
        try:
            resp      = requests.post(url, json=reading, timeout=5)
            resp_json = resp.json()
            print_response(reading, resp_json)
        except requests.exceptions.ConnectionError:
            print("✗ Could not reach backend — is app.py running?")
        except Exception as e:
            print(f"✗ Error: {e}")
        time.sleep(interval)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="VitalBand Wrist Patch Simulator")
    parser.add_argument("--patient",  default="P001",          help="Patient ID")
    parser.add_argument("--scenario", default="normal",
                        choices=["normal", "high_hr", "low_spo2", "fall", "drift"],
                        help="Simulation scenario")
    parser.add_argument("--interval", type=float, default=3.0, help="Seconds between readings")
    parser.add_argument("--url",      default=DEFAULT_URL,     help="Backend /api/sensor URL (supports ngrok)")
    args = parser.parse_args()
    run(args.patient, args.scenario, args.interval, args.url)
