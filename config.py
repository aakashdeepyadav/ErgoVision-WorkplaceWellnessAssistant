"""
ErgoVision — Configuration & Constants
All detection thresholds, camera settings, and application constants.
"""

import os


def _env_str(name: str, default: str) -> str:
    """Read a non-empty string from env, else fallback to default."""
    value = os.getenv(name)
    if value is None:
        return default

    value = value.strip()
    return value or default


def _env_int(name: str, default: int) -> int:
    """Read an integer from env, else fallback to default."""
    value = os.getenv(name)
    if value is None:
        return default

    try:
        return int(value)
    except ValueError:
        return default


def _env_csv(name: str, default: list[str]) -> list[str]:
    """Read comma-separated values from env, else fallback to default list."""
    value = os.getenv(name)
    if not value:
        return default

    parsed = [item.strip() for item in value.split(",") if item.strip()]
    return parsed or default

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
CAMERA_INDEX = _env_int("ERGOVISION_CAMERA_INDEX", 0)  # Default webcam
CAMERA_WIDTH = _env_int("ERGOVISION_CAMERA_WIDTH", 640)
CAMERA_HEIGHT = _env_int("ERGOVISION_CAMERA_HEIGHT", 480)
TARGET_FPS = _env_int("ERGOVISION_TARGET_FPS", 30)

# ──────────────────────────────────────────────
# API / Runtime Settings
# ──────────────────────────────────────────────
API_HOST = _env_str("ERGOVISION_API_HOST", "0.0.0.0")
API_PORT = _env_int("ERGOVISION_API_PORT", 8000)
LOG_LEVEL = _env_str("ERGOVISION_LOG_LEVEL", "info").lower()
FRONTEND_DEV_PORT = _env_int("ERGOVISION_FRONTEND_DEV_PORT", 5174)

_default_frontend_origin = _env_str(
    "ERGOVISION_FRONTEND_ORIGIN",
    f"http://localhost:{FRONTEND_DEV_PORT}",
)
CORS_ALLOWED_ORIGINS = _env_csv(
    "ERGOVISION_CORS_ALLOWED_ORIGINS",
    [
        _default_frontend_origin,
        f"http://127.0.0.1:{FRONTEND_DEV_PORT}",
        f"http://localhost:{API_PORT}",
        f"http://127.0.0.1:{API_PORT}",
    ],
)
CORS_ALLOW_CREDENTIALS = "*" not in CORS_ALLOWED_ORIGINS

# ──────────────────────────────────────────────
# Database
# ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.abspath(_env_str("ERGOVISION_DATA_DIR", os.path.join(BASE_DIR, "data")))
_default_db_path = os.path.join(DATA_DIR, "wellness.db")
DB_PATH = _env_str("ERGOVISION_DB_PATH", _default_db_path)
if not os.path.isabs(DB_PATH):
    DB_PATH = os.path.abspath(os.path.join(BASE_DIR, DB_PATH))
DB_TIMEOUT_SECONDS = _env_int("ERGOVISION_DB_TIMEOUT_SECONDS", 5)

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
