"""
ErgoVision — Screen Distance Detector (Iris Pinhole Model)
Estimates user's distance from screen using iris diameter as a biological constant.
"""

import numpy as np

import config


class DistanceDetector:
    """
    Estimates distance from screen using the pinhole camera model
    and the biological constant that the human iris is 11.7mm in diameter.
    
    Distance (cm) = (focal_length_px × 11.7mm) / iris_width_px
    """

    def __init__(self):
        self.iris_diameter_mm = config.IRIS_DIAMETER_MM
        self.min_distance_cm = config.MIN_DISTANCE_CM
        self.focal_length_px = config.DEFAULT_FOCAL_LENGTH_PX

        # Calibration
        self.is_calibrated = False
        self._calibration_samples = []
        self._calibration_distance_cm = config.DISTANCE_CALIBRATION_CM

        # Current readings
        self.current_distance_cm = 0.0
        self.iris_width_px = 0.0
        self.alert_active = False
        self.alert_reason = ""

    @staticmethod
    def _get_iris_width(face_landmarks, iris_indices, frame_w, frame_h):
        """
        Compute the pixel width of the iris.
        
        Args:
            face_landmarks: MediaPipe face landmarks
            iris_indices: list of 4 iris landmark indices
            frame_w: frame width
            frame_h: frame height
            
        Returns:
            float: iris width in pixels
        """
        points = []
        for idx in iris_indices:
            lm = face_landmarks.landmark[idx]
            points.append(np.array([lm.x * frame_w, lm.y * frame_h]))

        # Iris landmarks form a diamond shape:
        # index 0: right edge, 1: top, 2: left edge, 3: bottom
        # Width = distance between left and right edges (indices 0 and 2)
        width = np.linalg.norm(points[0] - points[2])
        return width

    def add_calibration_sample(self, face_landmarks, frame_w, frame_h):
        """
        Collect an iris width sample during calibration.
        
        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions
            
        Returns:
            int: number of samples collected
        """
        if face_landmarks is None:
            return len(self._calibration_samples)

        left_width = self._get_iris_width(
            face_landmarks, config.LEFT_IRIS_INDICES, frame_w, frame_h
        )
        right_width = self._get_iris_width(
            face_landmarks, config.RIGHT_IRIS_INDICES, frame_w, frame_h
        )

        avg_width = (left_width + right_width) / 2.0
        if avg_width > 0:
            self._calibration_samples.append(avg_width)

        return len(self._calibration_samples)

    def finish_calibration(self, known_distance_cm=None):
        """
        Compute focal length from calibration samples.
        
        focal_length_px = (mean_iris_width_px × known_distance_cm) / iris_diameter_mm
        
        Args:
            known_distance_cm: the distance the user sat at during calibration
            
        Returns:
            bool: True if calibration succeeded
        """
        if len(self._calibration_samples) < 10:
            return False

        dist = known_distance_cm or self._calibration_distance_cm
        mean_width = np.mean(self._calibration_samples)

        self.focal_length_px = (mean_width * dist) / self.iris_diameter_mm
        self.is_calibrated = True
        self._calibration_samples = []
        return True

    def reset_calibration(self):
        """Reset to default focal length."""
        self.focal_length_px = config.DEFAULT_FOCAL_LENGTH_PX
        self.is_calibrated = False
        self._calibration_samples = []

    def update(self, face_landmarks, frame_w, frame_h):
        """
        Estimate distance from the current frame.
        
        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions
        """
        if face_landmarks is None:
            self.alert_active = False
            return

        left_width = self._get_iris_width(
            face_landmarks, config.LEFT_IRIS_INDICES, frame_w, frame_h
        )
        right_width = self._get_iris_width(
            face_landmarks, config.RIGHT_IRIS_INDICES, frame_w, frame_h
        )

        self.iris_width_px = (left_width + right_width) / 2.0

        if self.iris_width_px <= 0:
            return

        # Pinhole camera model
        self.current_distance_cm = (
            self.focal_length_px * self.iris_diameter_mm
        ) / self.iris_width_px

        # Alert logic
        self.alert_active = False
        self.alert_reason = ""

        if self.current_distance_cm < self.min_distance_cm:
            self.alert_active = True
            self.alert_reason = (
                f"Too close: {self.current_distance_cm:.0f}cm "
                f"(min: {self.min_distance_cm}cm)"
            )

    def get_status(self):
        """
        Returns current detector status.
        
        Returns:
            dict with keys: distance_cm, iris_px, focal_length, alert, reason, calibrated
        """
        return {
            "distance_cm": round(self.current_distance_cm, 1),
            "iris_px": round(self.iris_width_px, 1),
            "focal_length": round(self.focal_length_px, 1),
            "alert": self.alert_active,
            "reason": self.alert_reason,
            "calibrated": self.is_calibrated,
        }
