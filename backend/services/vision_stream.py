"""
VitalBand Multi-Modal AI Vision Pipeline (Face + MediaPipe Pose + Fall Engine + Dizziness/Collapse Engine)
=============================================================================================
Integrates:
1. OpenCV Face Cascade Detector (instant face tracking & bounding box)
2. MediaPipe Pose 33-Keypoint Skeleton (head-to-leg joint tracking)
3. Head Tilt & Dizziness / Fainting Onset Engine (eye/ear angle & continuous sway)
4. Posture Collapse State Machine (NORMAL -> DIZZY_WARNING -> DROP_DETECTED -> FALL_CONFIRMED)
5. Multi-Modal AI HUD Overlay (Real-time telemetry status banner)
"""

import time
import math
import logging
import asyncio
from collections import deque
import cv2

logger = logging.getLogger("vitalband.vision_stream")

# Fall & Collapse rule tuning constants
DROP_SPEED_THRESHOLD = 0.05
HORIZONTAL_RATIO_THRESHOLD = 0.50
STILLNESS_SECONDS = 2.0
STILLNESS_MOVEMENT_THRESHOLD = 0.02
HISTORY_LEN = 10


class FallDetectorEngine:
    """
    Multi-modal posture & fainting detection engine:
      1. Head Tilt & Dizziness Onset (Eye/Ear inclination angle)
      2. Vertical Posture Collapse (rapid downward Y movement)
      3. Post-impact stillness verification
    """
    def __init__(self):
        self.y_history = deque(maxlen=HISTORY_LEN)
        self.tilt_history = deque(maxlen=12)
        self.state = "NORMAL" # NORMAL -> DIZZY_WARNING -> DROP_DETECTED -> FALL_CONFIRMED
        self.drop_time = None
        self.last_center = None
        self.head_tilt_deg = 0.0

    def update(self, landmarks):
        # 1. Head Tilt Angle Calculation (Eye / Ear orientation)
        head_tilt_deg = 0.0
        if len(landmarks) > 5:
            # Left eye (2) and Right eye (5) or Left ear (7) and Right ear (8)
            left_p = landmarks[2]
            right_p = landmarks[5]
            if hasattr(left_p, 'x') and hasattr(right_p, 'x'):
                dx = right_p.x - left_p.x
                dy = right_p.y - left_p.y
                if abs(dx) > 0.001:
                    raw_deg = abs(math.degrees(math.atan2(dy, dx)))
                    head_tilt_deg = min(raw_deg, abs(180 - raw_deg))

        self.head_tilt_deg = round(head_tilt_deg, 1)
        self.tilt_history.append(head_tilt_deg)
        avg_tilt = sum(self.tilt_history) / len(self.tilt_history) if self.tilt_history else 0
        is_dizzy = avg_tilt > 18.0

        # 2. Body center: Try mid-hip first (23/24), fallback to mid-shoulder (11/12), then nose (0)
        center_y = None
        if len(landmarks) > 24:
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            if hasattr(left_hip, 'y') and hasattr(right_hip, 'y'):
                center_y = (left_hip.y + right_hip.y) / 2

        if center_y is None and len(landmarks) > 12:
            left_sh = landmarks[11]
            right_sh = landmarks[12]
            if hasattr(left_sh, 'y') and hasattr(right_sh, 'y'):
                center_y = (left_sh.y + right_sh.y) / 2

        if center_y is None and len(landmarks) > 0:
            center_y = landmarks[0].y

        if center_y is not None:
            self.y_history.append(center_y)

        # Bounding box aspect ratio (width vs height)
        xs = [lm.x for lm in landmarks if hasattr(lm, 'x')]
        ys = [lm.y for lm in landmarks if hasattr(lm, 'y')]
        width = (max(xs) - min(xs)) if xs else 0
        height = (max(ys) - min(ys)) if ys else 0
        horizontal_ratio = width / height if height > 0 else 0

        movement = 0
        if self.last_center is not None and center_y is not None:
            movement = abs(center_y - self.last_center)
        if center_y is not None:
            self.last_center = center_y

        # State Machine Transitions
        if self.state in ("NORMAL", "DIZZY_WARNING"):
            if len(self.y_history) >= 2:
                drop_speed = self.y_history[-1] - self.y_history[0]
                if drop_speed > DROP_SPEED_THRESHOLD and horizontal_ratio > HORIZONTAL_RATIO_THRESHOLD:
                    self.state = "DROP_DETECTED"
                    self.drop_time = time.time()
                elif is_dizzy:
                    self.state = "DIZZY_WARNING"
                else:
                    self.state = "NORMAL"

        elif self.state == "DROP_DETECTED":
            if movement > STILLNESS_MOVEMENT_THRESHOLD:
                self.state = "NORMAL"
            elif time.time() - self.drop_time >= STILLNESS_SECONDS:
                self.state = "FALL_CONFIRMED"

        elif self.state == "FALL_CONFIRMED":
            if movement > STILLNESS_MOVEMENT_THRESHOLD * 3:
                self.state = "NORMAL"
                self.y_history.clear()

        return {
            "state": self.state,
            "head_tilt_deg": self.head_tilt_deg,
            "avg_tilt": round(avg_tilt, 1),
            "is_dizzy": is_dizzy,
            "horizontal_ratio": round(horizontal_ratio, 2),
            "movement": round(movement, 3),
        }


