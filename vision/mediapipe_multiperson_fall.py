"""
Multi-Person Fall Detection (Shared-space Scan Machine)
=============================================================
Use this INSTEAD of mediapipe_fall.py if one Scan Machine watches a
shared space (waiting room, ward) with multiple patients in frame at
once, rather than one camera per patient bed.

HONEST LIMITATION -- read this before you present it:
Without RFID or a fixed camera-to-bed mapping, this script can tell you
"the person in position 2 of the frame has fallen" but CANNOT tell you
which real patient_id that corresponds to. It labels people as
"Person 1", "Person 2", etc. based on their position in frame, tracked
frame-to-frame by nearest position -- not a real identity system. For a
real deployment, this is exactly why RFID-based check-in per bed/seat
matters: it's the missing link between "someone fell" and "who fell."

Setup (one-time model download -- needs internet):
    Download pose_landmarker_lite.task from:
    https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task
    Save it into this vision/ folder (same folder as this script).

    PowerShell:
        Invoke-WebRequest -Uri "https://storage.googleapis.com/mediapipe-models/pose_landmarker/pose_landmarker_lite/float16/1/pose_landmarker_lite.task" -OutFile "pose_landmarker_lite.task"

Usage:
    python mediapipe_multiperson_fall.py                       # watch only
    python mediapipe_multiperson_fall.py --send                # also POST falls to backend
    python mediapipe_multiperson_fall.py --max-people 6         # track up to 6 people

Press 'q' to quit.
"""

import argparse
import time
from pathlib import Path

import cv2
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision

try:
    import requests
except ImportError:
    requests = None

MODEL_PATH = Path(__file__).resolve().parent / "pose_landmarker_lite.task"
BACKEND_FALL_URL = "http://localhost:5000/api/fall"

DROP_SPEED_THRESHOLD = 0.06
HORIZONTAL_RATIO_THRESHOLD = 0.55
STILLNESS_SECONDS = 2.0
STILLNESS_MOVEMENT_THRESHOLD = 0.02
HISTORY_LEN = 10

MATCH_DISTANCE_THRESHOLD = 0.15


class PersonTrack:
    def __init__(self, track_id):
        self.track_id = track_id
        self.y_history = []
        self.state = "NORMAL"
        self.drop_time = None
        self.last_center = None   # last hip Y (used by the fall state machine)
        self.last_x = None        # last hip X (used only for cross-frame matching)
        self.last_seen = time.time()

    def update(self, landmarks):
        left_hip = landmarks[23]
        right_hip = landmarks[24]
        center_y = (left_hip.y + right_hip.y) / 2
        center_x = (left_hip.x + right_hip.x) / 2

        self.y_history.append(center_y)
        if len(self.y_history) > HISTORY_LEN:
            self.y_history.pop(0)

        xs = [lm.x for lm in landmarks]
        ys = [lm.y for lm in landmarks]
        width = max(xs) - min(xs)
        height = max(ys) - min(ys)
        horizontal_ratio = width / height if height > 0 else 0

        movement = 0
        if self.last_center is not None:
            movement = abs(center_y - self.last_center)
        self.last_center = center_y
        self.last_x = center_x
        self.last_seen = time.time()

        if self.state == "NORMAL":
            if len(self.y_history) >= 2:
                drop_speed = self.y_history[-1] - self.y_history[0]
                if drop_speed > DROP_SPEED_THRESHOLD and horizontal_ratio > HORIZONTAL_RATIO_THRESHOLD:
                    self.state = "DROP_DETECTED"
                    self.drop_time = time.time()
        elif self.state == "DROP_DETECTED":
            if movement > STILLNESS_MOVEMENT_THRESHOLD:
                self.state = "NORMAL"
            elif time.time() - self.drop_time >= STILLNESS_SECONDS:
                self.state = "FALL_CONFIRMED"
        elif self.state == "FALL_CONFIRMED":
            if movement > STILLNESS_MOVEMENT_THRESHOLD * 3:
                self.state = "NORMAL"
                self.y_history = []

        return center_x, center_y, self.state, horizontal_ratio


class MultiPersonTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def update(self, all_landmarks):
        results = []
        used_ids = set()

        for landmarks in all_landmarks:
            hip_x = (landmarks[23].x + landmarks[24].x) / 2
            hip_y = (landmarks[23].y + landmarks[24].y) / 2

            best_id, best_dist = None, MATCH_DISTANCE_THRESHOLD
            for tid, track in self.tracks.items():
                if tid in used_ids or track.last_x is None:
                    continue
                dist = ((hip_x - track.last_x) ** 2 + (hip_y - track.last_center) ** 2) ** 0.5
                if dist < best_dist:
                    best_id, best_dist = tid, dist

            if best_id is None:
                best_id = self.next_id
                self.next_id += 1
                self.tracks[best_id] = PersonTrack(best_id)

            used_ids.add(best_id)
            cx, cy, state, ratio = self.tracks[best_id].update(landmarks)
            results.append({"id": best_id, "x": cx, "y": cy, "state": state, "ratio": ratio})

        stale = [tid for tid, t in self.tracks.items() if time.time() - t.last_seen > 5]
        for tid in stale:
            del self.tracks[tid]

        return results


def run(send_to_backend, max_people, camera_index):
    if not MODEL_PATH.exists():
        print(f"Model file not found at {MODEL_PATH}")
        print("Download it first -- see the instructions at the top of this file.")
        return

    base_options = mp_python.BaseOptions(model_asset_path=str(MODEL_PATH))
    options = vision.PoseLandmarkerOptions(
        base_options=base_options,
        running_mode=vision.RunningMode.VIDEO,
        num_poses=max_people,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )
    landmarker = vision.PoseLandmarker.create_from_options(options)

    tracker = MultiPersonTracker()
    already_alerted = set()

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Could not open camera index {camera_index}. Try --camera 1.")
        return

    print(f"Multi-person fall detector running (tracking up to {max_people} people). "
          f"Press 'q' to quit.\n")

    frame_timestamp_ms = 0
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        frame_timestamp_ms += 33
        result = landmarker.detect_for_video(mp_image, frame_timestamp_ms)

        h, w = frame.shape[:2]
        if result.pose_landmarks:
            people = tracker.update(result.pose_landmarks)

            for person in people:
                px, py = int(person["x"] * w), int(person["y"] * h)
                state = person["state"]
                pid = person["id"]

                color = (0, 200, 0)
                if state == "DROP_DETECTED":
                    color = (0, 165, 255)
                    already_alerted.discard(pid)
                elif state == "FALL_CONFIRMED":
                    color = (0, 0, 255)
                    if pid not in already_alerted:
                        print(f">>> FALL CONFIRMED -- Person {pid} <<<")
                        if send_to_backend and requests is not None:
                            try:
                                response = requests.post(
                                    BACKEND_FALL_URL,
                                    json={
                                        "device_id": "scan_01",
                                        "patient_id": f"unidentified_person_{pid}",
                                        "fall_detected": True,
                                        "distress_detected": False,
                                        "confidence": 0.9,
                                    },
                                    timeout=3,
                                )
                                print(f"Posted to backend -> {response.status_code}")
                            except Exception as error:
                                print(f"Could not reach backend: {error}")
                        already_alerted.add(pid)
                else:
                    already_alerted.discard(pid)

                cv2.circle(frame, (px, py), 8, color, -1)
                cv2.putText(frame, f"Person {pid}: {state}", (px - 40, py - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

            cv2.putText(frame, f"Tracking {len(people)} people", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        else:
            cv2.putText(frame, "No people detected", (20, 30),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (200, 200, 200), 2)

        cv2.imshow("VitalBand - Multi-Person Fall Detection", frame)
        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--max-people", type=int, default=4)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    run(args.send, args.max_people, args.camera)
