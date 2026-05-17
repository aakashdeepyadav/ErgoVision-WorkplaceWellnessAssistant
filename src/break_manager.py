"""
ErgoVision — Break Manager (Enhanced)
Implements the 20-20-20 rule, Pomodoro timer, hydration reminders,
posture streak tracking, and stretch suggestions.
"""

import logging
import random
import time
from collections import deque

import config


logger = logging.getLogger("ergovision.breaks")


class BreakManager:
    """
    Manages break reminders with two modes:
    1. 20-20-20 Rule: Every 20 minutes, look 20 feet away for 20 seconds.
    2. Pomodoro: 25 min work → 5 min break → repeat 4x → 15 min long break.

    Also tracks hydration reminders, posture streaks, and stretch suggestions.
    """

    def __init__(self):
        self.break_interval = config.BREAK_INTERVAL_SECONDS
        self.min_break_duration = config.MIN_BREAK_DURATION_SECONDS

        # Mode: "20-20-20" or "pomodoro"
        self.mode = "20-20-20"

        # ── 20-20-20 state ──
        self._session_start = time.time()
        self._last_break_time = time.time()
        self._face_absent_start = None
        self._is_on_break = False
        self._break_log = deque(maxlen=100)

        # ── Pomodoro state ──
        self._pomodoro_phase = "work"  # work, short_break, long_break
        self._pomodoro_phase_start = time.time()
        self._pomodoro_cycle = 0  # Completed work cycles (0-3)
        self._pomodoro_total_cycles = 0

        # ── Hydration state ──
        self._last_hydration_time = time.time()
        self.hydration_glasses = 0
        self.hydration_goal = config.HYDRATION_DAILY_GOAL
        self.hydration_due = False

        # ── Posture streak state ──
        self._posture_good_start = None
        self.posture_streak_seconds = 0.0
        self.best_posture_streak = 0.0
        self.posture_streak_milestone = ""

        # ── Stretch suggestion ──
        self.current_stretch = None
        self._last_stretch_index = -1

        # ── Current readings ──
        self.time_since_break = 0.0
        self.break_due = False
        self.break_overdue = False
        self.current_break_duration = 0.0
        self.breaks_taken = 0
        self.breaks_skipped = 0
        self.total_break_time = 0.0
        self.compliance_score = 100.0

    def set_mode(self, mode):
        """Switch between '20-20-20' and 'pomodoro' modes."""
        if mode in ("20-20-20", "pomodoro"):
            self.mode = mode
            self._reset_pomodoro()
            self._last_break_time = time.time()
            logger.info("Break mode changed to: %s", mode)

    def _reset_pomodoro(self):
        """Reset Pomodoro state."""
        self._pomodoro_phase = "work"
        self._pomodoro_phase_start = time.time()
        self._pomodoro_cycle = 0

    def _get_pomodoro_phase_duration(self):
        """Get the duration of the current Pomodoro phase in seconds."""
        if self._pomodoro_phase == "work":
            return config.POMODORO_WORK_MINUTES * 60
        elif self._pomodoro_phase == "short_break":
            return config.POMODORO_SHORT_BREAK_MINUTES * 60
        else:  # long_break
            return config.POMODORO_LONG_BREAK_MINUTES * 60

    def _update_pomodoro(self):
        """Update the Pomodoro timer state machine."""
        now = time.time()
        elapsed = now - self._pomodoro_phase_start
        phase_duration = self._get_pomodoro_phase_duration()

        if elapsed >= phase_duration:
            # Phase completed — transition
            if self._pomodoro_phase == "work":
                self._pomodoro_cycle += 1
                self._pomodoro_total_cycles += 1
                if self._pomodoro_cycle >= config.POMODORO_CYCLES_BEFORE_LONG:
                    self._pomodoro_phase = "long_break"
                    self._pomodoro_cycle = 0
                else:
                    self._pomodoro_phase = "short_break"
                self.break_due = True
                self._pick_stretch()
            else:
                # Break ended → back to work
                self._pomodoro_phase = "work"
                self._last_break_time = now
                self.break_due = False
                self.break_overdue = False
                self.breaks_taken += 1

            self._pomodoro_phase_start = now

        # If in work phase and time is almost up
        if self._pomodoro_phase == "work":
            self.time_since_break = elapsed
            remaining = phase_duration - elapsed
            self.break_due = remaining <= 0
            self.break_overdue = elapsed >= phase_duration * 1.2

    def _update_hydration(self):
        """Check if hydration reminder is due."""
        now = time.time()
        time_since_last = now - self._last_hydration_time
        self.hydration_due = time_since_last >= config.HYDRATION_INTERVAL_SECONDS

    def drink_water(self):
        """User acknowledges drinking water."""
        self.hydration_glasses += 1
        self._last_hydration_time = time.time()
        self.hydration_due = False
        logger.info("Water consumed: %d/%d glasses", self.hydration_glasses, self.hydration_goal)

    def _update_posture_streak(self, posture_status):
        """Track consecutive good posture duration."""
        now = time.time()
        is_good = posture_status in ("GOOD", "UNCALIBRATED")

        if is_good:
            if self._posture_good_start is None:
                self._posture_good_start = now
            self.posture_streak_seconds = now - self._posture_good_start
            # Check milestones
            streak_minutes = self.posture_streak_seconds / 60.0
            self.posture_streak_milestone = ""
            for mins, msg in sorted(config.POSTURE_STREAK_MILESTONES.items(), reverse=True):
                if streak_minutes >= mins:
                    self.posture_streak_milestone = msg
                    break
            # Update best
            if self.posture_streak_seconds > self.best_posture_streak:
                self.best_posture_streak = self.posture_streak_seconds
        else:
            self._posture_good_start = None
            self.posture_streak_seconds = 0.0
            self.posture_streak_milestone = ""

    def _pick_stretch(self):
        """Select a random stretch exercise (avoid repeating the last one)."""
        exercises = config.STRETCH_EXERCISES
        available = [i for i in range(len(exercises)) if i != self._last_stretch_index]
        idx = random.choice(available) if available else 0
        self._last_stretch_index = idx
        self.current_stretch = exercises[idx]

    def update(self, face_detected, fatigue_score=0, posture_status="GOOD"):
        """
        Update break tracking state.

        Args:
            face_detected: whether a face is currently visible
            fatigue_score: current fatigue score (0-100) for adaptive intervals
            posture_status: current posture status string
        """
        now = time.time()

        # ── Hydration check ──
        self._update_hydration()

        # ── Posture streak ──
        self._update_posture_streak(posture_status)

        # ── Mode-specific break logic ──
        if self.mode == "pomodoro":
            self._update_pomodoro()
            # Still detect natural breaks
            if not face_detected:
                if self._face_absent_start is None:
                    self._face_absent_start = now
            else:
                self._face_absent_start = None
            return

        # ── 20-20-20 mode ──
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

        if self.break_due and self.current_stretch is None:
            self._pick_stretch()

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
        self.current_stretch = None  # Clear stretch after break

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
        self.current_stretch = None

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
        self._reset_pomodoro()
        self._last_hydration_time = now
        self.hydration_glasses = 0
        self.hydration_due = False
        self._posture_good_start = None
        self.posture_streak_seconds = 0.0
        self.best_posture_streak = 0.0
        self.current_stretch = None

    def get_status(self):
        """Returns current break manager status."""
        pomodoro_remaining = 0
        if self.mode == "pomodoro":
            elapsed = time.time() - self._pomodoro_phase_start
            pomodoro_remaining = max(0, self._get_pomodoro_phase_duration() - elapsed)

        return {
            "mode": self.mode,
            "time_since_break": round(self.time_since_break, 0),
            "break_due": self.break_due,
            "break_overdue": self.break_overdue,
            "on_break": self._is_on_break,
            "break_duration": round(self.current_break_duration, 0),
            "breaks_taken": self.breaks_taken,
            "total_break_time": round(self.total_break_time, 0),
            "compliance": round(self.compliance_score, 0),
            # Pomodoro
            "pomodoro_phase": self._pomodoro_phase,
            "pomodoro_remaining": round(pomodoro_remaining, 0),
            "pomodoro_cycle": self._pomodoro_cycle,
            "pomodoro_total_cycles": self._pomodoro_total_cycles,
            # Hydration
            "hydration_glasses": self.hydration_glasses,
            "hydration_goal": self.hydration_goal,
            "hydration_due": self.hydration_due,
            # Posture streak
            "posture_streak": round(self.posture_streak_seconds, 0),
            "best_posture_streak": round(self.best_posture_streak, 0),
            "posture_streak_milestone": self.posture_streak_milestone,
            # Stretch
            "current_stretch": self.current_stretch,
        }
