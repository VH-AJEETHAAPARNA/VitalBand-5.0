"""
MediaPipe Fall Detection (Scan Machine, Step 5-6 of the build plan)
=====================================================================
STAGE 1: Run this standalone first (no backend needed) to confirm your
         webcam + MediaPipe are working and print pose landmarks.
STAGE 2: Once you see keypoints printing, the fall RULE below runs on
         top of them automatically -- test it by actually leaning/falling
         in front of the camera.
STAGE 3: When you're confident it works, run with --send to POST detected
         falls to your VitalBand backend at /api/fall (same endpoint
         scan_simulator.py already uses -- no backend changes needed).

Usage:
    python mediapipe_fall.py                       # just watch keypoints + fall flag locally
    python mediapipe_fall.py --send --patient P001  # also POST falls to backend

Press 'q' in the video window to quit.

Requirements:
    pip install -r requirements-deepface.txt
"""

import argparse
import time
from collections import deque

import cv2
import mediapipe as mp

try:
    import requests
except ImportError:
    requests = None
   

BACKEND_FALL_URL = "http://localhost:5000/api/fall"
#backslash = photon2028 


# ---------------------------------------------------------------------------
# Fall-rule tuning constants -- adjust these after testing on your own webcam
# ---------------------------------------------------------------------------
DROP_SPEED_THRESHOLD = 0.06     # normalized-y change per frame considered "fast drop"
HORIZONTAL_RATIO_THRESHOLD = 0.55  # body width/height ratio considered "lying down"
STILLNESS_SECONDS = 2.0         # how long the body must stay still after a drop
STILLNESS_MOVEMENT_THRESHOLD = 0.02  # max movement per frame counted as "still"
HISTORY_LEN = 10                # frames kept for the vertical-position trend


class FallDetector:
    """
    Plain rule-based logic on top of MediaPipe keypoints -- NOT a trained
    model. Sequence it looks for:
        1. Hip/shoulder center drops quickly (fast downward movement)
        2. Body bounding box becomes wider than it is tall (horizontal posture)
        3. Little to no movement for STILLNESS_SECONDS afterward
    Any single frame alone never triggers a fall -- this avoids false
    positives from someone just bending down quickly.
    """

    def __init__(self):
        self.y_history = deque(maxlen=HISTORY_LEN)
        self.state = "NORMAL"          # NORMAL -> DROP_DETECTED -> FALL_CONFIRMED
        self.drop_time = None
        self.last_center = None

    def update(self, landmarks, image_h, image_w):
        # Use mid-hip as the body center (stable landmark for vertical tracking)
        left_hip = landmarks[mp.solutions.pose.PoseLandmark.LEFT_HIP]
        right_hip = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_HIP]
        left_shoulder = landmarks[mp.solutions.pose.PoseLandmark.LEFT_SHOULDER]
        right_shoulder = landmarks[mp.solutions.pose.PoseLandmark.RIGHT_SHOULDER]

        center_y = (left_hip.y + right_hip.y) / 2
        self.y_history.append(center_y)

        # bounding box of all landmarks -> width/height ratio
        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        horizontal_ratio = width / height if height > 0 else 0

        movement = 0
        if self.last_center is not None:
            movement = abs(center_y - self.last_center)
        self.last_center = center_y

        # --- state machine ---
        if self.state == "NORMAL":
            if len(self.y_history) >= 2:
                drop_speed = self.y_history[-1] - self.y_history[0]
                if drop_speed > DROP_SPEED_THRESHOLD and horizontal_ratio > HORIZONTAL_RATIO_THRESHOLD:
                    self.state = "DROP_DETECTED"
                    self.drop_time = time.time()

        elif self.state == "DROP_DETECTED":
            if movement > STILLNESS_MOVEMENT_THRESHOLD:
                # person moved a lot right after the drop -> probably not a fall
                # (e.g. sitting down normally), reset
                self.state = "NORMAL"
            elif time.time() - self.drop_time >= STILLNESS_SECONDS:
                self.state = "FALL_CONFIRMED"

        elif self.state == "FALL_CONFIRMED":
            # stays confirmed until person gets up (moves a lot again)
            if movement > STILLNESS_MOVEMENT_THRESHOLD * 3:
                self.state = "NORMAL"
                self.y_history.clear()

        return {
            "state": self.state,
            "horizontal_ratio": round(horizontal_ratio, 2),
            "movement": round(movement, 3),
        }


def run(send_to_backend, patient_id, camera_index):
    mp_pose = mp.solutions.pose
    mp_drawing = mp.solutions.drawing_utils

    detector = FallDetector()
    already_alerted = False

    # DirectShow is more reliable for local Windows webcams. Fall back to the
    # default backend for virtual cameras and non-Windows environments.
    cap = cv2.VideoCapture(camera_index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        cap.release()
        cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Could not open camera index {camera_index}. Try --camera 1.")
        return

    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    print(f"Camera opened: {int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))}x"
          f"{int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))}")

    with mp_pose.Pose(
        model_complexity=1,
        min_detection_confidence=0.35,
        min_tracking_confidence=0.35,
    ) as pose:
        print("MediaPipe fall detector running. Press 'q' to quit.\n")
        while cap.isOpened():
            ok, frame = cap.read()
            if not ok:
                print("Camera frame read failed; retrying...")
                cv2.waitKey(30)
                break

            frame = cv2.flip(frame, 1)
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            results = pose.process(rgb)

            status_text = "NO PERSON DETECTED"
            color = (200, 200, 200)

            if results.pose_landmarks:
                mp_drawing.draw_landmarks(
                    frame, results.pose_landmarks, mp_pose.POSE_CONNECTIONS
                )
                info = detector.update(
                    results.pose_landmarks.landmark, frame.shape[0], frame.shape[1]
                )
                status_text = info["state"]

                if info["state"] == "FALL_CONFIRMED":
                    color = (0, 0, 255)
                    if not already_alerted:
                        print(">>> FALL CONFIRMED <<<")
                        if send_to_backend and requests is not None:
                            try:
                                r = requests.post(
                                    BACKEND_FALL_URL,
                                    json={
                                        "device_id": "scan_01",
                                        "patient_id": patient_id,
                                        "fall_detected": True,
                                        "distress_detected": False,
                                        "confidence": 0.9,
                                    },
                                    timeout=3,
                                )
                                print(f"Posted to backend -> {r.status_code}")
                            except Exception as e:
                                print(f"Could not reach backend: {e}")
                        already_alerted = True
                elif info["state"] == "DROP_DETECTED":
                    color = (0, 165, 255)
                    already_alerted = False
                else:
                    color = (0, 200, 0)
                    already_alerted = False

                status_text = f"{status_text} | 33 LANDMARKS"

            cv2.putText(frame, status_text, (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)
            cv2.imshow("VitalBand - MediaPipe Fall Detection", frame)

            if cv2.waitKey(5) & 0xFF == ord("q"):
                break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true", help="POST falls to backend /api/fall")
    parser.add_argument("--patient", default="P001")
    parser.add_argument("--camera", type=int, default=0, help="webcam index, try 1 if 0 fails")
    args = parser.parse_args()
    run(args.send, args.patient, args.camera)
