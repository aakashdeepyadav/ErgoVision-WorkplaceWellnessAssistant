"""
ErgoVision — Fatigue Score Detector (MAR + Composite)
Monitors yawning via Mouth Aspect Ratio and computes composite fatigue score.
Enhanced with session-duration weighting and head tilt correlation.
"""

import time
import numpy as np
from collections import deque

import config


class FatigueScoreDetector:
    """
    Detects mental fatigue through yawn frequency (MAR) and
    computes a composite fatigue score combining blink rate, yawns,
    head tilt, and session duration.

    MAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)
    Applied to lip landmarks — analogous to EAR but for the mouth.
    """

    # Lip landmark indices for MAR calculation
    # Using a reliable set: outer lip top, bottom, left corner, right corner
    TOP_LIP = 13       # Upper lip center
    BOTTOM_LIP = 14    # Lower lip center
    LEFT_CORNER = 61   # Left mouth corner
    RIGHT_CORNER = 291 # Right mouth corner
    UPPER_INNER = 0    # Upper inner lip
    LOWER_INNER = 17   # Lower inner lip

    def __init__(self):
        self.mar_threshold = config.MAR_THRESHOLD
        self.sustained_seconds = config.MAR_SUSTAINED_SECONDS
        self.max_yawns = config.MAX_YAWNS_PER_HOUR

        # State
        self._yawn_buffer = deque()  # Timestamps of detected yawns
        self._mouth_open_start = None
        self._is_yawning = False
        self._session_start = time.time()

        # Fatigue score history for trend detection
        self._score_history = deque(maxlen=60)  # Last 60 samples

        # Current readings
        self.current_mar = 0.0
        self.yawn_count_per_hour = 0
        self.fatigue_score = 0.0  # 0-100 composite
        self.fatigue_trend = "stable"  # stable, rising, falling
        self.alert_active = False
        self.alert_reason = ""

    def compute_mar(self, face_landmarks, frame_w, frame_h):
        """
        Compute Mouth Aspect Ratio.

        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions

        Returns:
            float: MAR value (0.0 = closed, >0.6 = wide open / yawn)
        """
        def _pt(idx):
            lm = face_landmarks.landmark[idx]
            return np.array([lm.x * frame_w, lm.y * frame_h])

        top = _pt(self.TOP_LIP)
        bottom = _pt(self.BOTTOM_LIP)
        left = _pt(self.LEFT_CORNER)
        right = _pt(self.RIGHT_CORNER)
        upper_inner = _pt(self.UPPER_INNER)
        lower_inner = _pt(self.LOWER_INNER)

        # Vertical distances
        v1 = np.linalg.norm(top - bottom)
        v2 = np.linalg.norm(upper_inner - lower_inner)
        # Horizontal distance
        h = np.linalg.norm(left - right)

        if h == 0:
            return 0.0

        mar = (v1 + v2) / (2.0 * h)
        return mar

    def _compute_fatigue_trend(self):
        """Determine if fatigue is rising, falling, or stable."""
        if len(self._score_history) < 10:
            self.fatigue_trend = "stable"
            return

        recent = list(self._score_history)
        first_half = np.mean(recent[:len(recent)//2])
        second_half = np.mean(recent[len(recent)//2:])
        delta = second_half - first_half

        if delta > 5:
            self.fatigue_trend = "rising"
        elif delta < -5:
            self.fatigue_trend = "falling"
        else:
            self.fatigue_trend = "stable"

    def update(self, face_landmarks, frame_w, frame_h, blink_rate=None,
               head_tilt_angle=None):
        """
        Process a new frame and update fatigue state.

        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions
            blink_rate: current blinks/min from EyeFatigueDetector
            head_tilt_angle: current head tilt angle from HeadTiltDetector
        """
        if face_landmarks is None:
            self.alert_active = False
            return

        self.current_mar = self.compute_mar(face_landmarks, frame_w, frame_h)

        now = time.time()

        # Yawn detection — MAR above threshold sustained for N seconds
        if self.current_mar > self.mar_threshold:
            if self._mouth_open_start is None:
                self._mouth_open_start = now
            elif (now - self._mouth_open_start) >= self.sustained_seconds and not self._is_yawning:
                # Yawn confirmed
                self._is_yawning = True
                self._yawn_buffer.append(now)
        else:
            self._mouth_open_start = None
            self._is_yawning = False

        # Clean old yawns (keep last hour)
        cutoff = now - 3600
        while self._yawn_buffer and self._yawn_buffer[0] < cutoff:
            self._yawn_buffer.popleft()

        self.yawn_count_per_hour = len(self._yawn_buffer)

        # --- Enhanced Composite Fatigue Score (0-100) ---

        # Factor 1: Low blink rate (0-30 points)
        blink_factor = 0
        if blink_rate is not None and blink_rate < config.MIN_BLINK_RATE:
            blink_factor = max(0, (config.MIN_BLINK_RATE - blink_rate) / config.MIN_BLINK_RATE * 30)

        # Factor 2: Yawn frequency (0-30 points)
        yawn_factor = min(30, (self.yawn_count_per_hour / max(1, self.max_yawns)) * 30)

        # Factor 3: Session duration fatigue (0-20 points)
        # Fatigue naturally accumulates: ramps from 0 at start to 20 after 2 hours
        session_minutes = (now - self._session_start) / 60.0
        duration_factor = min(20, (session_minutes / 120.0) * 20)

        # Factor 4: Head tilt contribution (0-20 points)
        # Sustained head tilt correlates with fatigue
        tilt_factor = 0
        if head_tilt_angle is not None:
            abs_tilt = abs(head_tilt_angle)
            if abs_tilt > 10:
                tilt_factor = min(20, (abs_tilt - 10) / 20 * 20)

        self.fatigue_score = min(100, blink_factor + yawn_factor + duration_factor + tilt_factor)

        # Track score history for trend
        self._score_history.append(self.fatigue_score)
        self._compute_fatigue_trend()

        # Alert logic
        self.alert_active = False
        self.alert_reason = ""

        if self.yawn_count_per_hour >= self.max_yawns:
            self.alert_active = True
            self.alert_reason = f"High yawn rate: {self.yawn_count_per_hour}/hr (threshold: {self.max_yawns})"

        if self.fatigue_score > 70:
            self.alert_active = True
            if not self.alert_reason:
                self.alert_reason = f"High fatigue score: {self.fatigue_score:.0f}/100"

    def reset_session_timer(self):
        """Reset the session start time (e.g., after a break)."""
        self._session_start = time.time()

    def get_status(self):
        """
        Returns current detector status.

        Returns:
            dict with keys: mar, yawn_count, fatigue_score, fatigue_trend, alert, reason
        """
        return {
            "mar": round(self.current_mar, 3),
            "yawn_count": self.yawn_count_per_hour,
            "fatigue_score": round(self.fatigue_score, 1),
            "fatigue_trend": self.fatigue_trend,
            "alert": self.alert_active,
            "reason": self.alert_reason,
        }
