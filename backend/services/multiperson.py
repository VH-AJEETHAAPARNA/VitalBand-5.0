"""
Multi-person pose for the live dashboard feed.

Why this exists: the dashboard stream used mp.solutions.pose, which tracks
exactly ONE person. That quietly contradicted the core pitch — a Scan Machine
that "watches a waiting room" was in fact watching whoever it locked onto
first. This module upgrades the live feed to MediaPipe Tasks PoseLandmarker
with num_poses > 1, and runs an independent fall state machine per person.

Fail-safe by design: if the .task model is missing or the Tasks API is
unavailable, is_available() returns False and the caller keeps the original
single-person path. A missing model degrades coverage, it never blanks the
feed — and the SOS button is untouched either way.
"""

import logging
import math
import time
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("vitalband.multiperson")

MODEL_PATH = Path(__file__).resolve().parents[2] / "vision" / "pose_landmarker_lite.task"
MAX_PEOPLE = 4

# Matching radius in normalised frame units. Two people standing closer than
# this may swap ids — acceptable for triage, and stated honestly rather than
# dressed up as re-identification.
MATCH_RADIUS = 0.22
TRACK_TTL_S = 4.0


class PersonTrack:
    """One tracked person: position history plus their own fall state machine."""

    def __init__(self, track_id: int, detector):
        self.id = track_id
        self.detector = detector
        self.last_seen = time.time()
        self.center = (0.5, 0.5)
        self.last_landmarks = None
        self.state = "NORMAL"
        self.tilt = 0.0
        self.alerted_fall = False
        self.alerted_distress = False

    def update(self, landmarks, center):
        self.last_seen = time.time()
        self.center = center
        self.last_landmarks = landmarks
        info = self.detector.update(landmarks)
        self.state = info["state"]
        self.tilt = info["head_tilt_deg"]
        if self.state == "NORMAL":
            self.alerted_fall = False
            self.alerted_distress = False
        return info


def _center_of(landmarks) -> tuple:
    """Hip midpoint when visible, else the mean of all points."""
    try:
        lh, rh = landmarks[23], landmarks[24]
        return ((lh.x + rh.x) / 2.0, (lh.y + rh.y) / 2.0)
    except Exception:
        n = max(1, len(landmarks))
        return (sum(p.x for p in landmarks) / n, sum(p.y for p in landmarks) / n)


class MultiPersonPose:
    def __init__(self, detector_factory, max_people: int = MAX_PEOPLE):
        self._factory = detector_factory
        self.max_people = max_people
        self.landmarker = None
        self.tracks: Dict[int, PersonTrack] = {}
        self._next_id = 1
        self._mp = None

    # ── lifecycle ───────────────────────────────────────────────────────────

    def start(self) -> bool:
        if not MODEL_PATH.exists():
            logger.warning(
                "Multi-person model missing at %s — live feed stays single-person.",
                MODEL_PATH,
            )
            return False
        try:
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision

            self._mp = mp
            opts = vision.PoseLandmarkerOptions(
                base_options=mp_python.BaseOptions(model_asset_path=str(MODEL_PATH)),
                running_mode=vision.RunningMode.VIDEO,
                num_poses=self.max_people,
                min_pose_detection_confidence=0.5,
                min_pose_presence_confidence=0.5,
                min_tracking_confidence=0.5,
            )
            self.landmarker = vision.PoseLandmarker.create_from_options(opts)
            logger.info("Multi-person pose active (up to %d people).", self.max_people)
            return True
        except Exception as e:
            logger.warning("Could not start multi-person pose (%s) — staying single-person.", e)
            return False

    def is_available(self) -> bool:
        return self.landmarker is not None

    def close(self):
        try:
            if self.landmarker:
                self.landmarker.close()
        except Exception:
            pass
        self.landmarker = None

    # ── per-frame ───────────────────────────────────────────────────────────

    def process(self, rgb_frame, timestamp_ms: int) -> List[PersonTrack]:
        """Detect everyone in the frame and update their tracks."""
        if not self.landmarker:
            return []

        mp = self._mp
        image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
        try:
            result = self.landmarker.detect_for_video(image, timestamp_ms)
        except Exception as e:
            logger.debug("multi-person inference failed: %s", e)
            return []

        detections = []
        for lms in (result.pose_landmarks or []):
            detections.append((lms, _center_of(lms)))

        self._assign(detections)
        self._expire()
        return [t for t in self.tracks.values() if time.time() - t.last_seen < 0.6]

    def _assign(self, detections):
        """Greedy nearest-neighbour matching of detections to existing tracks."""
        unmatched = list(self.tracks.values())

        for lms, center in detections:
            best, best_d = None, MATCH_RADIUS
            for t in unmatched:
                d = math.dist(center, t.center)
                if d < best_d:
                    best, best_d = t, d

            if best is None:
                if len(self.tracks) >= self.max_people:
                    continue
                best = PersonTrack(self._next_id, self._factory())
                self.tracks[self._next_id] = best
                self._next_id += 1
            else:
                unmatched.remove(best)

            best.update(lms, center)

    def _expire(self):
        now = time.time()
        for tid in [t for t, tr in self.tracks.items() if now - tr.last_seen > TRACK_TTL_S]:
            del self.tracks[tid]

    def summary(self) -> Dict:
        return {
            "available": self.is_available(),
            "max_people": self.max_people,
            "tracked": len(self.tracks),
        }
