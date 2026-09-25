# VitalBand

**Silent emergency detection for the pre-admission gap.**
Team InstantZero · Chennai Institute of Technology · Human-AI Collaboration track

India has roughly **1 doctor per 836 patients**. Patients deteriorate in waiting
rooms and wards without anyone noticing — too weak to speak, too frightened to
ask, or simply alone. Most monitoring protects one moment: a bed-connected
patient, or a general camera. Nobody covers the gap between walking into a
hospital and being formally admitted.

VitalBand covers that gap for about **₹2,000 per patient**, against ₹11,000 for
a basic commercial vitals monitor that does neither fall detection nor facial
distress.

---

## The design rule everything follows

> **The emergency path is always deterministic. AI can raise attention; it can
> never lower it.**

- The **SOS button** fires instantly and unconditionally — no AI in that path.
- **Clinical thresholds** are fixed values, not learned ones.
- The **AI layer** (pose, trend index, language model) only ever adds signal.
  Nothing it produces can suppress, downgrade or delay an alert.

This holds all the way to the language model: Nemotron writes the *explanation*
of a verdict the rule engine already reached, and every sentence it produces is
validated before a nurse sees it.

---

## What runs

| Layer | Stack |
|---|---|
| Backend | FastAPI · SQLAlchemy · SQLite · WebSocket |
| Frontend | React + TypeScript · Vite · Tailwind |
| Vision | MediaPipe Tasks PoseLandmarker (multi-person) · OpenCV |
| Triage | Deterministic rules + JEV Deterioration Index |
| MLOps | Self-retraining baseline with versioning, drift and rollback |
| Language | NVIDIA NIM (Nemotron) behind clinical guardrails |
| Voice | Cached multilingual audio — Tamil, Hindi, Kannada, English |
| Devices | ESP32 + MAX30102 wrist patch · Scan Machine with RFID and SOS |

---

## Quick start

Two terminals, from the repository root.

**Backend**

```bash
cd backend
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
cd .. && backend\.venv\Scripts\python -m uvicorn backend.main:app --port 5000
```

**Frontend**

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:5173>.

Seeded logins: `nurse@vitalband.com` and `admin@vitalband.com`, password
`password` for both. Change these before any real deployment.

### Two assets fetched separately

They are excluded from the repo because they are binaries, not source.

```bash
# Multi-person pose model (5.7 MB) — without it the camera feed
# falls back to single-person tracking, it does not break.
curl -L -o vision/pose_landmarker_lite.task \
  https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task

# Multilingual alert audio (needs internet once, then works offline)
python voice/voice_alerts.py --pregenerate
```

---

## Optional: NVIDIA NIM

Copy `backend/.env.example` to `backend/.env` and add a free key from
[build.nvidia.com](https://build.nvidia.com).

Without a key the system is fully functional — explanations simply fall back to
deterministic rule text. Nothing else changes.

Self-hosted NIM, Riva and Triton/TensorRT-LLM all require a local NVIDIA GPU.
`GET /api/ai/status` reports exactly which services are live and which are
falling back, including on hosts with no NVIDIA hardware.

---

## Layout

```
backend/        FastAPI app, routers, services (triage, MLOps, vision, AI)
frontend/       React dashboard — floorplan, AI drawer, admin console
firmware/       ESP32 + MAX30102 wrist patch (Arduino), with flash script
vision/         Standalone CV demos; run_demo.bat picks the right interpreter
voice/          Multilingual alert generation and cache
simulator/      Fake devices for running without hardware
```

---

## Honest scope

Stated plainly, because overclaiming is the fastest way to lose a reviewer.

- **RFID identifies the wristband, not the face.** Wrong band on the wrong
  wrist resolves to the wrong person. No biometric identification is performed.
- **Person tracking is nearest-neighbour matching**, not re-identification.
  Two people standing very close may swap IDs; RFID check-in resolves identity.
- **DeepFace runs as a standalone demo**, not inside the dashboard — it needs
  OpenCV 4.x while the backend runs OpenCV 5.x. See `vision/run_demo.bat`.
- **The audit chain is signed in-browser** for the demo. Production co-signs
  server-side with an HSM-held key.
- **The retrained model is calibrated statistics**, not deep learning — and it
  needs no labelled dataset, which is deliberate.
- **Detection ranges are estimates** from CV experience: roughly 3–5 m for
  pose, 1.5–2.5 m for facial distress. Not measured specifications.
- Scan Machine coverage is **sequential** as the camera rotates, not
  simultaneous coverage of a whole room at every instant.
