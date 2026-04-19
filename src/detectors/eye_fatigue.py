"""
ErgoVision — Eye Fatigue Detector (EAR)
Monitors blink rate using the Eye Aspect Ratio formula.
"""

import time
import numpy as np
from collections import deque

import config


class EyeFatigueDetector:
    """
    Detects eye fatigue via the Eye Aspect Ratio (EAR).
    
    EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)
    
    A blink is detected when EAR drops below threshold and recovers.
    Alert fires when rolling blink rate < MIN_BLINK_RATE per minute.
    """

    def __init__(self):
        self.ear_threshold = config.EAR_THRESHOLD
        self.min_blink_rate = config.MIN_BLINK_RATE
        self.smoothing_alpha = config.EAR_SMOOTHING_ALPHA

        # State
        self._smoothed_ear = 0.3  # Initial estimate (open eyes)
        self._blink_buffer = deque()  # Timestamps of detected blinks
        self._below_threshold = False
        self._frames_below = 0
        self._eyes_closed_start = None

        # Current readings
        self.current_ear = 0.3
        self.blink_count_per_min = 0
        self.eyes_closed_duration = 0.0
        self.alert_active = False
        self.alert_reason = ""

    @staticmethod
    def compute_ear(landmarks, eye_indices, frame_w, frame_h):
        """
        Compute Eye Aspect Ratio for one eye.
        
        Args:
            landmarks: MediaPipe face landmarks
            eye_indices: list of 6 landmark indices [p1, p2, p3, p4, p5, p6]
            frame_w: frame width in pixels
            frame_h: frame height in pixels
            
        Returns:
            float: EAR value (0.0 = closed, ~0.3 = open)
        """
        points = []
        for idx in eye_indices:
            lm = landmarks.landmark[idx]
            points.append(np.array([lm.x * frame_w, lm.y * frame_h]))

        p1, p2, p3, p4, p5, p6 = points

        # Vertical distances
        v1 = np.linalg.norm(p2 - p6)
        v2 = np.linalg.norm(p3 - p5)
        # Horizontal distance
        h = np.linalg.norm(p1 - p4)

        if h == 0:
            return 0.0

        ear = (v1 + v2) / (2.0 * h)
        return ear

    def update(self, face_landmarks, frame_w, frame_h):
        """
        Process a new frame's landmarks and update blink state.
        
        Args:
            face_landmarks: MediaPipe face landmarks (single face)
            frame_w: frame width
            frame_h: frame height
        """
        if face_landmarks is None:
            self.alert_active = False
            return

        # Compute EAR for both eyes
        left_ear = self.compute_ear(
            face_landmarks, config.LEFT_EYE_INDICES, frame_w, frame_h
        )
        right_ear = self.compute_ear(
            face_landmarks, config.RIGHT_EYE_INDICES, frame_w, frame_h
        )

        raw_ear = (left_ear + right_ear) / 2.0

        # Exponential moving average smoothing
        self._smoothed_ear = (
            self.smoothing_alpha * raw_ear
            + (1 - self.smoothing_alpha) * self._smoothed_ear
        )
        self.current_ear = self._smoothed_ear

        now = time.time()

        # Blink detection — detect EAR dip below threshold then recovery
        if self._smoothed_ear < self.ear_threshold:
            if not self._below_threshold:
                self._below_threshold = True
                self._frames_below = 0
                self._eyes_closed_start = now
            self._frames_below += 1
            self.eyes_closed_duration = now - self._eyes_closed_start
        else:
            if self._below_threshold and self._frames_below >= config.EAR_CONSEC_FRAMES:
                # Blink completed
                self._blink_buffer.append(now)
            self._below_threshold = False
            self._frames_below = 0
            self._eyes_closed_start = None
            self.eyes_closed_duration = 0.0

        # Clean old blinks from buffer (keep last 60 seconds)
        cutoff = now - config.EAR_BUFFER_SECONDS
        while self._blink_buffer and self._blink_buffer[0] < cutoff:
            self._blink_buffer.popleft()

        self.blink_count_per_min = len(self._blink_buffer)

        # Alert logic
        self.alert_active = False
        self.alert_reason = ""

        if self.blink_count_per_min < self.min_blink_rate:
            self.alert_active = True
            self.alert_reason = f"Low blink rate: {self.blink_count_per_min}/min (min: {self.min_blink_rate})"

        if self.eyes_closed_duration > 1.5:
            self.alert_active = True
            self.alert_reason = f"Eyes closed for {self.eyes_closed_duration:.1f}s"

    def get_status(self):
        """
        Returns current detector status.
        
        Returns:
            dict with keys: ear, blink_rate, alert, reason, eyes_closed
        """
        return {
            "ear": round(self.current_ear, 3),
            "blink_rate": self.blink_count_per_min,
            "alert": self.alert_active,
            "reason": self.alert_reason,
            "eyes_closed": round(self.eyes_closed_duration, 1),
        }
