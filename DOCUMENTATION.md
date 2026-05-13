# ErgoVision — Complete Project Documentation

## 1. Project Overview

**ErgoVision** is a real-time workstation wellness monitoring system that uses a standard webcam to track six health signals and provide immediate corrective alerts. It is built with a **zero-ML, geometry-first** philosophy — all detection relies on MediaPipe landmark coordinates and mathematical formulas (EAR, MAR, pinhole model, trigonometry), not trained classifiers.

### Core Value Proposition
- Prevents repetitive strain injuries (RSI) during prolonged computer use
- Runs 100% locally — zero data leaves the machine
- Works with any standard webcam, no special hardware needed
- Real-time feedback loop: detect → alert → correct → track improvement

### Technology Stack
| Layer | Technology | Version |
|-------|-----------|---------|
| CV Engine | MediaPipe Face Mesh + Pose | 0.10.21 |
| Frame I/O | OpenCV (cv2) | Latest |
| Backend API | FastAPI + Uvicorn | ≥0.100.0 |
| Transport | WebSocket (real-time) + REST (analytics) | — |
| Database | SQLite with WAL mode | Built-in |
| Voice Alerts | pyttsx3 (offline TTS) | ≥2.90 |
| Frontend | React 19 + Vite 8 | Latest |
| Charts | Recharts 3 | 3.8.1 |
| Icons | Lucide React | 1.8.0 |
| Testing | Pytest (backend), ESLint (frontend) | ≥7.0 |

---

## 2. System Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                        React Dashboard                          │
│  ┌─────────┐ ┌──────────┐ ┌───────────┐ ┌──────────────────┐   │
│  │ Webcam  │ │ Metric   │ │ Wellness  │ │ Analytics Modal  │   │
│  │ Feed    │ │ Cards x5 │ │ Ring      │ │ (Recharts)       │   │
│  └─────────┘ └──────────┘ └───────────┘ └──────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌─────────────────┐   │
│  │ Gaze     │ │ Break    │ │ Settings  │ │ Alert Feed      │   │
│  │ Indicator│ │ Reminder │ │ Drawer    │ │ + Toast System  │   │
│  └──────────┘ └──────────┘ └───────────┘ └─────────────────┘   │
└───────────────────────┬──────────────────────────────────────────┘
                        │ WebSocket (JSON + base64 JPEG)
