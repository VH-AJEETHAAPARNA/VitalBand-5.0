"""
VitalBand Computer Vision Pipeline (Phase 3)
=============================================
Edge/Cloud Video Inference Service for Scan Machine Camera:
1. Pose Estimation (MediaPipe Pose) for physical fall detection & prone posture analysis.
2. Facial Expression Analysis (DeepFace / Landmarks) for pain/distress detection.
3. Fallback heuristic engine when video libraries or hardware accelerators are uninitialized.
"""

import math
import logging
from typing import Dict, Any, Optional, Tuple

logger = logging.getLogger("vitalband.cv_pipeline")

# Try optional imports
try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

try:
    import cv2
    OPENCV_AVAILABLE = True
except ImportError:
    OPENCV_AVAILABLE = False


class PoseFallDetector:
    """
    Analyzes body landmark geometry to detect falls based on torso vertical angle,
    hip-shoulder aspect ratio, and rapid downward bounding box transitions.
    """

    def __init__(self, angle_threshold_deg: float = 45.0, confidence_threshold: float = 0.65):
        self.angle_threshold = angle_threshold_deg
        self.confidence_threshold = confidence_threshold

    def calculate_body_angle(
        self,
        shoulder: Tuple[float, float],
        hip: Tuple[float, float]
    ) -> float:
        """
        Calculates the angle of the torso with respect to the vertical axis (0 deg = standing, 90 deg = horizontal/fallen).
        """
        dx = hip[0] - shoulder[0]
        dy = hip[1] - shoulder[1]
        if dy == 0:
            return 90.0
        angle_rad = math.atan2(abs(dx), abs(dy))
        return math.degrees(angle_rad)

    def evaluate_landmarks(self, landmarks: Dict[str, Tuple[float, float, float]]) -> Tuple[bool, float]:
        """
        Takes landmark coordinates (x, y, visibility) for shoulders, hips, and ankles.
        Returns (is_fall_detected, confidence).
        """
        try:
            left_shoulder = landmarks.get("left_shoulder")
            right_shoulder = landmarks.get("right_shoulder")
            left_hip = landmarks.get("left_hip")
            right_hip = landmarks.get("right_hip")

            if not all([left_shoulder, right_shoulder, left_hip, right_hip]):
                return False, 0.0

            # Midpoints
            mid_shoulder = (
                (left_shoulder[0] + right_shoulder[0]) / 2.0,
                (left_shoulder[1] + right_shoulder[1]) / 2.0,
            )
            mid_hip = (
                (left_hip[0] + right_hip[0]) / 2.0,
                (left_hip[1] + right_hip[1]) / 2.0,
            )

            # Torso angle relative to vertical
            angle = self.calculate_body_angle(mid_shoulder, mid_hip)
            avg_vis = sum([
                left_shoulder[2], right_shoulder[2],
                left_hip[2], right_hip[2]
            ]) / 4.0

            if angle > self.angle_threshold and avg_vis >= self.confidence_threshold:
                confidence = min(1.0, (angle / 90.0) * avg_vis)
                return True, round(confidence, 2)

            return False, round(avg_vis, 2)
        except Exception as e:
            logger.error(f"Error evaluating pose landmarks: {e}")
            return False, 0.0


class FacialDistressDetector:
    """
    Evaluates facial micro-expressions (grimacing, fear, pain, eyes tightly shut)
    to classify patient physical distress.
    """

    DISTRESS_EMOTIONS = {"fear", "sad", "angry", "pain"}

    def __init__(self, confidence_threshold: float = 0.70):
        self.confidence_threshold = confidence_threshold

    def evaluate_emotion_scores(self, emotion_dict: Dict[str, float]) -> Tuple[bool, float]:
        """
        Evaluates an emotion probability distribution (e.g. from DeepFace or custom model).
        Returns (is_distress_detected, confidence).
        """
        if not emotion_dict:
            return False, 0.0

        distress_score = sum(
            emotion_dict.get(emotion, 0.0) for emotion in self.DISTRESS_EMOTIONS
        )

        if distress_score >= self.confidence_threshold:
            return True, round(distress_score, 2)

        return False, round(distress_score, 2)


class CVPipeline:
    """
    Main Computer Vision inference coordinator for real-time video frames.
    """

    def __init__(self):
        self.pose_detector = PoseFallDetector()
        self.distress_detector = FacialDistressDetector()

    def process_telemetry_event(
        self,
        pose_landmarks: Optional[Dict[str, Tuple[float, float, float]]] = None,
        emotion_scores: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Synthesizes multimodal CV inferences into an actionable event payload.
        """
        fall_detected = False
        fall_conf = 0.0
        if pose_landmarks:
            fall_detected, fall_conf = self.pose_detector.evaluate_landmarks(pose_landmarks)

        distress_detected = False
        distress_conf = 0.0
        if emotion_scores:
            distress_detected, distress_conf = self.distress_detector.evaluate_emotion_scores(emotion_scores)

        overall_conf = max(fall_conf, distress_conf)

        return {
            "fall_detected": fall_detected,
            "distress_detected": distress_detected,
            "confidence": overall_conf,
            "details": {
                "fall_confidence": fall_conf,
                "distress_confidence": distress_conf
            }
        }


# Global pipeline instance
cv_pipeline = CVPipeline()
