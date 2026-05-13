"""
ErgoVision — Enhanced Posture Detector
Monitors slouching, shoulder asymmetry, and forward lean.
"""

import numpy as np
from collections import deque

import config


class PostureDetector:
    """
    Detects poor posture by comparing nose-to-shoulder vertical offset
    against a personal baseline established during calibration.

    Enhanced with:
    - Shoulder asymmetry detection (one shoulder higher than the other)
    - Forward lean detection using ear-to-shoulder horizontal offset
    - Multi-level status: GOOD, WARNING, ALERT with specific reasons

    Slouch offset = nose_y - mean(left_shoulder_y, right_shoulder_y)
    Alert fires when offset exceeds baseline by POSTURE_OFFSET_THRESHOLD pixels.
    """

    # MediaPipe Pose landmark indices
    NOSE_INDEX = 0
    LEFT_SHOULDER_INDEX = 11
    RIGHT_SHOULDER_INDEX = 12
    LEFT_EAR_INDEX = 7
    RIGHT_EAR_INDEX = 8

    def __init__(self):
        self.offset_threshold = config.POSTURE_OFFSET_THRESHOLD
        self.warning_threshold = config.POSTURE_WARNING_THRESHOLD

        # Calibration state
        self.baseline_offset = None
        self.baseline_shoulder_diff = None
        self.is_calibrated = False
        self._calibration_samples = []
        self._shoulder_diff_samples = []

        # Current readings
        self.current_offset = 0.0
        self.deviation = 0.0
        self.shoulder_asymmetry = 0.0
        self.forward_lean = 0.0
        self.status = "UNCALIBRATED"  # GOOD, WARNING, ALERT, UNCALIBRATED
        self.posture_issues = []  # List of specific issues detected
        self.alert_active = False
        self.alert_reason = ""

    def _compute_offset(self, pose_landmarks, frame_h):
        """
        Compute the vertical offset between nose and shoulders.

        Args:
            pose_landmarks: MediaPipe pose landmarks
            frame_h: frame height in pixels

        Returns:
            float: offset in pixels, or None if landmarks not detected
        """
        if pose_landmarks is None:
            return None

        nose = pose_landmarks.landmark[self.NOSE_INDEX]
        left_shoulder = pose_landmarks.landmark[self.LEFT_SHOULDER_INDEX]
        right_shoulder = pose_landmarks.landmark[self.RIGHT_SHOULDER_INDEX]

        # Check visibility — MediaPipe provides visibility scores
        if (nose.visibility < 0.5 or
            left_shoulder.visibility < 0.5 or
            right_shoulder.visibility < 0.5):
            return None

        nose_y = nose.y * frame_h
        shoulder_y = (left_shoulder.y * frame_h + right_shoulder.y * frame_h) / 2.0

        return nose_y - shoulder_y

    def _compute_shoulder_asymmetry(self, pose_landmarks, frame_h):
        """
        Compute shoulder level difference.

        Returns:
            float: absolute Y difference between shoulders in pixels, or None
        """
        if pose_landmarks is None:
            return None

        left = pose_landmarks.landmark[self.LEFT_SHOULDER_INDEX]
        right = pose_landmarks.landmark[self.RIGHT_SHOULDER_INDEX]

        if left.visibility < 0.5 or right.visibility < 0.5:
            return None

        return abs(left.y * frame_h - right.y * frame_h)

    def _compute_forward_lean(self, pose_landmarks, frame_h):
        """
        Estimate forward lean using ear-to-shoulder vertical relationship.

        When leaning forward, the ear moves further from the shoulder line.

        Returns:
            float: forward lean indicator (higher = more forward lean), or None
        """
        if pose_landmarks is None:
            return None

        try:
            left_ear = pose_landmarks.landmark[self.LEFT_EAR_INDEX]
            right_ear = pose_landmarks.landmark[self.RIGHT_EAR_INDEX]
            left_shoulder = pose_landmarks.landmark[self.LEFT_SHOULDER_INDEX]
            right_shoulder = pose_landmarks.landmark[self.RIGHT_SHOULDER_INDEX]

            if (left_ear.visibility < 0.3 or right_ear.visibility < 0.3 or
                left_shoulder.visibility < 0.5 or right_shoulder.visibility < 0.5):
                return None

            ear_y = (left_ear.y + right_ear.y) / 2.0 * frame_h
            shoulder_y = (left_shoulder.y + right_shoulder.y) / 2.0 * frame_h

            # The closer the ear is to the shoulder vertically,
            # the more forward the lean
            return shoulder_y - ear_y
        except (IndexError, AttributeError):
            return None

    def add_calibration_sample(self, pose_landmarks, frame_h):
        """
        Add a sample during the calibration phase.

        Args:
            pose_landmarks: MediaPipe pose landmarks
            frame_h: frame height

        Returns:
            int: number of samples collected so far
        """
        offset = self._compute_offset(pose_landmarks, frame_h)
        if offset is not None:
            self._calibration_samples.append(offset)

        shoulder_diff = self._compute_shoulder_asymmetry(pose_landmarks, frame_h)
        if shoulder_diff is not None:
            self._shoulder_diff_samples.append(shoulder_diff)

        return len(self._calibration_samples)

    def finish_calibration(self):
        """
        Complete calibration and set the personal baseline.

        Returns:
            bool: True if calibration succeeded (enough samples)
        """
        if len(self._calibration_samples) < 10:
            return False

        self.baseline_offset = np.mean(self._calibration_samples)

        if self._shoulder_diff_samples:
            self.baseline_shoulder_diff = np.mean(self._shoulder_diff_samples)
        else:
            self.baseline_shoulder_diff = 0.0

        self.is_calibrated = True
        self._calibration_samples = []
        self._shoulder_diff_samples = []
        return True

    def reset_calibration(self):
        """Reset calibration state."""
        self.baseline_offset = None
        self.baseline_shoulder_diff = None
        self.is_calibrated = False
        self._calibration_samples = []
        self._shoulder_diff_samples = []
        self.status = "UNCALIBRATED"

    def update(self, pose_landmarks, frame_h):
        """
        Process a new frame and update posture status.

        Args:
            pose_landmarks: MediaPipe pose landmarks
            frame_h: frame height in pixels
        """
        if not self.is_calibrated:
            self.status = "UNCALIBRATED"
            self.alert_active = False
            return

        offset = self._compute_offset(pose_landmarks, frame_h)
        if offset is None:
            return  # Keep last known state

        self.current_offset = offset
        self.deviation = abs(offset - self.baseline_offset)

        # Shoulder asymmetry
        shoulder_diff = self._compute_shoulder_asymmetry(pose_landmarks, frame_h)
        if shoulder_diff is not None:
            self.shoulder_asymmetry = shoulder_diff

        # Forward lean
        lean = self._compute_forward_lean(pose_landmarks, frame_h)
        if lean is not None:
            self.forward_lean = lean

        # Determine status with specific issue tracking
        self.posture_issues = []
        self.alert_active = False
        self.alert_reason = ""

        # Check slouch deviation
        if self.deviation > self.offset_threshold:
            self.posture_issues.append("slouch")
        elif self.deviation > self.warning_threshold:
            self.posture_issues.append("slight_slouch")

        # Check shoulder asymmetry (>15px difference is notable)
        baseline_diff = self.baseline_shoulder_diff or 0.0
        if self.shoulder_asymmetry > baseline_diff + 18:
            self.posture_issues.append("shoulder_tilt")

        # Determine overall status
        if "slouch" in self.posture_issues or "shoulder_tilt" in self.posture_issues:
            self.status = "ALERT"
            self.alert_active = True
            reasons = []
            if "slouch" in self.posture_issues:
                reasons.append(f"slouch {self.deviation:.0f}px")
            if "shoulder_tilt" in self.posture_issues:
                reasons.append(f"shoulder tilt {self.shoulder_asymmetry:.0f}px")
            self.alert_reason = "Posture: " + ", ".join(reasons)
        elif "slight_slouch" in self.posture_issues:
            self.status = "WARNING"
        else:
            self.status = "GOOD"

    def get_status(self):
        """
        Returns current detector status.

        Returns:
            dict with keys: offset, baseline, deviation, status, alert, reason,
                           calibrated, shoulder_asymmetry, issues
        """
        return {
            "offset": round(self.current_offset, 1),
            "baseline": round(self.baseline_offset, 1) if self.baseline_offset else 0,
            "deviation": round(self.deviation, 1),
            "status": self.status,
            "alert": self.alert_active,
            "reason": self.alert_reason,
            "calibrated": self.is_calibrated,
            "shoulder_asymmetry": round(self.shoulder_asymmetry, 1),
            "issues": self.posture_issues,
        }
