"""Tests for database operations."""

import os
import pytest
from src.database import DatabaseManager


@pytest.fixture
def db(tmp_path):
    """Create a temporary database for each test."""
    db_path = str(tmp_path / "test_wellness.db")
    return DatabaseManager(db_path=db_path)


class TestSessionLifecycle:
    def test_start_session_returns_id(self, db):
        sid = db.start_session()
        assert sid is not None
        assert isinstance(sid, int)

    def test_end_session_sets_duration(self, db):
        sid = db.start_session()
        result = db.end_session(sid)
        assert result is True

    def test_recent_sessions_returns_started_session(self, db):
        sid = db.start_session()
        sessions = db.get_recent_sessions(limit=5)
        assert len(sessions) >= 1
        assert sessions[0]["id"] == sid


class TestEventLogging:
    def test_log_event_persists(self, db):
        sid = db.start_session()
        result = db.log_event(sid, "EYE_STRAIN", 3.0, "low blink rate")
        assert result is True

        events = db.get_session_events(sid)
        assert len(events) == 1
        assert events[0]["event_type"] == "EYE_STRAIN"

    def test_event_counts_by_type(self, db):
        sid = db.start_session()
        db.log_event(sid, "EYE_STRAIN", 2.0, "test")
        db.log_event(sid, "EYE_STRAIN", 3.0, "test")
        db.log_event(sid, "POOR_POSTURE", 40.0, "test")

        counts = db.get_event_counts_by_type(sid)
        count_dict = {row[0]: row[1] for row in counts}
        assert count_dict.get("EYE_STRAIN") == 2
        assert count_dict.get("POOR_POSTURE") == 1


class TestSnapshotLogging:
    def test_log_snapshot_persists(self, db):
        sid = db.start_session()
        result = db.log_snapshot(sid, 0.28, 12, 15.3, 62.0, 25.0, head_tilt=5.2)
        assert result is True

        snapshots = db.get_session_snapshots(sid)
        assert len(snapshots) == 1
        assert snapshots[0]["blink_rate"] == 12
        assert snapshots[0]["head_tilt"] == 5.2


class TestBreakEvents:
    def test_log_break_persists(self, db):
        sid = db.start_session()
        result = db.log_break(sid, 25.0, was_overdue=False)
        assert result is True

        stats = db.get_break_stats(sid)
        assert stats["total_breaks"] == 1
        assert stats["overdue_count"] == 0

    def test_overdue_break_counted(self, db):
        sid = db.start_session()
        db.log_break(sid, 20.0, was_overdue=True)
        db.log_break(sid, 30.0, was_overdue=False)

        stats = db.get_break_stats(sid)
        assert stats["total_breaks"] == 2
        assert stats["overdue_count"] == 1
        assert stats["on_time_count"] == 1


class TestDailySummary:
    def test_update_and_get_daily_summary(self, db):
        sid = db.start_session()
        db.log_snapshot(sid, 0.3, 15, 10.0, 65.0, 20.0)
        db.end_session(sid)

        result = db.update_daily_summary()
        assert result is True

        summary = db.get_daily_summary()
        assert summary is not None
        assert summary["total_sessions"] >= 1