def draw_face_reticle(frame, faces):
    """Draw corner reticles and bounding boxes for detected faces."""
    face_count = len(faces)
    for (x, y, w, h) in faces:
        # Drawing bounding rectangle
        cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 230, 0), 2)
        # Corner accents
        length = int(min(w, h) * 0.2)
        cv2.line(frame, (x, y), (x + length, y), (0, 255, 255), 3)
        cv2.line(frame, (x, y), (x, y + length), (0, 255, 255), 3)
        cv2.line(frame, (x + w, y), (x + w - length, y), (0, 255, 255), 3)
        cv2.line(frame, (x + w, y), (x + w, y + length), (0, 255, 255), 3)
        # Label
        cv2.rectangle(frame, (x, y - 22), (x + 160, y), (255, 230, 0), -1)
        cv2.putText(frame, "SUBJECT FACE OK", (x + 6, y - 6),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.45, (15, 23, 42), 1, cv2.LINE_AA)
    return face_count


def _label_person(frame, track):
    """Draw the person id and state above a tracked person."""
    h, w = frame.shape[:2]
    cx = int(track.center[0] * w)
    cy = int(track.center[1] * h)
    colour = {
        "NORMAL": (0, 255, 0),
        "DIZZY_WARNING": (0, 215, 255),
        "DROP_DETECTED": (0, 165, 255),
        "FALL_CONFIRMED": (0, 0, 255),
    }.get(track.state, (0, 255, 0))

    label = f"P{track.id:03d} · {track.state}"
    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1)
    x = max(5, min(cx - tw // 2, w - tw - 10))
    y = max(28, cy - 90)

    cv2.rectangle(frame, (x - 6, y - th - 8), (x + tw + 6, y + 6), (15, 23, 42), -1)
    cv2.rectangle(frame, (x - 6, y - th - 8), (x + tw + 6, y + 6), colour, 1)
    cv2.putText(frame, label, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 0.45, colour, 1, cv2.LINE_AA)


def draw_skeleton(frame, landmarks, mp_pose, state, tilt_deg=0.0):
    """Draw head-to-leg 33 body keypoints skeleton on frame cleanly with state color."""
    h, w, _ = frame.shape
    color = (0, 255, 0) if state == "NORMAL" else (0, 215, 255) if state == "DIZZY_WARNING" else (0, 165, 255) if state == "DROP_DETECTED" else (0, 0, 255)

    points = {}
    visible_count = 0
    for idx, lm in enumerate(landmarks):
        if -0.2 <= lm.x <= 1.2 and -0.2 <= lm.y <= 1.2:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cx = max(0, min(w - 1, cx))
            cy = max(0, min(h - 1, cy))
            points[idx] = (cx, cy)
            visible_count += 1

            # Draw keypoint circle
            cv2.circle(frame, (cx, cy), 4, color, -1)
            cv2.circle(frame, (cx, cy), 5, (255, 255, 255), 1)

    # Draw body connection lines
    connections = mp_pose.POSE_CONNECTIONS
    for conn in connections:
        # POSE_CONNECTIONS holds plain ints in mediapipe 0.10.x but enum members
        # in some other versions. Accept either, rather than assuming .value and
        # crashing the whole stream with "'int' object has no attribute 'value'".
        p1 = getattr(conn[0], "value", conn[0])
        p2 = getattr(conn[1], "value", conn[1])
        if p1 in points and p2 in points:
            cv2.line(frame, points[p1], points[p2], color, 2, cv2.LINE_AA)

    # Draw Head Tilt Line indicator between eyes (points 2 & 5)
    if 2 in points and 5 in points:
        cv2.line(frame, points[2], points[5], (0, 255, 255), 3, cv2.LINE_AA)

    return visible_count


async def generate_mediapipe_mjpeg_stream(cap, trigger_alert_cb):
    """Yields high-speed MJPEG stream with Face Cascade + MediaPipe Pose + Fall/Dizziness Engine."""
    import numpy as np

    # Load Face Cascade.
    #
    # OpenCV 5.x NO LONGER SHIPS the haarcascade XML files: cv2.data.haarcascades
    # points at a directory that exists but is empty. Critically, constructing a
    # CascadeClassifier with a missing file does NOT raise — it returns an EMPTY
    # classifier that only fails later, deep in the frame loop, with
    # "detectMultiScale (-215:Assertion failed) !empty()". That killed the whole
    # MJPEG stream, so the dashboard showed no video at all even with a working
    # camera. Hence the explicit .empty() check: try/except cannot catch this.
    face_cascade = None
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        candidate = cv2.CascadeClassifier(cascade_path)
        if candidate.empty():
            logger.warning(
                "Face cascade XML not found at %s (OpenCV %s ships no cascades). "
                "Continuing with MediaPipe pose only — fall detection is unaffected.",
                cascade_path, cv2.__version__,
            )
        else:
            face_cascade = candidate
    except Exception as e:
        logger.warning(f"Face cascade unavailable: {e}")

    # Multi-person engine. When its model is present the live feed tracks
    # several people at once, which is what the Scan Machine pitch actually
    # claims. When it is absent we silently keep the single-person path below,
    # so a missing model costs coverage but never blanks the feed.
    from backend.services.multiperson import MultiPersonPose
    multi = MultiPersonPose(detector_factory=lambda: FallDetectorEngine())
    multi_on = multi.start()

    # Load MediaPipe Pose (single-person fallback, always initialised)
    try:
        import mediapipe as mp
        mp_pose = mp.solutions.pose
        pose = mp_pose.Pose(
            model_complexity=0,
            min_detection_confidence=0.2,
            min_tracking_confidence=0.2
        )
        detector = FallDetectorEngine()
        already_alerted = False
        dizzy_alerted = False
    except Exception as e:
        logger.warning(f"MediaPipe unavailable: {e}")
        mp = None

    last_landmarks = None
    last_state = "NORMAL"
    last_tilt = 0.0
    missed_frames = 0
    faces = []

    try:
        while True:
            ok, frame = await asyncio.to_thread(cap.read)
            if not ok or frame is None:
                await asyncio.sleep(0.01)
                continue

            frame = cv2.flip(frame, 1)
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

            # 1. Face Cascade Detection (optional enhancement, never fatal)
            if face_cascade is not None:
                try:
                    faces = face_cascade.detectMultiScale(
                        gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
                    )
                except cv2.error as e:
                    logger.warning("Face cascade failed, disabling it: %s", e)
                    face_cascade = None
                    faces = []
            face_count = draw_face_reticle(frame, faces)

            # 2. Pose detection — multi-person when available
            vis_count = 0
            people_count = 0

            if multi_on:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                tracks = multi.process(rgb, int(time.time() * 1000))
                people_count = len(tracks)

                # Draw every tracked person and fire per-person alerts.
                worst_rank = -1
                for tr in tracks:
                    rank = {"NORMAL": 0, "DIZZY_WARNING": 1,
                            "DROP_DETECTED": 2, "FALL_CONFIRMED": 3}.get(tr.state, 0)
                    if rank > worst_rank:
                        worst_rank = rank
                        last_state = tr.state
                        last_tilt = tr.tilt

                    if tr.last_landmarks is not None:
                        vis_count = max(
                            vis_count,
                            draw_skeleton(frame, tr.last_landmarks, mp_pose,
                                          tr.state, tr.tilt),
                        )
                        _label_person(frame, tr)

                    # Each person carries their own alert latch, so one
                    # person's fall cannot mask another's.
                    if tr.state == "FALL_CONFIRMED" and not tr.alerted_fall:
                        tr.alerted_fall = True
                        if trigger_alert_cb:
                            asyncio.create_task(trigger_alert_cb(f"P{tr.id:03d}", "FALL"))
                    elif tr.state == "DIZZY_WARNING" and not tr.alerted_distress:
                        tr.alerted_distress = True
                        if trigger_alert_cb:
                            asyncio.create_task(trigger_alert_cb(f"P{tr.id:03d}", "DISTRESS"))

                if worst_rank < 0:
                    last_state = "NORMAL"

            elif mp is not None:
                rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                results = pose.process(rgb)

                if results.pose_landmarks:
                    last_landmarks = results.pose_landmarks.landmark
                    missed_frames = 0
                    info = detector.update(last_landmarks)
                    last_state = info["state"]
                    last_tilt = info["head_tilt_deg"]
                else:
                    missed_frames += 1
                    if missed_frames > 10:
                        last_landmarks = None

                if last_landmarks is not None:
                    vis_count = draw_skeleton(frame, last_landmarks, mp_pose, last_state, last_tilt)

                    if last_state == "FALL_CONFIRMED" and not already_alerted:
                        already_alerted = True
                        if trigger_alert_cb:
                            asyncio.create_task(trigger_alert_cb("P001", "FALL"))
                    elif last_state == "DIZZY_WARNING" and not dizzy_alerted:
                        dizzy_alerted = True
                        if trigger_alert_cb:
                            asyncio.create_task(trigger_alert_cb("P001", "DISTRESS"))
                    elif last_state == "NORMAL":
                        already_alerted = False
                        dizzy_alerted = False

            # 3. Multi-Modal HUD Banner Overlay
            color = (0, 255, 0) if last_state == "NORMAL" else (0, 215, 255) if last_state == "DIZZY_WARNING" else (0, 165, 255) if last_state == "DROP_DETECTED" else (0, 0, 255)
            status_label = "STABLE" if last_state == "NORMAL" else "DIZZINESS / FAINTING RISK" if last_state == "DIZZY_WARNING" else "POSTURE DROP" if last_state == "DROP_DETECTED" else "COLLAPSE CONFIRMED"

            cv2.rectangle(frame, (10, 10), (410, 105), (15, 23, 42), -1)
            cv2.rectangle(frame, (10, 10), (410, 105), color, 1)

            cv2.putText(frame, "● MULTI-MODAL AI VISION SCANNER", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (56, 189, 248), 2, cv2.LINE_AA)
            mode_txt = f"TRACKING {people_count} PERSON(S)" if multi_on else "SINGLE-PERSON MODE"
            cv2.putText(frame, f"{mode_txt}  |  HEAD TILT: {last_tilt}°", (20, 52), cv2.FONT_HERSHEY_SIMPLEX, 0.43, (226, 232, 240), 1, cv2.LINE_AA)
            cv2.putText(frame, f"POSE: {status_label} ({vis_count}/33 KEYPOINTS)", (20, 74), cv2.FONT_HERSHEY_SIMPLEX, 0.43, color, 1, cv2.LINE_AA)
            cv2.putText(frame, f"STATE ENGINE: {last_state}", (20, 94), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (148, 163, 184), 1, cv2.LINE_AA)

            # Fast JPEG Compression
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
            yield (b"--frame\r\n"
                   b"Content-Type: image/jpeg\r\n\r\n" + buf.tobytes() + b"\r\n")
            await asyncio.sleep(0.01)

    except asyncio.CancelledError:
        logger.info("Multi-modal video stream disconnected")
    except Exception as e:
        logger.error(f"Multi-modal vision stream error: {e}")

