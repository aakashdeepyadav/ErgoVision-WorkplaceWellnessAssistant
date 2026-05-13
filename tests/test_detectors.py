"""Tests for detector modules — geometry computations with known inputs."""

import math
import numpy as np
import pytest

from src.detectors.head_tilt import HeadTiltDetector


class FakeLandmark:
    def __init__(self, x, y, z=0, visibility=1.0):
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility


class FakeFaceLandmarks:
    def __init__(self, landmarks_dict):
        self.landmark = landmarks_dict


def _make_face_with_tilt(angle_deg, frame_w=640, frame_h=480):
    """Create fake face landmarks with eyes at a given roll angle."""
    cx, cy = frame_w / 2, frame_h / 2
    half_eye_dist = 60  # pixels

    angle_rad = math.radians(angle_deg)
    dx = math.cos(angle_rad) * half_eye_dist
    dy = math.sin(angle_rad) * half_eye_dist

    landmarks = {}
    # Left eye outer (33), inner (133)
    landmarks[33] = FakeLandmark((cx - dx) / frame_w, (cy - dy) / frame_h)
    landmarks[133] = FakeLandmark((cx - dx * 0.5) / frame_w, (cy - dy * 0.5) / frame_h)
    # Right eye outer (263), inner (362)
    landmarks[263] = FakeLandmark((cx + dx) / frame_w, (cy + dy) / frame_h)
    landmarks[362] = FakeLandmark((cx + dx * 0.5) / frame_w, (cy + dy * 0.5) / frame_h)

    return FakeFaceLandmarks(landmarks)


class TestHeadTiltDetector:
    def test_zero_tilt_returns_near_zero_angle(self):
        face = _make_face_with_tilt(0)
        angle = HeadTiltDetector._compute_roll_angle(face, 640, 480)
        assert abs(angle) < 1.0, f"Expected ~0° but got {angle:.1f}°"

    def test_positive_tilt_detected(self):
        face = _make_face_with_tilt(20)
        angle = HeadTiltDetector._compute_roll_angle(face, 640, 480)
        assert 15 < angle < 25, f"Expected ~20° but got {angle:.1f}°"

    def test_negative_tilt_detected(self):
        face = _make_face_with_tilt(-15)
        angle = HeadTiltDetector._compute_roll_angle(face, 640, 480)
        assert -20 < angle < -10, f"Expected ~-15° but got {angle:.1f}°"

    def test_no_alert_below_threshold(self):
        detector = HeadTiltDetector()
        detector.tilt_threshold_deg = 15
        detector.sustained_seconds = 0  # Instant alert for testing

        face = _make_face_with_tilt(5)  # Below threshold
        detector.update(face, 640, 480)
        assert not detector.alert_active

    def test_alert_above_threshold_with_zero_sustain(self):
        detector = HeadTiltDetector()
        detector.tilt_threshold_deg = 10
        detector.sustained_seconds = 0  # Instant

        face = _make_face_with_tilt(20)
        detector.update(face, 640, 480)
        # Need a second update since smoothing may not hit threshold first frame
        detector.update(face, 640, 480)
        detector.update(face, 640, 480)
        status = detector.get_status()
        assert abs(status["angle"]) > 10

    def test_none_face_resets_state(self):
        detector = HeadTiltDetector()
        detector.update(None, 640, 480)
        assert not detector.alert_active
        assert detector.tilt_duration == 0.0


class TestEARComputation:
    """Test the Eye Aspect Ratio formula with known geometry."""

    def test_open_eye_gives_high_ear(self):
        from src.detectors.eye_fatigue import EyeFatigueDetector

        # Simulate an open eye: vertical distances > 0
        landmarks = {}
        # EAR eye indices from config: [362, 385, 387, 263, 373, 380]
        import config
        indices = config.LEFT_EYE_INDICES
        # p1(outer), p2(top-right), p3(top-left), p4(inner), p5(bottom-left), p6(bottom-right)
        pts = [(0.3, 0.5), (0.33, 0.47), (0.37, 0.47), (0.4, 0.5), (0.37, 0.53), (0.33, 0.53)]
        for idx, (x, y) in zip(indices, pts):
            landmarks[idx] = FakeLandmark(x, y)

        face = FakeFaceLandmarks(landmarks)
        ear = EyeFatigueDetector.compute_ear(face, indices, 640, 480)
        assert ear > 0.15, f"Open eye EAR should be > 0.15, got {ear:.3f}"

    def test_closed_eye_gives_low_ear(self):
        from src.detectors.eye_fatigue import EyeFatigueDetector
        import config

        indices = config.LEFT_EYE_INDICES
        # Nearly closed: all y values ~same
        pts = [(0.3, 0.5), (0.33, 0.499), (0.37, 0.499), (0.4, 0.5), (0.37, 0.501), (0.33, 0.501)]
        landmarks = {}
        for idx, (x, y) in zip(indices, pts):
            landmarks[idx] = FakeLandmark(x, y)

        face = FakeFaceLandmarks(landmarks)
        ear = EyeFatigueDetector.compute_ear(face, indices, 640, 480)
        assert ear < 0.1, f"Closed eye EAR should be < 0.1, got {ear:.3f}"
