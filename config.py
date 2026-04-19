"""
ErgoVision — Configuration & Constants
All detection thresholds, camera settings, and application constants.
"""

import os

# ──────────────────────────────────────────────
# Eye Fatigue Detection (EAR)
# ──────────────────────────────────────────────
EAR_THRESHOLD = 0.25           # Below this = eye closed / heavy droop
EAR_CONSEC_FRAMES = 3          # Minimum consecutive frames for a blink
EAR_SMOOTHING_ALPHA = 0.3     # Exponential moving average smoothing
MIN_BLINK_RATE = 5             # Blinks per minute — alert if below this
EAR_BUFFER_SECONDS = 60       # Rolling window for blink rate calculation

# Eye landmark indices (MediaPipe Face Mesh)
LEFT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
RIGHT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

# ──────────────────────────────────────────────
# Posture Detection
# ──────────────────────────────────────────────
POSTURE_OFFSET_THRESHOLD = 40  # Pixels deviation from baseline to trigger alert
POSTURE_CALIBRATION_SECONDS = 30  # Duration of baseline calibration
POSTURE_WARNING_THRESHOLD = 25    # Pixels — WARNING level (before ALERT)

# ──────────────────────────────────────────────
# Screen Distance Detection (Iris Pinhole Model)
# ──────────────────────────────────────────────
IRIS_DIAMETER_MM = 11.7        # Biological constant — universal across humans
MIN_DISTANCE_CM = 50           # Below this = too close alert
DEFAULT_FOCAL_LENGTH_PX = 600  # Default focal length (calibrated at runtime)
DISTANCE_CALIBRATION_CM = 60   # Default calibration distance

# Iris landmark indices (MediaPipe Face Mesh with refine_landmarks=True)
LEFT_IRIS_INDICES = [469, 470, 471, 472]
RIGHT_IRIS_INDICES = [474, 475, 476, 477]

# ──────────────────────────────────────────────
# Mental Fatigue / Yawn Detection (MAR)
# ──────────────────────────────────────────────
MAR_THRESHOLD = 0.6            # Above this = mouth wide open (yawn)
MAR_SUSTAINED_SECONDS = 2.0   # Yawn must last this long
MAX_YAWNS_PER_HOUR = 3         # Alert threshold

# Lip landmark indices for MAR
UPPER_LIP_INDICES = [13, 14]
LOWER_LIP_INDICES = [17, 18]
LEFT_LIP_CORNER = 61
RIGHT_LIP_CORNER = 291
# Full lip contour for MAR: top-center, bottom-center, left-corner, right-corner, upper-inner, lower-inner
LIP_INDICES = [61, 291, 0, 17, 13, 14]

# ──────────────────────────────────────────────
# Alert Engine
# ──────────────────────────────────────────────
ALERT_COOLDOWN_SECONDS = 300   # 5 minutes between same alert type
ALERT_POPUP_DURATION_MS = 8000  # Auto-dismiss popup after 8 seconds

# Alert messages for voice TTS
ALERT_MESSAGES = {
    "EYE_STRAIN": "You have not blinked enough in the last minute. Please rest your eyes and blink slowly.",
    "POOR_POSTURE": "Your posture has drifted. Please sit upright and align your shoulders.",
    "TOO_CLOSE": "You are sitting too close to the screen. Please move back to a comfortable distance.",
    "FATIGUE": "Multiple yawns detected. Consider taking a short break to refresh.",
}

# ──────────────────────────────────────────────
# Camera Settings
# ──────────────────────────────────────────────
CAMERA_INDEX = 0               # Default webcam
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
TARGET_FPS = 30

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "wellness.db")

# ──────────────────────────────────────────────
# UI Colors (for overlay and PyQt6)
# ──────────────────────────────────────────────
COLOR_GOOD = (0, 200, 100)       # Green — BGR for OpenCV
COLOR_WARNING = (0, 180, 255)    # Orange
COLOR_ALERT = (0, 50, 255)       # Red
COLOR_TEXT = (255, 255, 255)     # White
COLOR_BG_OVERLAY = (30, 30, 30)  # Dark background for HUD

# PyQt6 colors (hex)
HEX_PRIMARY = "#6C5CE7"
HEX_ACCENT = "#00CEC9"
HEX_DANGER = "#FF6B6B"
HEX_WARNING = "#FDCB6E"
HEX_SUCCESS = "#00B894"
HEX_BG_DARK = "#1A1A2E"
HEX_BG_CARD = "#16213E"
HEX_TEXT = "#E8E8E8"
