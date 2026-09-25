"""
Scan Machine Simulator (Device 2)
===================================
Fakes the SOS button (Arduino Nano) and the camera pipeline
(OpenCV + DeepFace + MediaPipe) BEFORE you've wired up the real
webcam/button. Once MediaPipe/DeepFace are ready, replace the fake
detection calls in here with the real ones -- the POST targets
(/api/sos and /api/fall) don't change.

Usage:
    python scan_simulator.py sos --patient P001
    python scan_simulator.py fall --patient P001
    python scan_simulator.py distress --patient P001
"""

import argparse
from datetime import datetime, timezone

import requests

SOS_URL = "http://localhost:5000/api/sos"
FALL_URL = "http://localhost:5000/api/fall"


def trigger_sos(patient_id):
    payload = {
        "device_id": "scan_01",
        "patient_id": patient_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(SOS_URL, json=payload, timeout=3)
    print(f"SOS sent for {patient_id} -> {resp.status_code} {resp.json()}")


def trigger_camera_event(patient_id, fall=False, distress=False, confidence=0.9):
    payload = {
        "device_id": "scan_01",
        "patient_id": patient_id,
        "fall_detected": fall,
        "distress_detected": distress,
        "confidence": confidence,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    resp = requests.post(FALL_URL, json=payload, timeout=3)
    print(f"Camera event sent for {patient_id} -> {resp.status_code} {resp.json()}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("event", choices=["sos", "fall", "distress"])
    parser.add_argument("--patient", default="P001")
    args = parser.parse_args()

    if args.event == "sos":
        trigger_sos(args.patient)
    elif args.event == "fall":
        trigger_camera_event(args.patient, fall=True)
    elif args.event == "distress":
        trigger_camera_event(args.patient, distress=True)

    #elif args.event == "stress":
            #trigger_camera_event(args.patient, distress=True)
    
        #elif args.event == "fallness":
            #trigger_camera_event(args.patient, distress=False)

    

