"""
ErgoVision — Database Manager
SQLite schema and CRUD operations for session logging.
"""

import os
import sqlite3
import time
from datetime import datetime

import config


class DatabaseManager:
    """Manages SQLite storage for wellness sessions and events."""

    def __init__(self, db_path=None):
        self.db_path = db_path or config.DB_PATH
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Create tables if they don't exist."""
        with sqlite3.connect(self.db_path) as conn:
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

    def start_session(self):
        """
        Start a new monitoring session.
        
        Returns:
            int: session ID
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "INSERT INTO sessions (start_time) VALUES (?)",
                (now,)
            )
            conn.commit()
            return cursor.lastrowid

    def end_session(self, session_id):
        """End a monitoring session."""
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
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

    def log_event(self, session_id, event_type, value=None, details=None):
        """
        Log a wellness event (alert triggered, etc.)
        
        Args:
            session_id: current session ID
            event_type: one of EYE_STRAIN, POOR_POSTURE, TOO_CLOSE, FATIGUE
            value: numeric value associated with the event
            details: additional text details
        """
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "INSERT INTO events (session_id, timestamp, event_type, value, details) VALUES (?, ?, ?, ?, ?)",
                (session_id, now, event_type, value, details)
            )
            conn.commit()

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
        now = datetime.now().isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT INTO snapshots 
                   (session_id, timestamp, ear, blink_rate, posture_deviation, distance_cm, fatigue_score) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, now, ear, blink_rate, posture_deviation, distance_cm, fatigue_score)
            )
            conn.commit()

    def get_session_events(self, session_id):
        """Get all events for a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM events WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            ).fetchall()

    def get_session_snapshots(self, session_id):
        """Get all snapshots for a session."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM snapshots WHERE session_id = ? ORDER BY timestamp",
                (session_id,)
            ).fetchall()

    def get_recent_sessions(self, limit=10):
        """Get the most recent sessions."""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM sessions ORDER BY start_time DESC LIMIT ?",
                (limit,)
            ).fetchall()

    def get_all_snapshots_last_n_days(self, days=7):
        """Get all snapshots from the last N days for dashboard charts."""
        cutoff = datetime.now().timestamp() - (days * 86400)
        cutoff_iso = datetime.fromtimestamp(cutoff).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(
                "SELECT * FROM snapshots WHERE timestamp >= ? ORDER BY timestamp",
                (cutoff_iso,)
            ).fetchall()

    def get_event_counts_by_type(self, session_id=None):
        """Get event counts grouped by type."""
        with sqlite3.connect(self.db_path) as conn:
            if session_id:
                return conn.execute(
                    "SELECT event_type, COUNT(*) as count FROM events WHERE session_id = ? GROUP BY event_type",
                    (session_id,)
                ).fetchall()
            else:
                return conn.execute(
                    "SELECT event_type, COUNT(*) as count FROM events GROUP BY event_type"
                ).fetchall()
