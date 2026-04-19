"""
ErgoVision runtime orchestration.

This module owns the long-running monitoring state (camera, detectors,
calibration/session lifecycle) so the FastAPI layer can stay focused on
transport concerns.
"""

from __future__ import annotations

import base64
import json
import time
from threading import Lock
from typing import Any

import cv2
from fastapi import WebSocket

from .alert_engine import AlertEngine
from .calibration import CalibrationManager
from .camera import CameraManager
from .database import DatabaseManager
from .detectors.distance import DistanceDetector
from .detectors.eye_fatigue import EyeFatigueDetector
from .detectors.fatigue_score import FatigueScoreDetector
from .detectors.posture import PostureDetector
from .session_state import SessionState
from .voice_alert import VoiceAlert


class ErgoVisionRuntime:
    """Coordinates detector state, session lifecycle, and frame processing."""

    def __init__(self):
        self.camera = CameraManager()
        self.eye_detector = EyeFatigueDetector()
        self.posture_detector = PostureDetector()
        self.distance_detector = DistanceDetector()
        self.fatigue_detector = FatigueScoreDetector()
        self.session_state = SessionState()
        self.db = DatabaseManager()
        self.voice = VoiceAlert()
        self.calibration = CalibrationManager(self.posture_detector, self.distance_detector)
        self.alert_engine = AlertEngine(self.session_state, self.voice, self.db)

        self._lifecycle_lock = Lock()
        self._frame_lock = Lock()

        self.ws_clients: set[WebSocket] = set()
        self.is_running = False
        self.current_session_id: int | None = None
        self.snapshot_timer = 0.0

    def bootstrap_calibration(self) -> bool:
        """Load persisted calibration, if present."""
        return self.calibration.load_saved_calibration()

    def add_client(self, websocket: WebSocket) -> None:
        """Register a newly connected client."""
        with self._lifecycle_lock:
            self.ws_clients.add(websocket)

    def remove_client(self, websocket: WebSocket) -> None:
        """Unregister a disconnected client."""
        with self._lifecycle_lock:
            self.ws_clients.discard(websocket)

    def client_count(self) -> int:
        """Return currently connected client count."""
        with self._lifecycle_lock:
            return len(self.ws_clients)

    def ensure_pipeline_started(self) -> None:
        """Start camera/session runtime when first client connects."""
        with self._lifecycle_lock:
            if self.is_running:
                return

            self.camera.start()
            self.is_running = True
            self.current_session_id = self.db.start_session()
            self.alert_engine.set_session_id(self.current_session_id)
            self.snapshot_timer = time.time()

    def stop_pipeline_if_idle(self) -> int | None:
        """Stop camera/session runtime when no clients remain."""
        with self._lifecycle_lock:
            if self.ws_clients or not self.is_running:
                return None

            self.camera.stop()
            self.is_running = False

            ended_session_id = self.current_session_id
            if ended_session_id:
                self.db.end_session(ended_session_id)

            self.current_session_id = None
            return ended_session_id

    @staticmethod
    def _encode_frame(frame: Any) -> str:
        _, buffer = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        return base64.b64encode(buffer).decode("utf-8")

    def process_frame(self) -> tuple[str | None, dict[str, Any]]:
        """Process one frame through calibration/detection pipelines."""
        with self._frame_lock:
            frame, face_landmarks, pose_landmarks, fps = self.camera.read_frame()
            if frame is None:
                return None, {}

            frame_h, frame_w = frame.shape[:2]
            face_detected = face_landmarks is not None
            pose_detected = pose_landmarks is not None

            if not self.calibration.is_complete():
                if self.calibration.phase == "posture" and pose_detected:
                    self.calibration.update_posture_calibration(pose_landmarks, frame_h)
                elif self.calibration.phase == "distance" and face_detected:
                    self.calibration.update_distance_calibration(face_landmarks, frame_w, frame_h)
                elif self.calibration.phase == "posture_done":
                    self.calibration.start_distance_calibration()

                self.session_state.update(
                    is_calibrating=True,
                    face_detected=face_detected,
                    pose_detected=pose_detected,
                    fps=fps,
                )

                return self._encode_frame(frame), {
                    "type": "calibration",
                    "phase": self.calibration.phase,
                    "progress": self.calibration.progress,
                    "message": self.calibration.status_message,
                    "face_detected": face_detected,
                    "pose_detected": pose_detected,
                    "fps": round(fps, 1),
                }

            if face_detected:
                self.eye_detector.update(face_landmarks, frame_w, frame_h)
                self.distance_detector.update(face_landmarks, frame_w, frame_h)
                self.fatigue_detector.update(
                    face_landmarks,
                    frame_w,
                    frame_h,
                    self.eye_detector.blink_count_per_min,
                )

            if pose_detected:
                self.posture_detector.update(pose_landmarks, frame_h)

            eye_status = self.eye_detector.get_status()
            posture_status = self.posture_detector.get_status()
            distance_status = self.distance_detector.get_status()
            fatigue_status = self.fatigue_detector.get_status()

            self.session_state.update(
                ear=eye_status["ear"],
                blink_rate=eye_status["blink_rate"],
                eyes_closed=eye_status["eyes_closed"],
                eye_alert=eye_status["alert"],
                eye_reason=eye_status["reason"],
                posture_offset=posture_status["offset"],
                posture_baseline=posture_status["baseline"],
                posture_deviation=posture_status["deviation"],
                posture_status=posture_status["status"],
                posture_alert=posture_status["alert"],
                posture_reason=posture_status["reason"],
                posture_calibrated=posture_status["calibrated"],
                distance_cm=distance_status["distance_cm"],
                iris_px=distance_status["iris_px"],
                distance_alert=distance_status["alert"],
                distance_reason=distance_status["reason"],
                distance_calibrated=distance_status["calibrated"],
                mar=fatigue_status["mar"],
                yawn_count=fatigue_status["yawn_count"],
                fatigue_score=fatigue_status["fatigue_score"],
                fatigue_alert=fatigue_status["alert"],
                fatigue_reason=fatigue_status["reason"],
                fps=fps,
                face_detected=face_detected,
                pose_detected=pose_detected,
                is_monitoring=True,
                is_calibrating=False,
            )

            fired = self.alert_engine.check()

            now = time.time()
            if self.current_session_id and (now - self.snapshot_timer) >= 30:
                self.snapshot_timer = now
                self.db.log_snapshot(
                    self.current_session_id,
                    eye_status["ear"],
                    eye_status["blink_rate"],
                    posture_status["deviation"],
                    distance_status["distance_cm"],
                    fatigue_status["fatigue_score"],
                )

            data = {
                "type": "detection",
                "eye": eye_status,
                "posture": posture_status,
                "distance": distance_status,
                "fatigue": fatigue_status,
                "fps": round(fps, 1),
                "face_detected": face_detected,
                "pose_detected": pose_detected,
                "alerts_fired": fired,
            }

            return self._encode_frame(frame), data

    def _apply_settings(self, settings: dict[str, Any]) -> None:
        """Update runtime detector/alert settings from UI payload."""
        if "ear_threshold" in settings:
            self.eye_detector.ear_threshold = float(settings["ear_threshold"])
        if "min_blink_rate" in settings:
            self.eye_detector.min_blink_rate = int(settings["min_blink_rate"])
        if "posture_threshold" in settings:
            self.posture_detector.offset_threshold = float(settings["posture_threshold"])
        if "min_distance" in settings:
            self.distance_detector.min_distance_cm = float(settings["min_distance"])
        if "voice_enabled" in settings:
            self.voice.enabled = bool(settings["voice_enabled"])
        if "cooldown_minutes" in settings:
            self.alert_engine.cooldown_seconds = int(settings["cooldown_minutes"]) * 60

    async def handle_client_message(self, raw_message: str) -> None:
        """Handle a command message from the React dashboard."""
        try:
            data = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        command = data.get("command")

        if command == "start_calibration":
            self.calibration.start_posture_calibration()
            return

        if command == "skip_calibration":
            self.calibration.skip_calibration()
            return

        if command == "recalibrate":
            self.calibration.start_posture_calibration()
            return

        if command == "toggle_voice":
            self.voice.toggle()
            return

        if command == "update_settings":
            settings = data.get("settings", {})
            try:
                self._apply_settings(settings)
            except (TypeError, ValueError):
                # Ignore malformed values and keep current runtime defaults.
                return
