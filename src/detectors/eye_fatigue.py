"""
ErgoVision — Eye Fatigue Detector (EAR + Gaze)
Monitors blink rate using the Eye Aspect Ratio formula.
Also detects prolonged staring without natural saccades.
"""

import time
import numpy as np
from collections import deque

import config


class EyeFatigueDetector:
    """
    Detects eye fatigue via the Eye Aspect Ratio (EAR) and
    prolonged staring via iris position tracking.

    EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)

    A blink is detected when EAR drops below threshold and recovers.
    Alert fires when rolling blink rate < MIN_BLINK_RATE per minute.

    Gaze tracking monitors iris center position for saccade detection.
    A prolonged stare alert fires when no saccade is detected for
    GAZE_STARE_SECONDS.
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

        # Gaze / stare tracking
        self._last_iris_pos = None
        self._last_saccade_time = time.time()
        self._gaze_stare_threshold = config.GAZE_STARE_SECONDS
        self._gaze_movement_threshold = config.GAZE_MOVEMENT_THRESHOLD
        self._stare_duration = 0.0

        # Gaze direction (relative position of iris in eye socket)
        self.gaze_x = 0.0  # -1 = left, 0 = center, 1 = right
        self.gaze_y = 0.0  # -1 = up, 0 = center, 1 = down

        # Current readings
        self.current_ear = 0.3
        self.blink_count_per_min = 0
        self.eyes_closed_duration = 0.0
        self.stare_alert = False
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

    def _compute_gaze_direction(self, face_landmarks, frame_w, frame_h):
        """
        Compute gaze direction using iris center relative to eye bounds.

        Uses left iris center relative to left eye socket to estimate
        where the user is looking.

        Returns:
            tuple: (gaze_x, gaze_y, iris_center) or (0, 0, None) if unavailable
        """
        try:
            # Left eye corners
            left_outer = face_landmarks.landmark[33]
            left_inner = face_landmarks.landmark[133]
            left_top = face_landmarks.landmark[159]
            left_bottom = face_landmarks.landmark[145]

            # Left iris center (average of 4 iris landmarks)
            iris_indices = config.LEFT_IRIS_INDICES
            iris_x = sum(face_landmarks.landmark[i].x for i in iris_indices) / 4
            iris_y = sum(face_landmarks.landmark[i].y for i in iris_indices) / 4

            # Compute relative position within eye socket
            eye_center_x = (left_outer.x + left_inner.x) / 2
            eye_center_y = (left_top.y + left_bottom.y) / 2
            eye_width = abs(left_inner.x - left_outer.x)
            eye_height = abs(left_bottom.y - left_top.y)

            if eye_width == 0 or eye_height == 0:
                return 0.0, 0.0, None

            gaze_x = (iris_x - eye_center_x) / (eye_width / 2)
            gaze_y = (iris_y - eye_center_y) / (eye_height / 2)

            # Clamp to [-1, 1]
            gaze_x = max(-1.0, min(1.0, gaze_x))
            gaze_y = max(-1.0, min(1.0, gaze_y))

            iris_center = np.array([iris_x, iris_y])
            return gaze_x, gaze_y, iris_center
        except (IndexError, AttributeError):
            return 0.0, 0.0, None

    def _update_stare_detection(self, iris_center):
        """
        Detect prolonged staring by tracking iris movement.

        A saccade is detected when iris position shifts by more than
        the movement threshold. Alert fires when no saccade for N seconds.
        """
        now = time.time()

        if iris_center is None:
            self._last_iris_pos = None
            return

        if self._last_iris_pos is not None:
            movement = np.linalg.norm(iris_center - self._last_iris_pos)
            if movement > self._gaze_movement_threshold:
                self._last_saccade_time = now

        self._last_iris_pos = iris_center.copy()
        self._stare_duration = now - self._last_saccade_time

        self.stare_alert = self._stare_duration > self._gaze_stare_threshold

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
            self.stare_alert = False
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

        # Gaze direction + stare detection
        self.gaze_x, self.gaze_y, iris_center = self._compute_gaze_direction(
            face_landmarks, frame_w, frame_h
        )
        self._update_stare_detection(iris_center)

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
            dict with keys: ear, blink_rate, alert, reason, eyes_closed,
                           gaze_x, gaze_y, stare_duration, stare_alert
        """
        return {
            "ear": round(self.current_ear, 3),
            "blink_rate": self.blink_count_per_min,
            "alert": self.alert_active,
            "reason": self.alert_reason,
            "eyes_closed": round(self.eyes_closed_duration, 1),
            "gaze_x": round(self.gaze_x, 2),
            "gaze_y": round(self.gaze_y, 2),
            "stare_duration": round(self._stare_duration, 1),
            "stare_alert": self.stare_alert,
        }
