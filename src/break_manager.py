"""
ErgoVision — Break Manager
Implements the 20-20-20 rule and tracks break compliance.
"""

import logging
import time
from collections import deque

import config


logger = logging.getLogger("ergovision.breaks")


class BreakManager:
    """
    Manages break reminders based on the 20-20-20 rule:
    Every 20 minutes, look at something 20 feet away for 20 seconds.

    Also detects natural breaks (user leaves, face disappears) and
    tracks compliance for session statistics.
    """

    def __init__(self):
        self.break_interval = config.BREAK_INTERVAL_SECONDS
        self.min_break_duration = config.MIN_BREAK_DURATION_SECONDS

        # State
        self._session_start = time.time()
        self._last_break_time = time.time()
        self._face_absent_start = None
        self._is_on_break = False
        self._break_log = deque(maxlen=100)

        # Current readings
        self.time_since_break = 0.0
        self.break_due = False
        self.break_overdue = False
        self.current_break_duration = 0.0
        self.breaks_taken = 0
        self.breaks_skipped = 0
        self.total_break_time = 0.0
        self.compliance_score = 100.0  # 0-100

    def update(self, face_detected, fatigue_score=0):
        """
        Update break tracking state.

        Detects natural breaks when face disappears from frame for
        longer than MIN_BREAK_DURATION_SECONDS.

        Args:
            face_detected: whether a face is currently visible
            fatigue_score: current fatigue score (0-100) for adaptive intervals
        """
        now = time.time()
        self.time_since_break = now - self._last_break_time

        # Adaptive break interval — shorten if fatigue is high
        effective_interval = self.break_interval
        if fatigue_score > 60:
            effective_interval = max(600, self.break_interval * 0.7)  # Min 10 min
        elif fatigue_score > 40:
            effective_interval = max(900, self.break_interval * 0.85)  # Min 15 min

        # Check if break is due
        self.break_due = self.time_since_break >= effective_interval
        self.break_overdue = self.time_since_break >= (effective_interval * 1.5)

        # Detect natural breaks (face disappears)
        if not face_detected:
            if self._face_absent_start is None:
                self._face_absent_start = now
            else:
                absence_duration = now - self._face_absent_start
                if absence_duration >= self.min_break_duration and not self._is_on_break:
                    self._is_on_break = True
                    self.current_break_duration = absence_duration
        else:
            if self._is_on_break:
                # Break ended — log it
                self._complete_break(now)
            self._face_absent_start = None
            self._is_on_break = False
            self.current_break_duration = 0.0

        # Update compliance
        self._compute_compliance()

    def acknowledge_break(self):
        """User manually acknowledges taking a break."""
        self._complete_break(time.time())

    def _complete_break(self, end_time):
        """Record a completed break."""
        duration = self.current_break_duration
        if duration < self.min_break_duration:
            duration = self.min_break_duration

        was_overdue = self.break_overdue
        self._break_log.append({
            "time": end_time,
            "duration": duration,
            "was_overdue": was_overdue,
        })

        self._last_break_time = end_time
        self.breaks_taken += 1
        self.total_break_time += duration
        self.break_due = False
        self.break_overdue = False
        self._is_on_break = False
        self.current_break_duration = 0.0

        logger.info(
            "Break recorded: %.0fs duration, overdue=%s, total_breaks=%d",
            duration, was_overdue, self.breaks_taken,
        )

    def _compute_compliance(self):
        """Compute break compliance score (0-100)."""
        session_duration = time.time() - self._session_start
        expected_breaks = max(1, session_duration / self.break_interval)
        actual_breaks = self.breaks_taken

        if expected_breaks <= 0:
            self.compliance_score = 100.0
            return

        ratio = min(1.0, actual_breaks / expected_breaks)

        # Penalize for overdue breaks
        overdue_count = sum(1 for b in self._break_log if b.get("was_overdue"))
        overdue_penalty = min(20, overdue_count * 5)

        self.compliance_score = max(0, min(100, ratio * 100 - overdue_penalty))

    def reset_session(self):
        """Reset for a new monitoring session."""
        now = time.time()
        self._session_start = now
        self._last_break_time = now
        self._face_absent_start = None
        self._is_on_break = False
        self._break_log.clear()
        self.breaks_taken = 0
        self.breaks_skipped = 0
        self.total_break_time = 0.0
        self.compliance_score = 100.0

    def get_status(self):
        """
        Returns current break manager status.

        Returns:
            dict with break tracking state
        """
        return {
            "time_since_break": round(self.time_since_break, 0),
            "break_due": self.break_due,
            "break_overdue": self.break_overdue,
            "on_break": self._is_on_break,
            "break_duration": round(self.current_break_duration, 0),
            "breaks_taken": self.breaks_taken,
            "total_break_time": round(self.total_break_time, 0),
            "compliance": round(self.compliance_score, 0),
        }
