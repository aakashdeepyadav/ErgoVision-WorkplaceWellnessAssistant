"""
ErgoVision — Posture Detector
Monitors slouching via nose-shoulder Y-axis deviation.
"""

import numpy as np
from collections import deque

import config


class PostureDetector:
    """
    Detects poor posture by comparing nose-to-shoulder vertical offset
    against a personal baseline established during calibration.
    
    Slouch offset = nose_y - mean(left_shoulder_y, right_shoulder_y)
    Alert fires when offset exceeds baseline by POSTURE_OFFSET_THRESHOLD pixels.
    """

    # MediaPipe Pose landmark indices
    NOSE_INDEX = 0
    LEFT_SHOULDER_INDEX = 11
    RIGHT_SHOULDER_INDEX = 12

    def __init__(self):
        self.offset_threshold = config.POSTURE_OFFSET_THRESHOLD
        self.warning_threshold = config.POSTURE_WARNING_THRESHOLD

        # Calibration state
        self.baseline_offset = None
        self.is_calibrated = False
        self._calibration_samples = []

        # Current readings
        self.current_offset = 0.0
        self.deviation = 0.0
        self.status = "UNCALIBRATED"  # GOOD, WARNING, ALERT, UNCALIBRATED
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
        self.is_calibrated = True
        self._calibration_samples = []
        return True

    def reset_calibration(self):
        """Reset calibration state."""
        self.baseline_offset = None
        self.is_calibrated = False
        self._calibration_samples = []
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

        # Determine status
        self.alert_active = False
        self.alert_reason = ""

        if self.deviation > self.offset_threshold:
            self.status = "ALERT"
            self.alert_active = True
            self.alert_reason = f"Posture deviation: {self.deviation:.0f}px (threshold: {self.offset_threshold}px)"
        elif self.deviation > self.warning_threshold:
            self.status = "WARNING"
        else:
            self.status = "GOOD"

    def get_status(self):
        """
        Returns current detector status.
        
        Returns:
            dict with keys: offset, baseline, deviation, status, alert, reason
        """
        return {
            "offset": round(self.current_offset, 1),
            "baseline": round(self.baseline_offset, 1) if self.baseline_offset else 0,
            "deviation": round(self.deviation, 1),
            "status": self.status,
            "alert": self.alert_active,
            "reason": self.alert_reason,
            "calibrated": self.is_calibrated,
        }
