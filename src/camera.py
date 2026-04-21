"""
ErgoVision — Camera Manager
Handles webcam capture and MediaPipe Face Mesh / Pose processing.
"""

import cv2
import mediapipe as mp
import numpy as np
import time

import config


class CameraManager:
    """Manages webcam capture and MediaPipe landmark extraction."""

    def __init__(self):
        self.cap = None
        self.face_mesh = None
        self.pose = None
        self._fps_timer = time.perf_counter()
        self._frame_count = 0
        self._current_fps = 0.0

    def start(self):
        """Initialize webcam and MediaPipe models."""
        if not hasattr(mp, "solutions"):
            raise RuntimeError(
                "Incompatible MediaPipe build detected. Use Python 3.12 with the pinned requirements "
                "(mediapipe==0.10.21)."
            )

        self.cap = cv2.VideoCapture(config.CAMERA_INDEX)
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.TARGET_FPS)

        if not self.cap.isOpened():
            raise RuntimeError("Cannot open webcam. Check camera connection.")

        # Face Mesh with iris landmarks enabled
        self.face_mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,  # Enables iris landmarks (468 → 478)
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

        # Pose for shoulder landmarks
        self.pose = mp.solutions.pose.Pose(
            model_complexity=0,  # Lightweight — fastest
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def read_frame(self):
        """
        Read a frame, process with MediaPipe, return results.
        
        Returns:
            tuple: (frame, face_landmarks, pose_landmarks, fps)
                - frame: BGR numpy array (flipped horizontally)
                - face_landmarks: MediaPipe NormalizedLandmarkList or None
                - pose_landmarks: MediaPipe NormalizedLandmarkList or None
                - fps: current frames per second
        """
        if self.cap is None or not self.cap.isOpened():
            return None, None, None, 0.0

        ret, frame = self.cap.read()
        if not ret:
            return None, None, None, 0.0

        # Mirror view
        frame = cv2.flip(frame, 1)

        # Convert BGR → RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        rgb_frame.flags.writeable = False  # Performance optimization

        # Process face mesh
        face_results = self.face_mesh.process(rgb_frame)
        face_landmarks = None
        if face_results.multi_face_landmarks:
            face_landmarks = face_results.multi_face_landmarks[0]

        # Process pose
        pose_results = self.pose.process(rgb_frame)
        pose_landmarks = None
        if pose_results.pose_landmarks:
            pose_landmarks = pose_results.pose_landmarks

        # Calculate FPS
        self._frame_count += 1
        elapsed = time.perf_counter() - self._fps_timer
        if elapsed >= 1.0:
            self._current_fps = self._frame_count / elapsed
            self._frame_count = 0
            self._fps_timer = time.perf_counter()

        return frame, face_landmarks, pose_landmarks, self._current_fps

    def get_frame_dimensions(self):
        """Return (width, height) of the camera frame."""
        if self.cap is None:
            return config.CAMERA_WIDTH, config.CAMERA_HEIGHT
        w = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        h = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        return w, h

    def stop(self):
        """Release all resources."""
        if self.face_mesh:
            self.face_mesh.close()
        if self.pose:
            self.pose.close()
        if self.cap and self.cap.isOpened():
            self.cap.release()

    def __del__(self):
        self.stop()
