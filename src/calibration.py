"""
ErgoVision — Calibration Manager
Handles posture baseline and distance focal length calibration routines.
"""

import time
import json
import os

import config


class CalibrationManager:
    """
    Manages the startup calibration process:
    1. Posture baseline: 30-second sampling of correct sitting position
    2. Distance calibration: iris width at known distance for focal length
    
    Calibration data is saved to a JSON file so it persists across sessions.
    """

    CALIBRATION_FILE = os.path.join(config.BASE_DIR, "data", "calibration.json")

    def __init__(self, posture_detector, distance_detector):
        """
        Args:
            posture_detector: PostureDetector instance
            distance_detector: DistanceDetector instance
        """
        self.posture = posture_detector
        self.distance = distance_detector

        # Calibration state
        self.phase = "idle"  # idle, posture, distance, complete
        self.start_time = None
        self.posture_duration = config.POSTURE_CALIBRATION_SECONDS
        self.progress = 0.0  # 0.0 to 1.0
        self.status_message = ""

    def load_saved_calibration(self):
        """
        Attempt to load previous calibration data.
        
        Returns:
            bool: True if calibration was loaded successfully
        """
        if not os.path.exists(self.CALIBRATION_FILE):
            return False

        try:
            with open(self.CALIBRATION_FILE, "r") as f:
                data = json.load(f)

            if "posture_baseline" in data:
                self.posture.baseline_offset = data["posture_baseline"]
                self.posture.is_calibrated = True

            if "focal_length" in data:
                self.distance.focal_length_px = data["focal_length"]
                self.distance.is_calibrated = True

            self.phase = "complete"
            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def save_calibration(self):
        """Save current calibration data to disk."""
        os.makedirs(os.path.dirname(self.CALIBRATION_FILE), exist_ok=True)
        data = {
            "posture_baseline": self.posture.baseline_offset,
            "focal_length": self.distance.focal_length_px,
            "calibrated_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        }
        with open(self.CALIBRATION_FILE, "w") as f:
            json.dump(data, f, indent=2)

    def start_posture_calibration(self):
        """Begin the posture calibration phase."""
        self.posture.reset_calibration()
        self.phase = "posture"
        self.start_time = time.time()
        self.progress = 0.0
        self.status_message = "Sit upright in your natural good posture..."

    def start_distance_calibration(self):
        """Begin the distance calibration phase."""
        self.distance.reset_calibration()
        self.phase = "distance"
        self.start_time = time.time()
        self.progress = 0.0
        self.status_message = "Sit at arm's length (~60cm) from the screen..."

    def update_posture_calibration(self, pose_landmarks, frame_h):
        """
        Feed a frame into posture calibration.
        
        Args:
            pose_landmarks: MediaPipe pose landmarks
            frame_h: frame height
            
        Returns:
            bool: True if calibration phase is complete
        """
        if self.phase != "posture":
            return False

        elapsed = time.time() - self.start_time
        self.progress = min(1.0, elapsed / self.posture_duration)
        
        sample_count = self.posture.add_calibration_sample(pose_landmarks, frame_h)
        self.status_message = f"Calibrating posture... {self.progress*100:.0f}% ({sample_count} samples)"

        if elapsed >= self.posture_duration:
            success = self.posture.finish_calibration()
            if success:
                self.phase = "posture_done"
                self.status_message = "Posture calibration complete!"
                return True
            else:
                self.status_message = "Calibration failed — not enough samples. Retrying..."
                self.start_posture_calibration()

        return False

    def update_distance_calibration(self, face_landmarks, frame_w, frame_h):
        """
        Feed a frame into distance calibration.
        
        Args:
            face_landmarks: MediaPipe face landmarks
            frame_w, frame_h: frame dimensions
            
        Returns:
            bool: True if calibration phase is complete
        """
        if self.phase != "distance":
            return False

        elapsed = time.time() - self.start_time
        self.progress = min(1.0, elapsed / 10.0)  # 10 seconds for distance

        sample_count = self.distance.add_calibration_sample(face_landmarks, frame_w, frame_h)
        self.status_message = f"Calibrating distance... {self.progress*100:.0f}% ({sample_count} samples)"

        if elapsed >= 10.0:
            success = self.distance.finish_calibration()
            if success:
                self.save_calibration()
                self.phase = "complete"
                self.status_message = "All calibration complete!"
                return True
            else:
                self.status_message = "Distance calibration failed. Retrying..."
                self.start_distance_calibration()

        return False

    def skip_calibration(self):
        """Skip calibration and use defaults."""
        if not self.posture.is_calibrated:
            self.posture.baseline_offset = 0
            self.posture.is_calibrated = True
        self.phase = "complete"
        self.status_message = "Using default calibration values."

    def is_complete(self):
        """Check if all calibration is done."""
        return self.phase == "complete"

    def needs_calibration(self):
        """Check if calibration is needed."""
        return not self.posture.is_calibrated or not self.distance.is_calibrated
