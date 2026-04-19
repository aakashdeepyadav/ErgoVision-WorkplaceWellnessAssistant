"""
ErgoVision — Thread-Safe Session State
Shared state object that all detectors write to and the alert engine reads from.
"""

import threading
import time


class SessionState:
    """
    Thread-safe container for all detector readings.
    Updated by detection modules, read by the alert engine and UI.
    """

    def __init__(self):
        self._lock = threading.Lock()
        self._state = {
            # Eye fatigue
            "ear": 0.3,
            "blink_rate": 0,
            "eyes_closed": 0.0,
            "eye_alert": False,
            "eye_reason": "",
            # Posture
            "posture_offset": 0.0,
            "posture_baseline": 0.0,
            "posture_deviation": 0.0,
            "posture_status": "UNCALIBRATED",
            "posture_alert": False,
            "posture_reason": "",
            "posture_calibrated": False,
            # Distance
            "distance_cm": 0.0,
            "iris_px": 0.0,
            "distance_alert": False,
            "distance_reason": "",
            "distance_calibrated": False,
            # Fatigue
            "mar": 0.0,
            "yawn_count": 0,
            "fatigue_score": 0.0,
            "fatigue_alert": False,
            "fatigue_reason": "",
            # System
            "fps": 0.0,
            "face_detected": False,
            "pose_detected": False,
            "session_start": time.time(),
            "is_monitoring": False,
            "is_calibrating": False,
        }

    def update(self, **kwargs):
        """Update one or more state values atomically."""
        with self._lock:
            for key, value in kwargs.items():
                if key in self._state:
                    self._state[key] = value

    def get(self, key, default=None):
        """Get a single state value."""
        with self._lock:
            return self._state.get(key, default)

    def get_all(self):
        """Get a snapshot of all state values."""
        with self._lock:
            return dict(self._state)

    def get_eye_status(self):
        """Get eye-related state."""
        with self._lock:
            return {
                "ear": self._state["ear"],
                "blink_rate": self._state["blink_rate"],
                "eyes_closed": self._state["eyes_closed"],
                "alert": self._state["eye_alert"],
                "reason": self._state["eye_reason"],
            }

    def get_posture_status(self):
        """Get posture-related state."""
        with self._lock:
            return {
                "offset": self._state["posture_offset"],
                "baseline": self._state["posture_baseline"],
                "deviation": self._state["posture_deviation"],
                "status": self._state["posture_status"],
                "alert": self._state["posture_alert"],
                "reason": self._state["posture_reason"],
                "calibrated": self._state["posture_calibrated"],
            }

    def get_distance_status(self):
        """Get distance-related state."""
        with self._lock:
            return {
                "distance_cm": self._state["distance_cm"],
                "iris_px": self._state["iris_px"],
                "alert": self._state["distance_alert"],
                "reason": self._state["distance_reason"],
                "calibrated": self._state["distance_calibrated"],
            }

    def get_fatigue_status(self):
        """Get fatigue-related state."""
        with self._lock:
            return {
                "mar": self._state["mar"],
                "yawn_count": self._state["yawn_count"],
                "fatigue_score": self._state["fatigue_score"],
                "alert": self._state["fatigue_alert"],
                "reason": self._state["fatigue_reason"],
            }
