"""
ErgoVision — Alert Engine (Enhanced)
Manages alert thresholds, cooldowns, progressive escalation, and notification dispatch.
"""

import logging
import time
import config


logger = logging.getLogger("ergovision.alerts")


class AlertEngine:
    """
    Reads from SessionState and triggers alerts with cooldown management.
    Prevents alert fatigue by enforcing minimum intervals between same-type alerts.

    Enhanced with:
    - New alert types: HEAD_TILT, PROLONGED_STARE, TAKE_BREAK
    - Progressive escalation: cooldown reduces if alerts are repeatedly ignored
    """

    def __init__(self, session_state, voice_alert, database, session_id=None):
        """
        Args:
            session_state: SessionState instance
            voice_alert: VoiceAlert instance
            database: DatabaseManager instance
            session_id: current session ID for logging
        """
        self.state = session_state
        self.voice = voice_alert
        self.db = database
        self.session_id = session_id

        self.cooldown_seconds = config.ALERT_COOLDOWN_SECONDS
        self._last_alert_time = {
            "EYE_STRAIN": 0,
            "POOR_POSTURE": 0,
            "TOO_CLOSE": 0,
            "FATIGUE": 0,
            "HEAD_TILT": 0,
            "PROLONGED_STARE": 0,
            "TAKE_BREAK": 0,
        }
        self._ignore_count = {k: 0 for k in self._last_alert_time}
        self._alert_callback = None  # UI callback for popup notifications

    def set_alert_callback(self, callback):
        """
        Register a UI callback for displaying alerts.

        Args:
            callback: function(alert_type: str, message: str) -> None
        """
        self._alert_callback = callback

    def set_session_id(self, session_id):
        """Update session ID (e.g., when a new session starts)."""
        self.session_id = session_id

    def _get_effective_cooldown(self, alert_type):
        """Get cooldown adjusted for escalation level."""
        ignore_count = self._ignore_count.get(alert_type, 0)
        max_level = max(config.ALERT_ESCALATION_LEVELS.keys())
        level = min(ignore_count, max_level)
        multiplier = config.ALERT_ESCALATION_LEVELS.get(level, 1.0)
        return self.cooldown_seconds * multiplier

    def _can_alert(self, alert_type):
        """Check if cooldown period has elapsed for this alert type."""
        now = time.time()
        last = self._last_alert_time.get(alert_type, 0)
        effective_cooldown = self._get_effective_cooldown(alert_type)
        return (now - last) >= effective_cooldown

    def _fire_alert(self, alert_type, reason, value=None):
        """
        Fire an alert: log to DB, speak via TTS, notify UI.

        Args:
            alert_type: alert identifier
            reason: human-readable reason string
            value: numeric value to log
        """
        if not self._can_alert(alert_type):
            # Count as ignored for escalation
            self._ignore_count[alert_type] = self._ignore_count.get(alert_type, 0) + 1
            return

        self._last_alert_time[alert_type] = time.time()
        # Reset ignore count on successful fire
        self._ignore_count[alert_type] = 0

        # Log to database
        if self.session_id and self.db:
            try:
                self.db.log_event(self.session_id, alert_type, value, reason)
            except Exception:
                logger.exception(
                    "Failed to persist alert event (session_id=%s, alert_type=%s).",
                    self.session_id,
                    alert_type,
                )

        # Voice alert
        if self.voice:
            try:
                self.voice.speak_alert(alert_type)
            except Exception:
                logger.exception("Failed to play voice alert for type '%s'.", alert_type)

        # UI callback
        if self._alert_callback:
            message = config.ALERT_MESSAGES.get(alert_type, reason)
            self._alert_callback(alert_type, message)

        logger.warning("Alert fired: %s (%s)", alert_type, reason)

    def check(self):
        """
        Check all detector states and fire alerts as needed.
        Call this once per frame from the main processing loop.

        Returns:
            list: alert types that were fired this check
        """
        fired = []
        state = self.state.get_all()

        if not state.get("is_monitoring", False):
            return fired

        # Eye strain check
        if state.get("eye_alert", False):
            if self._can_alert("EYE_STRAIN"):
                self._fire_alert(
                    "EYE_STRAIN",
                    state.get("eye_reason", "Low blink rate detected"),
                    state.get("blink_rate", 0)
                )
                fired.append("EYE_STRAIN")

        # Posture check
        if state.get("posture_alert", False):
            if self._can_alert("POOR_POSTURE"):
                self._fire_alert(
                    "POOR_POSTURE",
                    state.get("posture_reason", "Poor posture detected"),
                    state.get("posture_deviation", 0)
                )
                fired.append("POOR_POSTURE")

        # Distance check
        if state.get("distance_alert", False):
            if self._can_alert("TOO_CLOSE"):
                self._fire_alert(
                    "TOO_CLOSE",
                    state.get("distance_reason", "Too close to screen"),
                    state.get("distance_cm", 0)
                )
                fired.append("TOO_CLOSE")

        # Fatigue check
        if state.get("fatigue_alert", False):
            if self._can_alert("FATIGUE"):
                self._fire_alert(
                    "FATIGUE",
                    state.get("fatigue_reason", "Mental fatigue detected"),
                    state.get("fatigue_score", 0)
                )
                fired.append("FATIGUE")

        # Head tilt check
        if state.get("head_tilt_alert", False):
            if self._can_alert("HEAD_TILT"):
                self._fire_alert(
                    "HEAD_TILT",
                    state.get("head_tilt_reason", "Sustained head tilt detected"),
                    state.get("head_tilt_angle", 0)
                )
                fired.append("HEAD_TILT")

        # Prolonged stare check
        if state.get("stare_alert", False):
            if self._can_alert("PROLONGED_STARE"):
                self._fire_alert(
                    "PROLONGED_STARE",
                    f"Staring for {state.get('stare_duration', 0):.0f}s without saccade",
                    state.get("stare_duration", 0)
                )
                fired.append("PROLONGED_STARE")

        # Break reminder check
        if state.get("break_overdue", False):
            if self._can_alert("TAKE_BREAK"):
                self._fire_alert(
                    "TAKE_BREAK",
                    f"Working for {state.get('time_since_break', 0) / 60:.0f} min without a break",
                    state.get("time_since_break", 0)
                )
                fired.append("TAKE_BREAK")

        return fired

    def get_cooldown_status(self):
        """
        Get remaining cooldown time for each alert type.

        Returns:
            dict: alert_type → seconds remaining (0 if ready to fire)
        """
        now = time.time()
        status = {}
        for alert_type, last_time in self._last_alert_time.items():
            effective_cooldown = self._get_effective_cooldown(alert_type)
            remaining = max(0, effective_cooldown - (now - last_time))
            status[alert_type] = round(remaining, 0)
        return status
