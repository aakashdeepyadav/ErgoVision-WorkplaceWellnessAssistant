"""
ErgoVision — Head Tilt / Neck Angle Detector
Monitors head roll angle to detect sustained neck strain from tilting.
"""

import math
import time
import numpy as np
from collections import deque

import config


class HeadTiltDetector:
    """
    Detects sustained head tilt (roll) by measuring the angle between
    the left and right eye corners relative to the horizontal plane.

    Head tilt strains the cervical spine and is a common unconscious habit
    during focused screen work, especially when leaning on one hand.
    """

    # MediaPipe Face Mesh landmark indices for eye corners
    LEFT_EYE_OUTER = 33
    RIGHT_EYE_OUTER = 263
    # Additional landmarks for more robust angle estimation
    LEFT_EYE_INNER = 133
    RIGHT_EYE_INNER = 362

    def __init__(self):
        self.tilt_threshold_deg = config.HEAD_TILT_THRESHOLD_DEG
        self.sustained_seconds = config.HEAD_TILT_SUSTAINED_SECONDS
        self.smoothing_alpha = 0.3

        # State
        self._smoothed_angle = 0.0
        self._tilt_start = None
        self._is_tilted = False
        self._tilt_history = deque(maxlen=120)  # ~2 minutes of samples

        # Current readings
        self.current_angle = 0.0
        self.tilt_direction = "center"  # center, left, right
        self.tilt_duration = 0.0
        self.alert_active = False
        self.alert_reason = ""

    @staticmethod
    def _compute_roll_angle(face_landmarks, frame_w, frame_h):
        """
        Compute head roll angle from eye corner landmarks.

        Uses both inner and outer eye corners for robust estimation.
        Averages the angle from outer corners and inner corners.

        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions

        Returns:
            float: roll angle in degrees (positive = tilted right, negative = left)
        """
        def _pt(idx):
            lm = face_landmarks.landmark[idx]
            return np.array([lm.x * frame_w, lm.y * frame_h])

        # Outer eye corners
        left_outer = _pt(HeadTiltDetector.LEFT_EYE_OUTER)
        right_outer = _pt(HeadTiltDetector.RIGHT_EYE_OUTER)

        # Inner eye corners
        left_inner = _pt(HeadTiltDetector.LEFT_EYE_INNER)
        right_inner = _pt(HeadTiltDetector.RIGHT_EYE_INNER)

        # Compute angle from outer corners
        delta_outer = right_outer - left_outer
        angle_outer = math.degrees(math.atan2(delta_outer[1], delta_outer[0]))

        # Compute angle from inner corners
        delta_inner = right_inner - left_inner
        angle_inner = math.degrees(math.atan2(delta_inner[1], delta_inner[0]))

        # Average for robustness
        return (angle_outer + angle_inner) / 2.0

    def update(self, face_landmarks, frame_w, frame_h):
        """
        Process a new frame and update head tilt state.

        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions
        """
        if face_landmarks is None:
            self.alert_active = False
            self._tilt_start = None
            self._is_tilted = False
            self.tilt_duration = 0.0
            return

        raw_angle = self._compute_roll_angle(face_landmarks, frame_w, frame_h)

        # Exponential moving average smoothing
        self._smoothed_angle = (
            self.smoothing_alpha * raw_angle
            + (1 - self.smoothing_alpha) * self._smoothed_angle
        )
        self.current_angle = self._smoothed_angle

        # Track history for trend analysis
        self._tilt_history.append({
            "time": time.time(),
            "angle": self.current_angle,
        })

        # Determine tilt direction
        abs_angle = abs(self.current_angle)
        if self.current_angle > 3:
            self.tilt_direction = "right"
        elif self.current_angle < -3:
            self.tilt_direction = "left"
        else:
            self.tilt_direction = "center"

        now = time.time()

        # Sustained tilt detection
        if abs_angle > self.tilt_threshold_deg:
            if self._tilt_start is None:
                self._tilt_start = now
            self.tilt_duration = now - self._tilt_start
            self._is_tilted = True
        else:
            self._tilt_start = None
            self._is_tilted = False
            self.tilt_duration = 0.0

        # Alert logic
        self.alert_active = False
        self.alert_reason = ""

        if self._is_tilted and self.tilt_duration > self.sustained_seconds:
            self.alert_active = True
            self.alert_reason = (
                f"Head tilted {self.tilt_direction} at {abs_angle:.0f}° "
                f"for {self.tilt_duration:.0f}s"
            )

    def get_status(self):
        """
        Returns current detector status.

        Returns:
            dict with keys: angle, direction, duration, alert, reason
        """
        return {
            "angle": round(self.current_angle, 1),
            "direction": self.tilt_direction,
            "duration": round(self.tilt_duration, 1),
            "alert": self.alert_active,
            "reason": self.alert_reason,
        }