┌───────────────────────▼──────────────────────────────────────────┐
│                     FastAPI Server (server.py)                    │
│  WebSocket /ws  │  REST /api/*  │  CORS  │  Lifecycle Mgmt      │
└───────────────────────┬──────────────────────────────────────────┘
                        │
┌───────────────────────▼──────────────────────────────────────────┐
│                  Runtime Orchestrator (runtime.py)                │
│  Camera ──► MediaPipe ──► Detectors ──► SessionState ──► Alerts  │
│                              │              │              │     │
│                              ▼              ▼              ▼     │
│                     ┌─────────────┐  ┌──────────┐  ┌──────────┐ │
│                     │ Break Mgr   │  │ Prod.    │  │ SQLite   │ │
│                     │ 20-20-20    │  │ Tracker  │  │ Database │ │
│                     └─────────────┘  └──────────┘  └──────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Data Flow Per Frame
1. `CameraManager` captures a frame via OpenCV and runs MediaPipe Face Mesh + Pose
2. `runtime.py` distributes landmarks to all 5 detector modules
3. Each detector computes its metric and sets alert flags
4. `BreakManager` tracks time since last break, `ProductivityTracker` logs state
5. `SessionState` is atomically updated with all readings
6. `AlertEngine` checks all flags against cooldown policy
7. Frame is JPEG-encoded to base64 and sent with detection data via WebSocket
8. Every 30 seconds, a snapshot is persisted to SQLite

---

## 3. Detection Modules (Zero-ML Geometry)

### 3.1 Eye Fatigue Detector (`src/detectors/eye_fatigue.py`)

**Purpose:** Monitors blink rate and detects prolonged staring.

**EAR Formula (Eye Aspect Ratio):**
```
EAR = (||p2-p6|| + ||p3-p5||) / (2 × ||p1-p4||)
```
- Uses 6 landmarks per eye from MediaPipe Face Mesh
- Open eye ≈ 0.25–0.35, closed eye < 0.2
- A blink = EAR dips below threshold then recovers (minimum consecutive frames)
- Rolling 60-second window counts blinks per minute

**Gaze Direction:**
- Computes iris center position relative to eye socket bounds
- Outputs `gaze_x` (-1=left, 0=center, 1=right) and `gaze_y` (-1=up, 1=down)

**Prolonged Stare Detection:**
- Tracks iris center movement between frames
- If movement < `GAZE_MOVEMENT_THRESHOLD` (0.015) for > `GAZE_STARE_SECONDS` (30s), fires stare alert
- Natural saccades (involuntary eye movements) reset the timer

**Alert Conditions:**
- Blink rate < `MIN_BLINK_RATE` (5/min)
- Eyes closed > 1.5 seconds
- Prolonged stare > 30 seconds

**Configuration:** `EAR_THRESHOLD`, `EAR_CONSEC_FRAMES`, `EAR_BUFFER_SECONDS`, `MIN_BLINK_RATE`, `EAR_SMOOTHING_ALPHA`, `GAZE_STARE_SECONDS`, `GAZE_MOVEMENT_THRESHOLD`

---

### 3.2 Posture Detector (`src/detectors/posture.py`)

**Purpose:** Detects slouching, shoulder asymmetry, and forward lean.

**Slouch Detection:**
```
offset = nose_y - mean(left_shoulder_y, right_shoulder_y)
deviation = |offset - calibrated_baseline|
```
- Uses MediaPipe Pose landmarks (nose=0, shoulders=11,12)
- Requires calibration phase to establish personal baseline
- `POSTURE_OFFSET_THRESHOLD` (40px) = ALERT, `POSTURE_WARNING_THRESHOLD` (25px) = WARNING

**Shoulder Asymmetry:**
- Measures Y-difference between left and right shoulders
- Alerts when asymmetry exceeds baseline + 18px

**Multi-Status Output:** `GOOD`, `WARNING`, `ALERT`, `UNCALIBRATED`

**Issues Tracked:** `slouch`, `slight_slouch`, `shoulder_tilt`

**Configuration:** `POSTURE_OFFSET_THRESHOLD`, `POSTURE_WARNING_THRESHOLD`, `POSTURE_CALIBRATION_SECONDS`

---

### 3.3 Distance Detector (`src/detectors/distance.py`)

**Purpose:** Estimates screen-to-face distance using iris diameter.

**Pinhole Camera Model:**
```
distance_cm = (IRIS_DIAMETER_MM × focal_length_px) / (iris_width_px × 10)
```
- `IRIS_DIAMETER_MM = 11.7` — biological constant, universal across humans
- Focal length is calibrated during setup (user sits at known distance)
- Uses 4 iris landmarks per eye from MediaPipe Face Mesh (refine_landmarks=True)

**Alert Condition:** Distance < `MIN_DISTANCE_CM` (50cm)

**Configuration:** `IRIS_DIAMETER_MM`, `MIN_DISTANCE_CM`, `DEFAULT_FOCAL_LENGTH_PX`, `DISTANCE_CALIBRATION_CM`, `LEFT_IRIS_INDICES`, `RIGHT_IRIS_INDICES`

---

### 3.4 Fatigue Score Detector (`src/detectors/fatigue_score.py`)

**Purpose:** Detects yawns via MAR and computes weighted composite fatigue score.

**MAR Formula (Mouth Aspect Ratio):**
```
MAR = (||top-bottom|| + ||upper_inner-lower_inner||) / (2 × ||left_corner-right_corner||)
```
- Yawn = MAR > 0.6 sustained for 2+ seconds
- Tracks yawns per hour

**Composite Fatigue Score (0–100):**
| Factor | Weight | Source |
|--------|--------|--------|
| Low blink rate | 0–30 pts | EyeFatigueDetector |
| Yawn frequency | 0–30 pts | MAR yawn count |
| Session duration | 0–20 pts | Time-weighted (ramps over 2 hours) |
| Head tilt | 0–20 pts | HeadTiltDetector angle |

**Fatigue Trend:** Compares first-half vs second-half of recent score history → `rising`, `falling`, `stable`

**Configuration:** `MAR_THRESHOLD`, `MAR_SUSTAINED_SECONDS`, `MAX_YAWNS_PER_HOUR`

---

### 3.5 Head Tilt Detector (`src/detectors/head_tilt.py`)

**Purpose:** Detects sustained head roll (neck strain from tilting).

**Roll Angle Computation:**
```
angle = atan2(right_eye_y - left_eye_y, right_eye_x - left_eye_x)
```
- Uses outer (33, 263) and inner (133, 362) eye corner landmarks
- Averages both pairs for robustness
- Exponential smoothing (alpha=0.3) to reduce jitter

**Direction:** `center` (|angle|<3°), `left` (angle<-3°), `right` (angle>3°)

**Alert Condition:** |angle| > `HEAD_TILT_THRESHOLD_DEG` (15°) sustained for > `HEAD_TILT_SUSTAINED_SECONDS` (10s)

**Configuration:** `HEAD_TILT_THRESHOLD_DEG`, `HEAD_TILT_SUSTAINED_SECONDS`

---

## 4. Support Systems

### 4.1 Break Manager (`src/break_manager.py`)

Implements the **20-20-20 rule**: every 20 minutes, look 20 feet away for 20 seconds.

**Features:**
- Adaptive intervals — shortens to 70% when fatigue > 60, 85% when fatigue > 40
- Natural break detection — face disappearing for > 20s = automatic break logged
- Manual acknowledgment via UI button
- Compliance scoring (0–100) based on expected vs actual breaks, with overdue penalties
- Break overdue = 1.5× the interval without a break

### 4.2 Productivity Tracker (`src/productivity_tracker.py`)

Tracks three states per frame:
- **Healthy**: face detected, no alerts active
- **Degraded**: face detected, one or more alerts active
- **Absent**: face not detected

Computes session wellness-productivity score: `(healthy_time / active_time) × 100`

Per-minute samples stored for hourly trend charts.

### 4.3 Alert Engine (`src/alert_engine.py`)

**7 Alert Types:**
| Type | Trigger | Default Cooldown |
|------|---------|-----------------|
| `EYE_STRAIN` | Low blink rate | 5 min |
| `POOR_POSTURE` | Slouch/shoulder tilt | 5 min |
| `TOO_CLOSE` | Distance < threshold | 5 min |
| `FATIGUE` | High fatigue score / yawns | 5 min |
| `HEAD_TILT` | Sustained head roll | 5 min |
| `PROLONGED_STARE` | No saccade detected | 5 min |
| `TAKE_BREAK` | Break overdue | 5 min |

**Progressive Escalation:** When alerts are ignored (same alert fires but is within cooldown), the cooldown multiplier reduces: 100% → 70% → 50%. Resets on successful fire.

**Dispatch Chain:** Alert → Log to SQLite → Voice TTS (pyttsx3) → WebSocket push → Toast notification

### 4.4 Calibration System (`src/calibration.py`)

Two-phase calibration:
1. **Posture phase** (30s): User sits naturally. Collects nose-shoulder offset samples to establish baseline.
2. **Distance phase** (30s): User sits at arm's length. Computes focal length from known iris diameter.

Persists to `data/calibration.json`. Loaded on server restart — no recalibration needed between sessions.

Can be triggered via UI button or `POST /api/recalibrate`.

### 4.5 Voice Alerts (`src/voice_alert.py`)

- Offline TTS via `pyttsx3` — no internet required
- Non-blocking: runs in a background thread with a queue
- Toggle on/off from the dashboard settings
- Custom messages per alert type defined in `config.ALERT_MESSAGES`

### 4.6 Session State (`src/session_state.py`)

Thread-safe shared state container with 40+ fields. All detectors write, alert engine and UI read. Uses `threading.Lock` for atomic updates.

Key field groups: eye metrics, gaze tracking, posture metrics, distance, fatigue, head tilt, break status, productivity, system (FPS, face/pose detected, monitoring flags).

### 4.7 Database (`src/database.py`)

SQLite with WAL journal mode for concurrent read/write.

**Tables:**
| Table | Purpose | Key Columns |
|-------|---------|-------------|
| `sessions` | Monitoring session lifecycle | start_time, end_time, duration_minutes |
| `events` | Alert occurrences | session_id, event_type, value, details |
| `snapshots` | 30-second health readings | ear, blink_rate, posture_deviation, distance_cm, fatigue_score, head_tilt, gaze_x, gaze_y |
| `break_events` | Break occurrences | duration_seconds, was_overdue |
| `daily_summaries` | Aggregated daily metrics | avg_blink_rate, avg_posture_deviation, total_alerts, breaks_taken, wellness_score |

Auto-migration adds new columns to existing databases safely.

---

## 5. API Reference

### WebSocket
| Endpoint | Description |
|----------|-------------|
| `WS /ws` | Main monitoring stream. Sends JSON with `frame` (base64 JPEG) and `data` (detection payload) per frame. First client triggers pipeline start; last disconnect stops it. |

**Client Commands (JSON via WebSocket):**
| Command | Payload | Effect |
|---------|---------|--------|
| `start_calibration` | — | Begin posture calibration |
| `skip_calibration` | — | Use default values |
| `recalibrate` | — | Restart calibration |
| `toggle_voice` | — | Toggle voice alerts |
| `acknowledge_break` | — | Log break taken |
| `update_settings` | `{settings: {...}}` | Update thresholds at runtime |

### REST Endpoints
| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Full session state snapshot |
| GET | `/api/health` | Pipeline readiness probe |
| GET | `/api/sessions` | Last 20 sessions |
| GET | `/api/sessions/{id}/events` | Alert events for session |
| GET | `/api/sessions/{id}/snapshots` | Health snapshots for session |
| GET | `/api/analytics` | 7-day snapshots + event counts |
| GET | `/api/calibration` | Current calibration state |
| GET | `/api/daily-summary?date=YYYY-MM-DD` | Aggregated daily report |
| GET | `/api/weekly-report?days=7` | Daily summaries for last N days |
| GET | `/api/break-stats` | Break compliance statistics |
| POST | `/api/recalibrate` | Trigger recalibration |

---

## 6. Frontend Architecture

### 6.1 Design System

**Fonts:** Fraunces (display/headings), Manrope (UI text)

**Color Palette:**
| Token | Light | Dark |
|-------|-------|------|
| `--accent-teal` | #0f766e | #2dd4bf |
| `--accent-blue` | #0369a1 | #38bdf8 |
| `--accent-amber` | #c2410c | #fb923c |
| `--accent-red` | #b91c1c | #f87171 |
| `--accent-purple` | #7c3aed | #a78bfa |

**Dark Mode:** Full theme toggle via `[data-theme="dark"]` CSS custom properties. Persisted to `localStorage`.

**Visual Effects:** Glassmorphism header, subtle grid background, micro-animations (popIn, fadeIn, breathe, valueFlash), smooth transitions.

### 6.2 Components

| Component | File | Purpose |
|-----------|------|---------|
| `App` | `App.jsx` | Root layout, state management, theme toggle |
| `ConnectionState` | `ConnectionState.jsx` | Pre-connection screen with consent + camera permission |
| `CalibrationOverlay` | `CalibrationOverlay.jsx` | Modal with progress bar during calibration |
| `MetricCard` | `MetricCard.jsx` | Reusable card with value, unit, trend indicator, status dot |
| `SparklineChart` | `SparklineChart.jsx` | Mini area chart (Recharts) for metric trends |
| `WellnessRing` | `WellnessRing.jsx` | Animated SVG arc showing composite wellness score |
| `GazeIndicator` | `GazeIndicator.jsx` | Directional dot overlay on webcam feed |
| `BreakReminder` | `BreakReminder.jsx` | Fullscreen overlay with 20s countdown timer |
| `SettingsDrawer` | `SettingsDrawer.jsx` | Slide-in panel for threshold configuration |
| `AnalyticsModal` | `AnalyticsModal.jsx` | Full analytics with 5 area charts, range selector, CSV export |

### 6.3 WebSocket Hook (`useErgoVisionSocket.js`)

Custom React hook managing:
- Connection lifecycle with exponential backoff reconnection (1s → 2s → 4s → ... → 15s max)
- Frame and detection data state
- Alert feed with configurable limit (50 alerts)
- Toast notification queue with auto-dismiss (5s)
- History buffer (240 samples) for sparklines and analytics
- Break status tracking
- Head tilt + gaze data in history entries

### 6.4 Dashboard Layout

**Header:** Logo, brand, break timer pill, live status badge, theme toggle, focus mode, analytics button, settings button.

**Insight Strip (3 cards):**
1. Wellness Ring — animated SVG score with tier label (Excellent/Balanced/At Risk/Critical)
2. Session Stats — duration, healthy time, score, breaks taken
3. Quick Actions — contextual advice + recalibrate button

**Webcam Panel:** Live feed with LIVE badge, FPS counter, gaze indicator dot overlay.

**Metrics Grid (5 cards):** Eye Strain, Posture, Distance, Fatigue, Head Tilt — each with value, unit, detail, status dot, trend arrow.

**Sparkline Grid (5 charts):** Rolling 30-sample mini charts for each metric.

**Side Panel:** Session info card + scrollable alert feed with category filter chips.

**Focus Mode:** Hides side panel, expands webcam to 16:9, 5-column metric grid.

---

## 7. Configuration Reference (`config.py`)

All values can be overridden via environment variables (prefix `ERGOVISION_`).

### Server
| Variable | Default | Description |
|----------|---------|-------------|
| `API_HOST` | `0.0.0.0` | Bind address |
| `API_PORT` | `8000` | HTTP/WS port |
| `LOG_LEVEL` | `INFO` | Python logging level |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:*` | Comma-separated origins |

### Camera
| Variable | Default | Description |
|----------|---------|-------------|
| `CAMERA_INDEX` | `0` | OpenCV camera device index |
| `CAMERA_WIDTH` | `640` | Capture width |
| `CAMERA_HEIGHT` | `480` | Capture height |
| `TARGET_FPS` | `15` | Frame processing target |

### Eye Detection
| Variable | Default | Description |
|----------|---------|-------------|
| `EAR_THRESHOLD` | `0.25` | EAR below this = closed |
| `EAR_CONSEC_FRAMES` | `2` | Minimum frames for blink |
| `EAR_BUFFER_SECONDS` | `60` | Rolling blink window |
| `MIN_BLINK_RATE` | `5` | Alert if fewer blinks/min |
| `EAR_SMOOTHING_ALPHA` | `0.3` | EMA smoothing factor |
| `GAZE_STARE_SECONDS` | `30` | Stare alert threshold |
| `GAZE_MOVEMENT_THRESHOLD` | `0.015` | Min iris shift for saccade |

### Posture
| Variable | Default | Description |
|----------|---------|-------------|
| `POSTURE_OFFSET_THRESHOLD` | `40` | Pixels for ALERT |
| `POSTURE_WARNING_THRESHOLD` | `25` | Pixels for WARNING |
| `POSTURE_CALIBRATION_SECONDS` | `30` | Calibration duration |

### Distance
| Variable | Default | Description |
|----------|---------|-------------|
| `IRIS_DIAMETER_MM` | `11.7` | Universal iris constant |
| `MIN_DISTANCE_CM` | `50` | Too-close threshold |
| `DEFAULT_FOCAL_LENGTH_PX` | `600` | Fallback focal length |

### Fatigue
| Variable | Default | Description |
|----------|---------|-------------|
| `MAR_THRESHOLD` | `0.6` | MAR above = yawn |
| `MAR_SUSTAINED_SECONDS` | `2.0` | Min yawn duration |
| `MAX_YAWNS_PER_HOUR` | `3` | Yawn alert threshold |

### Head Tilt
| Variable | Default | Description |
|----------|---------|-------------|
| `HEAD_TILT_THRESHOLD_DEG` | `15` | Degrees for alert |
| `HEAD_TILT_SUSTAINED_SECONDS` | `10` | Sustained duration |

### Breaks
| Variable | Default | Description |
|----------|---------|-------------|
| `BREAK_INTERVAL_SECONDS` | `1200` | 20 minutes |
| `MIN_BREAK_DURATION_SECONDS` | `20` | 20 seconds |

### Alerts
| Variable | Default | Description |
|----------|---------|-------------|
| `ALERT_COOLDOWN_SECONDS` | `300` | 5 min between same type |
| `ALERT_ESCALATION_LEVELS` | `{0:1.0, 1:0.7, 2:0.5}` | Cooldown multipliers |

---

## 8. Project Structure

```
ErgoVision/
├── server.py                    # FastAPI entry point (v2.0)
├── config.py                    # All thresholds and env config
├── requirements.txt             # Python dependencies
├── DOCUMENTATION.md             # This file
├── README.md                    # Quick-start guide
├── .env.example                 # Environment template
│
├── src/
│   ├── __init__.py
│   ├── runtime.py               # Frame processing orchestrator
│   ├── camera.py                # OpenCV + MediaPipe wrapper
│   ├── session_state.py         # Thread-safe shared state (40+ fields)
│   ├── alert_engine.py          # 7 alert types + progressive escalation
│   ├── break_manager.py         # 20-20-20 rule + compliance tracking
│   ├── productivity_tracker.py  # Healthy/degraded/absent time tracking
│   ├── calibration.py           # Two-phase calibration state machine
│   ├── database.py              # SQLite with 5 tables + auto-migration
│   ├── voice_alert.py           # Offline TTS via pyttsx3
│   └── detectors/
│       ├── __init__.py
│       ├── eye_fatigue.py       # EAR + gaze + stare detection
│       ├── posture.py           # Slouch + shoulder asymmetry
│       ├── distance.py          # Iris pinhole model
│       ├── fatigue_score.py     # MAR + weighted composite score
│       └── head_tilt.py         # Roll angle from eye corners
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js           # Dev server + backend proxy
│   ├── index.html
│   ├── .env.example
│   └── src/
│       ├── main.jsx             # React entry
│       ├── App.jsx              # Root component (dark mode, 5 metrics)
│       ├── App.css
│       ├── index.css            # Full design system + dark mode
│       ├── hooks/
│       │   └── useErgoVisionSocket.js  # WebSocket state management
│       ├── components/
│       │   ├── AnalyticsModal.jsx      # 5 area charts + CSV export
│       │   ├── BreakReminder.jsx       # 20s countdown overlay
│       │   ├── CalibrationOverlay.jsx  # Calibration progress modal
│       │   ├── ConnectionState.jsx     # Pre-connect consent screen
│       │   ├── GazeIndicator.jsx       # Directional dot on webcam
│       │   ├── MetricCard.jsx          # Reusable metric display
│       │   ├── SettingsDrawer.jsx      # Threshold configuration
│       │   ├── SparklineChart.jsx      # Mini trend chart
│       │   └── WellnessRing.jsx        # Animated SVG score ring
│       └── constants/
│           └── alerts.js               # Alert configs + defaults
│
├── tests/
│   ├── __init__.py
│   ├── test_alert_engine.py     # 7 alert types + cooldown tests
│   ├── test_database.py         # Session, event, snapshot, break tests
│   ├── test_detectors.py        # Head tilt geometry + EAR formula
│   └── test_session_state.py    # Thread-safe state tests
│
└── data/                        # Auto-created at runtime
    ├── wellness.db              # SQLite database
    └── calibration.json         # Persisted calibration baselines
```

---

## 9. Setup & Running

### Prerequisites
- Python 3.11 or 3.12
- Node.js 18+
- Webcam

### Backend
```bash
pip install -r requirements.txt
python server.py
```

### Frontend (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

### Open Dashboard
```
http://localhost:5174
```

### Run Tests
```bash
# Backend (25 tests)
pytest -q

# Frontend
cd frontend
npm run lint
npm run build
```

---

## 10. Privacy & Security

- **100% local processing** — no cloud APIs, no telemetry, no network calls
- Raw video frames are streamed only to the local browser via WebSocket — never persisted
- SQLite stores only derived numeric metrics (EAR values, distances, angles)
- Camera consent is explicitly requested via browser prompt before monitoring starts
- No user accounts, no authentication — single-user local tool
