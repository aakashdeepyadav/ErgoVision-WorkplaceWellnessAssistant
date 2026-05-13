"""
ErgoVision — Database Manager (Enhanced)
SQLite schema and CRUD operations for session logging, daily summaries, and break tracking.
"""

import logging
import os
import sqlite3
from datetime import datetime, timedelta

import config


logger = logging.getLogger("ergovision.database")


class DatabaseManager:
    """Manages SQLite storage for wellness sessions, events, snapshots, and daily summaries."""

    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        db_dir = os.path.dirname(os.path.abspath(self.db_path))
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)
        self._init_db()

    def _connect(self):
        """Open a SQLite connection with a lock timeout for busy DB states."""
        return sqlite3.connect(self.db_path, timeout=config.DB_TIMEOUT_SECONDS)

    def _init_db(self):
        """Create tables if they don't exist."""
        try:
            with self._connect() as conn:
                conn.execute("PRAGMA journal_mode=WAL")
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS sessions (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        start_time TEXT NOT NULL,
                        end_time TEXT,
                        duration_minutes REAL
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        value REAL,
                        details TEXT,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS snapshots (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        ear REAL,
                        blink_rate INTEGER,
                        posture_deviation REAL,
                        distance_cm REAL,
                        fatigue_score REAL,
                        head_tilt REAL DEFAULT 0,
                        gaze_x REAL DEFAULT 0,
                        gaze_y REAL DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS break_events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        session_id INTEGER NOT NULL,
                        timestamp TEXT NOT NULL,
                        duration_seconds REAL,
                        was_overdue INTEGER DEFAULT 0,
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    )
                """)
                conn.execute("""
                    CREATE TABLE IF NOT EXISTS daily_summaries (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        date TEXT NOT NULL UNIQUE,
                        total_sessions INTEGER DEFAULT 0,
                        total_minutes REAL DEFAULT 0,
                        avg_blink_rate REAL DEFAULT 0,
                        avg_posture_deviation REAL DEFAULT 0,
                        avg_distance_cm REAL DEFAULT 0,
                        avg_fatigue_score REAL DEFAULT 0,
                        avg_head_tilt REAL DEFAULT 0,
                        total_alerts INTEGER DEFAULT 0,
                        breaks_taken INTEGER DEFAULT 0,
                        break_compliance REAL DEFAULT 0,
                        wellness_score REAL DEFAULT 0
                    )
                """)
                # Migration: add new columns to snapshots if they don't exist
                self._migrate_snapshots(conn)
                conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to initialize database schema at '%s'.", self.db_path)
            raise

    def _migrate_snapshots(self, conn):
        """Add new columns to snapshots table if missing (safe migration)."""
        try:
            cursor = conn.execute("PRAGMA table_info(snapshots)")
            existing_columns = {row[1] for row in cursor.fetchall()}

            migrations = {
                "head_tilt": "REAL DEFAULT 0",
                "gaze_x": "REAL DEFAULT 0",
                "gaze_y": "REAL DEFAULT 0",
            }

            for col_name, col_type in migrations.items():
                if col_name not in existing_columns:
                    conn.execute(f"ALTER TABLE snapshots ADD COLUMN {col_name} {col_type}")
                    logger.info("Migrated snapshots table: added column '%s'.", col_name)
        except sqlite3.Error:
            logger.debug("Snapshot migration skipped (columns may already exist).")

    def start_session(self):
        """
        Start a new monitoring session.

        Returns:
            int: session ID
        """
        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                cursor = conn.execute(
                    "INSERT INTO sessions (start_time) VALUES (?)",
                    (now,)
                )
                conn.commit()
                return cursor.lastrowid
        except sqlite3.Error:
            logger.exception("Failed to start a new session.")
            return None

    def end_session(self, session_id):
        """End a monitoring session."""
        if not session_id:
            return False

        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                # Calculate duration
                row = conn.execute(
                    "SELECT start_time FROM sessions WHERE id = ?",
                    (session_id,)
                ).fetchone()

                duration = 0.0
                if row:
                    start = datetime.fromisoformat(row[0])
                    duration = (datetime.now() - start).total_seconds() / 60.0

                conn.execute(
                    "UPDATE sessions SET end_time = ?, duration_minutes = ? WHERE id = ?",
                    (now, round(duration, 2), session_id)
                )
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception("Failed to end session '%s'.", session_id)
            return False

    def log_event(self, session_id, event_type, value=None, details=None):
        """
        Log a wellness event (alert triggered, etc.)

        Args:
            session_id: current session ID
            event_type: one of EYE_STRAIN, POOR_POSTURE, TOO_CLOSE, FATIGUE, etc.
            value: numeric value associated with the event
            details: additional text details
        """
        if not session_id:
            return False

        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO events (session_id, timestamp, event_type, value, details) VALUES (?, ?, ?, ?, ?)",
                    (session_id, now, event_type, value, details)
                )
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception(
                "Failed to log event for session '%s' (event_type=%s).",
                session_id,
                event_type,
            )
            return False

    def log_snapshot(self, session_id, ear, blink_rate, posture_deviation,
                     distance_cm, fatigue_score, head_tilt=0, gaze_x=0, gaze_y=0):
        """
        Log a periodic health snapshot (every 30 seconds).

        Args:
            session_id: current session ID
            ear: current EAR value
            blink_rate: blinks per minute
            posture_deviation: pixels from baseline
            distance_cm: screen distance
            fatigue_score: composite fatigue 0-100
            head_tilt: head tilt angle in degrees
            gaze_x: horizontal gaze direction (-1 to 1)
            gaze_y: vertical gaze direction (-1 to 1)
        """
        if not session_id:
            return False

        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO snapshots
                       (session_id, timestamp, ear, blink_rate, posture_deviation,
                        distance_cm, fatigue_score, head_tilt, gaze_x, gaze_y)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, now, ear, blink_rate, posture_deviation,
                     distance_cm, fatigue_score, head_tilt, gaze_x, gaze_y)
                )
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception("Failed to log snapshot for session '%s'.", session_id)
            return False

    def log_break(self, session_id, duration_seconds, was_overdue=False):
        """Log a break event."""
        if not session_id:
            return False

        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    "INSERT INTO break_events (session_id, timestamp, duration_seconds, was_overdue) VALUES (?, ?, ?, ?)",
                    (session_id, now, duration_seconds, int(was_overdue))
                )
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception("Failed to log break for session '%s'.", session_id)
            return False

    def update_daily_summary(self, date_str=None):
        """
        Compute and store/update daily summary for the given date.

        Args:
            date_str: ISO date string (YYYY-MM-DD), defaults to today
        """
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            with self._connect() as conn:
                # Get session stats for the day
                sessions = conn.execute(
                    "SELECT COUNT(*), COALESCE(SUM(duration_minutes), 0) FROM sessions WHERE start_time LIKE ?",
                    (f"{date_str}%",)
                ).fetchone()

                # Get snapshot averages for the day
                avgs = conn.execute(
                    """SELECT
                        COALESCE(AVG(blink_rate), 0),
                        COALESCE(AVG(posture_deviation), 0),
                        COALESCE(AVG(distance_cm), 0),
                        COALESCE(AVG(fatigue_score), 0),
                        COALESCE(AVG(head_tilt), 0)
                    FROM snapshots WHERE timestamp LIKE ?""",
                    (f"{date_str}%",)
                ).fetchone()

                # Get alert count
                alert_count = conn.execute(
                    "SELECT COUNT(*) FROM events WHERE timestamp LIKE ?",
                    (f"{date_str}%",)
                ).fetchone()[0]

                # Get break stats
                break_stats = conn.execute(
                    "SELECT COUNT(*) FROM break_events WHERE timestamp LIKE ?",
                    (f"{date_str}%",)
                ).fetchone()

                conn.execute("""
                    INSERT OR REPLACE INTO daily_summaries
                    (date, total_sessions, total_minutes, avg_blink_rate,
                     avg_posture_deviation, avg_distance_cm, avg_fatigue_score,
                     avg_head_tilt, total_alerts, breaks_taken)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    date_str,
                    sessions[0], sessions[1],
                    avgs[0], avgs[1], avgs[2], avgs[3], avgs[4],
                    alert_count,
                    break_stats[0],
                ))
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception("Failed to update daily summary for '%s'.", date_str)
            return False

    def get_daily_summary(self, date_str=None):
        """Get daily summary for a specific date."""
        if date_str is None:
            date_str = datetime.now().strftime("%Y-%m-%d")

        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                row = conn.execute(
                    "SELECT * FROM daily_summaries WHERE date = ?",
                    (date_str,)
                ).fetchone()
                return dict(row) if row else None
        except sqlite3.Error:
            logger.exception("Failed to fetch daily summary for '%s'.", date_str)
            return None

    def get_weekly_summaries(self, days=7):
        """Get daily summaries for the last N days."""
        cutoff = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM daily_summaries WHERE date >= ? ORDER BY date",
                    (cutoff,)
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch weekly summaries.")
            return []

    def get_session_events(self, session_id):
        """Get all events for a session."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch events for session '%s'.", session_id)
            return []

    def get_session_snapshots(self, session_id):
        """Get all snapshots for a session."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM snapshots WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch snapshots for session '%s'.", session_id)
            return []

    def get_recent_sessions(self, limit=10):
        """Get the most recent sessions."""
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
                    (limit,)
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch recent sessions.")
            return []

    def get_all_snapshots_last_n_days(self, days=7):
        """Get all snapshots from the last N days for dashboard charts."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()
        try:
            with self._connect() as conn:
                conn.row_factory = sqlite3.Row
                return conn.execute(
                    "SELECT * FROM snapshots WHERE timestamp >= ? ORDER BY timestamp",
                    (cutoff_iso,)
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch snapshots for analytics window (%s days).", days)
            return []

    def get_event_counts_by_type(self, session_id=None):
        """Get event counts grouped by type."""
        try:
            with self._connect() as conn:
                if session_id:
                    return conn.execute(
                        "SELECT event_type, COUNT(*) as count FROM events WHERE session_id = ? GROUP BY event_type",
                        (session_id,)
                    ).fetchall()

                return conn.execute(
                    "SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type"
                ).fetchall()
        except sqlite3.Error:
            logger.exception("Failed to fetch event counts (session_id=%s).", session_id)
            return []

    def get_break_stats(self, session_id=None):
        """Get break statistics."""
        try:
            with self._connect() as conn:
                if session_id:
                    rows = conn.execute(
                        "SELECT * FROM break_events WHERE session_id = ? ORDER BY timestamp",
                        (session_id,)
                    ).fetchall()
                else:
                    rows = conn.execute(
                        "SELECT * FROM break_events ORDER BY timestamp DESC LIMIT 50"
                    ).fetchall()

                total = len(rows)
                total_duration = sum(r[3] for r in rows) if rows else 0
                overdue_count = sum(1 for r in rows if r[4]) if rows else 0

                return {
                    "total_breaks": total,
                    "total_duration": round(total_duration, 0),
                    "overdue_count": overdue_count,
                    "on_time_count": total - overdue_count,
                }
        except sqlite3.Error:
            logger.exception("Failed to fetch break stats.")
            return {"total_breaks": 0, "total_duration": 0, "overdue_count": 0, "on_time_count": 0}
