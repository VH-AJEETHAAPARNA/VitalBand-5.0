"""
Multi-Person Facial Distress Detection (Shared-space Scan Machine)
=======================================================================
Use this INSTEAD of deepface_distress.py if one Scan Machine watches a
shared space (waiting room, ward) with multiple people in frame at once.

How it differs from the single-person version:
  - DeepFace.extract_faces() finds ALL faces in the frame first
  - Each face is analyzed for emotion separately
  - Each face is tracked frame-to-frame by position so a person needs
    several consecutive distressed readings before an alert fires --
    EVERY person gets this "don't trust one frame" protection independently.

SAME HONEST LIMITATION as the multi-person fall script: without RFID or
a fixed seat/bed mapping, this can only say "the person in position 3
looks distressed," not which real patient that is. Labeled as
"Person 1", "Person 2", etc. -- positional labels, not real identity.

Usage:
    python deepface_distress_multiperson.py                        # watch only
    python deepface_distress_multiperson.py --send --max-faces 6    # also POST alerts

Press 'q' to quit.
"""

import argparse
import threading
import time

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

ANALYZE_EVERY_N_FRAMES = 20
DISTRESS_EMOTIONS = {"fear", "sad", "angry"}
DISTRESS_SCORE_THRESHOLD = 70.0
NEUTRAL_MARGIN_REQUIRED = 15.0
CONSECUTIVE_HITS_REQUIRED = 5
MATCH_DISTANCE_PIXELS = 80

class FaceTrack:
    def __init__(self, track_id):
        self.track_id = track_id
        self.hit_streak = 0
        self.confirmed = False
        self.last_center = None
        self.last_seen = time.time()

    def update(self, emotions):
        top_emotion = max(emotions, key=emotions.get)
        top_score = emotions[top_emotion]
        neutral_score = emotions.get("neutral", 0)

        is_distress = (
            top_emotion in DISTRESS_EMOTIONS
            and top_score >= DISTRESS_SCORE_THRESHOLD
            and (top_score - neutral_score) >= NEUTRAL_MARGIN_REQUIRED
        )

        self.hit_streak = self.hit_streak + 1 if is_distress else 0
        self.confirmed = self.hit_streak >= CONSECUTIVE_HITS_REQUIRED
        self.last_seen = time.time()

        return top_emotion, round(float(top_score), 1), self.confirmed

class MultiFaceTracker:
    def __init__(self):
        self.tracks = {}
        self.next_id = 1

    def update(self, face_detections, frame_analyses):
        results = []
        used_ids = set()

        for face, emotions in zip(face_detections, frame_analyses):
            area = face["facial_area"]
            cx = area["x"] + area["w"] / 2
            cy = area["y"] + area["h"] / 2

            best_id, best_dist = None, MATCH_DISTANCE_PIXELS
            for tid, track in self.tracks.items():
                if tid in used_ids or track.last_center is None:
                    continue
                dist = ((cx - track.last_center[0]) ** 2 + (cy - track.last_center[1]) ** 2) ** 0.5
                if dist < best_dist:
                    best_id, best_dist = tid, dist

            if best_id is None:
                best_id = self.next_id
                self.next_id += 1
                self.tracks[best_id] = FaceTrack(best_id)

            used_ids.add(best_id)
            track = self.tracks[best_id]
            track.last_center = (cx, cy)
            top_emotion, top_score, confirmed = track.update(emotions)

            results.append({
                "id": best_id,
                "box": (area["x"], area["y"], area["w"], area["h"]),
                "emotion": top_emotion,
                "score": top_score,
                "confirmed": confirmed,
            })

        stale = [tid for tid, t in self.tracks.items() if time.time() - t.last_seen > 5]
        for tid in stale:
            del self.tracks[tid]

        return results

def run(send_to_backend, max_faces, camera_index):
    if DeepFace is None:
        print("DeepFace is not installed. Run: pip install deepface tf-keras")
        return

    tracker = MultiFaceTracker()
    already_alerted = set()
    frame_count = 0
    last_results = []

    cap = cv2.VideoCapture(camera_index)
    if not cap.isOpened():
        print(f"Could not open camera index {camera_index}. Try --camera 1.")
        return

    print(f"Multi-person distress detector running (up to {max_faces} faces). "
          f"Press 'q' to quit.")
    print("(First analysis may take a few seconds while models load.)\n")

    analysis_lock = threading.Lock()
    analysis_in_progress = {"busy": False}

    def analyze_frame(frame_copy):
        nonlocal last_results
        try:
            detections = DeepFace.extract_faces(
                frame_copy, enforce_detection=False, detector_backend="opencv"
            )
            detections = [f for f in detections if f.get("confidence", 0) > 0.5][:max_faces]

            faces, analyses = [], []
            for detection in detections:
                area = detection["facial_area"]
                x, y, w, h = area["x"], area["y"], area["w"], area["h"]
                x = max(0, x)
                y = max(0, y)
                crop = frame_copy[y:y + h, x:x + w]
                if crop.size == 0:
                    continue

                result = DeepFace.analyze(
                    crop, actions=["emotion"], enforce_detection=False, silent=True
                )
                emotions = result[0]["emotion"] if isinstance(result, list) else result["emotion"]
                faces.append(detection)
                analyses.append(emotions)

            with analysis_lock:
                last_results = tracker.update(faces, analyses)
                results_snapshot = list(last_results)

            for result in results_snapshot:
                if result["confirmed"] and result["id"] not in already_alerted:
                    print(f">>> DISTRESS CONFIRMED -- Person {result['id']} "
                          f"({result['emotion']} {result['score']}%) <<<")
                    if send_to_backend and requests is not None:
                        try:
                            response = requests.post(
                                BACKEND_FALL_URL,
                                json={
                                    "device_id": "scan_01",
                                    "patient_id": f"unidentified_person_{result['id']}",
                                    "fall_detected": False,
                                    "distress_detected": True,
                                    "confidence": round(result["score"] / 100, 2),
                                },
                                timeout=3,
                            )
                            print(f"Posted to backend -> {response.status_code}")
                        except Exception as error:
                            print(f"Could not reach backend: {error}")
                    already_alerted.add(result["id"])
                elif not result["confirmed"]:
                    already_alerted.discard(result["id"])
        except Exception as error:
            print(f"Analysis error this cycle: {error}")
        finally:
            analysis_in_progress["busy"] = False

    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break

        frame = cv2.flip(frame, 1)
        frame_count += 1

        if frame_count % ANALYZE_EVERY_N_FRAMES == 0 and not analysis_in_progress["busy"]:
            analysis_in_progress["busy"] = True
            threading.Thread(target=analyze_frame, args=(frame.copy(),), daemon=True).start()

        with analysis_lock:
            results_snapshot = list(last_results)

        for r in results_snapshot:
            x, y, w, h = r["box"]
            color = (0, 0, 255) if r["confirmed"] else (0, 200, 0)
            label = "DISTRESS" if r["confirmed"] else f"{r['emotion']} {r['score']}%"
            cv2.rectangle(frame, (x, y), (x + w, y + h), color, 2)
            cv2.putText(frame, f"Person {r['id']}: {label}", (x, y - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

        cv2.putText(frame, f"Tracking {len(results_snapshot)} faces", (20, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 255, 255), 2)
        cv2.imshow("VitalBand - Multi-Person Distress Detection", frame)

        if cv2.waitKey(5) & 0xFF == ord("q"):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--max-faces", type=int, default=6)
    parser.add_argument("--camera", type=int, default=0)
    args = parser.parse_args()
    run(args.send, args.max_faces, args.camera)
