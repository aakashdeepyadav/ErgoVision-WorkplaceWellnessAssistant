"""
ErgoVision — Database Manager
SQLite schema and CRUD operations for session logging.
"""

import logging
import os
import sqlite3
from datetime import datetime

import config


logger = logging.getLogger("ergovision.database")


class DatabaseManager:
    """Manages SQLite storage for wellness sessions and events."""

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
                        FOREIGN KEY (session_id) REFERENCES sessions(id)
                    )
                """)
                conn.commit()
        except sqlite3.Error:
            logger.exception("Failed to initialize database schema at '%s'.", self.db_path)
            raise

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
            event_type: one of EYE_STRAIN, POOR_POSTURE, TOO_CLOSE, FATIGUE
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

    def log_snapshot(self, session_id, ear, blink_rate, posture_deviation, distance_cm, fatigue_score):
        """
        Log a periodic health snapshot (every 30 seconds).
        
        Args:
            session_id: current session ID
            ear: current EAR value
            blink_rate: blinks per minute
            posture_deviation: pixels from baseline
            distance_cm: screen distance
            fatigue_score: composite fatigue 0-100
        """
        if not session_id:
            return False

        now = datetime.now().isoformat()
        try:
            with self._connect() as conn:
                conn.execute(
                    """INSERT INTO snapshots 
                       (session_id, timestamp, ear, blink_rate, posture_deviation, distance_cm, fatigue_score) 
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (session_id, now, ear, blink_rate, posture_deviation, distance_cm, fatigue_score)
                )
                conn.commit()
                return True
        except sqlite3.Error:
            logger.exception("Failed to log snapshot for session '%s'.", session_id)
            return False

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
