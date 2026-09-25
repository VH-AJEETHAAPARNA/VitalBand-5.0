"""
DeepFace Facial Distress Detection (Scan Machine, final AI piece)
=====================================================================
STAGE 1: Run standalone first (no backend needed) to confirm your webcam
         + DeepFace are working and print emotion scores on your own face.
STAGE 2: The distress RULE below runs on top of those scores automatically
         -- test it by making a pained/fearful/distressed face at the camera.
STAGE 3: When confident it works, run with --send to POST distress events
         to your VitalBand backend at /api/fall (same endpoint MediaPipe
         and scan_simulator.py already use -- no backend changes needed).

Usage:
    python deepface_distress.py                        # just watch scores locally
    python deepface_distress.py --send --patient P001   # also POST to backend

Press 'q' in the video window to quit.

Requirements:
    pip install deepface tf-keras opencv-python requests
    (first run downloads DeepFace's model weights automatically -- needs
    internet once, then it's cached locally)

Notes:
- DeepFace is PRETRAINED. Nothing here is trained on your own data.
- Analysis is run every ANALYSIS_EVERY_N_FRAMES frames, not every frame,
  because DeepFace is much slower than MediaPipe -- running it every frame
  would make the video feel frozen.
"""

import argparse
import time
from collections import deque

import cv2

try:
    from deepface import DeepFace
except ImportError:
    DeepFace = None

try:
    import requests
except ImportError:
    requests = None

BACKEND_FALL_URL = "http://localhost:5000/api/fall"

# ---------------------------------------------------------------------------
# Distress-rule tuning constants
# ---------------------------------------------------------------------------
ANALYSIS_EVERY_N_FRAMES = 15
DISTRESS_EMOTIONS = {"fear", "sad", "angry"}
DISTRESS_SCORE_THRESHOLD = 70.0
NEUTRAL_MARGIN_REQUIRED = 15.0
CONSECUTIVE_HITS_REQUIRED = 5


class DistressDetector:
    """
    Wraps DeepFace's pretrained emotion model with a simple temporal rule:
    a single distressed-looking frame does NOT trigger an alert. Only a
    short streak of consecutive distress readings does. This is the same
    "don't trust one frame" principle used in the fall detector.
    """

    def __init__(self):
        self.hit_streak = 0
        self.confirmed = False

    def update(self, frame):
        try:
            result = DeepFace.analyze(
                frame, actions=["emotion"], enforce_detection=False, silent=True
            )
            emotions = result[0]["emotion"] if isinstance(result, list) else result["emotion"]
        except Exception as e:
            return {"confirmed": self.confirmed, "top_emotion": None, "error": str(e)}

        top_emotion = max(emotions, key=emotions.get)
        top_score = emotions[top_emotion]
        neutral_score = emotions.get("neutral", 0)

        is_distress_frame = (
            top_emotion in DISTRESS_EMOTIONS
            and top_score >= DISTRESS_SCORE_THRESHOLD
            and (top_score - neutral_score) >= NEUTRAL_MARGIN_REQUIRED
        )

        if is_distress_frame:
            self.hit_streak += 1
        else:
            self.hit_streak = 0

        self.confirmed = self.hit_streak >= CONSECUTIVE_HITS_REQUIRED

        return {
            "confirmed": self.confirmed,
            "top_emotion": top_emotion,
            "top_score": round(float(top_score), 1),
            "streak": self.hit_streak,
        }


def run(send_to_backend, patient_id, camera_index):
    if DeepFace is None:
        print("DeepFace is not installed. Run: pip install deepface tf-keras")
        return

    detector = DistressDetector()
    already_alerted = False
    frame_count = 0
    last_info = {"confirmed": False, "top_emotion": "-", "top_score": 0}

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Could not open camera index {camera_index}. Try --camera 1.")
        return

    print("DeepFace distress detector running. Press 'q' to quit.")
    print("(First analysis may take a few seconds while models load.)\n")

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        frame_count += 1

        if frame_count % ANALYSIS_EVERY_N_FRAMES == 0:
            last_info = detector.update(frame)

            if last_info.get("error"):
                pass  # no face found this cycle -- just keep showing last known state
            elif last_info["confirmed"] and not already_alerted:
                print(f">>> DISTRESS CONFIRMED << ({last_info['top_emotion']} "
                      f"{last_info['top_score']}%)")
                if send_to_backend and requests is not None:
                    try:
                        r = requests.post(
                            BACKEND_FALL_URL,
                            json={
                                "device_id": "scan_01",
                                "patient_id": patient_id,
                                "fall_detected": False,
                                "distress_detected": True,
                                "confidence": round(last_info["top_score"] / 100, 2),
                            },
                            timeout=3,
                        )
                        print(f"Posted to backend -> {r.status_code}")
                    except Exception as e:
                        print(f"Could not reach backend: {e}")
                already_alerted = True
            elif not last_info["confirmed"]:
                already_alerted = False

        color = (0, 0, 255) if last_info.get("confirmed") else (0, 200, 0)
        label = f"{last_info.get('top_emotion', '-')} {last_info.get('top_score', 0)}%"
        status = "DISTRESS CONFIRMED" if last_info.get("confirmed") else label

        cv2.putText(frame, status, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)
        cv2.imshow("VitalBand - DeepFace Distress Detection", frame)

        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="POST distress events to backend /api/fall")
    parser.add_argument("--patient", default="P001")
    parser.add_argument("--camera", type=int, default=0, help="webcam index, try 1 if 0 fails")
    args = parser.parse_args()
    run(args.send, args.patient, args.camera)