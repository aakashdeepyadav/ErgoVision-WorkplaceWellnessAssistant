"""
ErgoVision — Productivity Tracker
Tracks active presence and wellness quality over session duration.
"""

import time
from collections import deque


class ProductivityTracker:
    """
    Correlates wellness metrics with active presence time.

    Tracks three states:
    - Active/Healthy: face detected, no alerts active
    - Active/Degraded: face detected, one or more alerts active
    - Absent: face not detected (break or away)

    Provides session-level statistics and hourly breakdowns.
    """

    def __init__(self):
        self._session_start = time.time()

        # Cumulative seconds in each state
        self.healthy_time = 0.0
        self.degraded_time = 0.0
        self.absent_time = 0.0

        self._last_update = time.time()
        self._last_state = "absent"

        # Hourly breakdown for trend charts
        self._hourly_samples = deque(maxlen=480)  # 8 hours of per-minute samples
        self._minute_healthy = 0.0
        self._minute_degraded = 0.0
        self._minute_start = time.time()

    def update(self, face_detected, any_alert_active):
        """
        Update productivity state for this frame.

        Args:
            face_detected: whether a face is currently visible
            any_alert_active: whether any detector has an active alert
        """
        now = time.time()
        delta = min(now - self._last_update, 1.0)  # Cap at 1s to handle pauses
        self._last_update = now

        if not face_detected:
            self.absent_time += delta
            current_state = "absent"
        elif any_alert_active:
            self.degraded_time += delta
            self._minute_degraded += delta
            current_state = "degraded"
        else:
            self.healthy_time += delta
            self._minute_healthy += delta
            current_state = "healthy"

        self._last_state = current_state

        # Log per-minute sample
        if now - self._minute_start >= 60:
            total_minute = self._minute_healthy + self._minute_degraded
            minute_score = (
                (self._minute_healthy / total_minute * 100) if total_minute > 0 else 0
            )
            self._hourly_samples.append({
                "time": now,
                "score": round(minute_score, 1),
                "healthy": round(self._minute_healthy, 1),
                "degraded": round(self._minute_degraded, 1),
            })
            self._minute_healthy = 0.0
            self._minute_degraded = 0.0
            self._minute_start = now

    def get_session_score(self):
        """
        Compute overall session wellness-productivity score.

        Returns:
            float: 0-100 where 100 = all active time was healthy
        """
        active_time = self.healthy_time + self.degraded_time
        if active_time <= 0:
            return 0.0
        return round((self.healthy_time / active_time) * 100, 1)

    def reset_session(self):
        """Reset for a new monitoring session."""
        now = time.time()
        self._session_start = now
        self._last_update = now
        self.healthy_time = 0.0
        self.degraded_time = 0.0
        self.absent_time = 0.0
        self._hourly_samples.clear()
        self._minute_healthy = 0.0
        self._minute_degraded = 0.0
        self._minute_start = now

    def get_status(self):
        """
        Returns current productivity status.

        Returns:
            dict with productivity tracking data
        """
        session_duration = time.time() - self._session_start
        active_time = self.healthy_time + self.degraded_time

        return {
            "session_duration": round(session_duration, 0),
            "healthy_time": round(self.healthy_time, 0),
            "degraded_time": round(self.degraded_time, 0),
            "absent_time": round(self.absent_time, 0),
            "active_time": round(active_time, 0),
            "session_score": self.get_session_score(),
            "current_state": self._last_state,
        }
