# ErgoVision

ErgoVision is a realtime workstation wellness monitor built with Python, FastAPI, MediaPipe, and React.

It tracks **six health signals** from a standard webcam and provides immediate alerts plus session analytics:

- **Eye fatigue** — EAR formula + blink rate tracking
- **Posture drift** — nose-shoulder baseline deviation + shoulder asymmetry
- **Screen distance** — iris-based pinhole estimation
- **Fatigue trend** — yawn pattern (MAR) + composite score with session-duration weighting
- **Head tilt / neck strain** — sustained head roll detection via eye-corner geometry
- **Gaze tracking** — prolonged stare detection via iris saccade monitoring

### Additional Features

- 🌗 **Dark mode** — full dark/light theme toggle
- 🍅 **Pomodoro timer** — 25m work → 5m break → 15m long break cycle, toggleable with 20-20-20 mode
- 💧 **Hydration reminders** — periodic water drinking alerts with daily glass tracking and progress bar
- 🧘 **Stretch suggestions** — random exercise shown during break overlays (6 pre-defined routines)
- 🏆 **Posture streak** — live counter tracking consecutive good posture minutes with milestone badges
- ☕ **20-20-20 break reminders** — adaptive break intervals based on fatigue level
- 📊 **Wellness ring** — animated SVG ring showing real-time composite wellness score
- 🎯 **Gaze indicator** — directional dot overlaid on webcam feed
- 📈 **Productivity tracker** — healthy vs degraded time correlation
- 🔔 **Progressive alert escalation** — cooldown reduces when alerts are ignored
- 💡 **Context-aware wellness tips** — tailored advice based on current alert state
- 📥 **CSV export** + daily/weekly summary analytics

## Why This Project Is Production-Oriented

- Clear separation between API transport and runtime orchestration.
- Detector logic isolated into focused, testable modules.
- Frontend split into reusable components and a dedicated WebSocket hook.
- Persistent local analytics with SQLite (sessions, events, snapshots, breaks, daily summaries).
- Runtime calibration persistence for repeat sessions.
- Unit tests for state, alert engine, detectors, and database operations.
- Zero ML — geometry-first approach using only MediaPipe landmarks.

## Architecture

```text
Webcam -> MediaPipe landmarks -> Detector modules -> SessionState -> AlertEngine
                                                  -> Break Manager (20-20-20 / Pomodoro)
                                                  -> Hydration Tracker
                                                  -> Posture Streak Tracker
                                                  -> Productivity Tracker
                                                  -> Snapshot/Event logging (SQLite)
                                                  -> WebSocket stream -> React dashboard
```

### Backend Layers

- `server.py`: FastAPI entrypoint, HTTP/WebSocket routes, REST analytics API.
- `src/runtime.py`: monitoring lifecycle, frame processing, command handling.
- `src/detectors/`: eye fatigue, posture, distance, fatigue score, head tilt.
- `src/alert_engine.py`: alert cooldown, progressive escalation, and dispatch (9 alert types including `DRINK_WATER` and `POMODORO_BREAK`).
- `src/break_manager.py`: 20-20-20 rule + Pomodoro timer, hydration tracking, posture streak, stretch suggestions.
- `src/productivity_tracker.py`: healthy/degraded/absent time correlation.
- `src/calibration.py`: posture/distance calibration state machine.
- `src/database.py`: SQLite schema, migrations, and query operations.

### Frontend Layers

- `frontend/src/App.jsx`: top-level page with dark mode, 5 metric cards, break overlay.
- `frontend/src/hooks/useErgoVisionSocket.js`: stream state, reconnection, break tracking.
- `frontend/src/components/`: modular UI — WellnessRing, BreakReminder, GazeIndicator, MetricCard, AnalyticsModal, SettingsDrawer, SparklineChart, CalibrationOverlay, ConnectionState.
- `frontend/src/constants/alerts.js`: alert metadata and defaults.

## Project Structure

```text
ErgoVision/
├── config.py
├── server.py
├── requirements.txt
├── src/
│   ├── runtime.py
│   ├── camera.py
│   ├── session_state.py
│   ├── alert_engine.py
│   ├── break_manager.py
│   ├── productivity_tracker.py
│   ├── calibration.py
│   ├── database.py
│   ├── voice_alert.py
│   └── detectors/
│       ├── eye_fatigue.py
│       ├── posture.py
│       ├── distance.py
│       ├── fatigue_score.py
│       └── head_tilt.py
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       ├── hooks/
│       │   └── useErgoVisionSocket.js
│       ├── components/
│       │   ├── AnalyticsModal.jsx
│       │   ├── BreakReminder.jsx
│       │   ├── CalibrationOverlay.jsx
│       │   ├── ConnectionState.jsx
│       │   ├── GazeIndicator.jsx
│       │   ├── MetricCard.jsx
│       │   ├── SettingsDrawer.jsx
│       │   ├── SparklineChart.jsx
│       │   └── WellnessRing.jsx
│       └── constants/
│           └── alerts.js
├── tests/
│   ├── test_alert_engine.py
│   ├── test_database.py
│   ├── test_detectors.py
│   └── test_session_state.py
└── data/
    ├── wellness.db
    └── calibration.json
```

## Quick Start

### Prerequisites

- Python 3.11 or 3.12 (3.12 recommended)
- Node.js 18+
- Webcam

### 1. One-command setup (recommended)

Windows PowerShell:

```powershell
./scripts/setup.ps1
```

macOS/Linux:

```bash
bash scripts/setup.sh
```

### 2. Manual setup (optional)

Copy environment templates:

```bash
cp .env.example .env
cp frontend/.env.example frontend/.env
```

Install backend dependencies:

```bash
pip install -r requirements.txt
```

Install frontend dependencies:

```bash
cd frontend
npm install
```

### 3. Start backend

```bash
python server.py
```

### 4. Start frontend (new terminal)

```bash
cd frontend
npm run dev
```

### 5. Open dashboard

```text
http://localhost:5174
```

## Runtime Flow

1. Frontend connects to `VITE_WS_URL` or auto-resolves the backend WebSocket URL.
2. Backend starts camera + monitoring session on first client connect.
3. Calibration runs if not previously stored.
4. Each frame updates all detector states (eye, posture, distance, fatigue, head tilt, gaze).
5. Break manager tracks time since last break with adaptive intervals.
6. Productivity tracker correlates healthy vs degraded time.
7. Alerts are rate-limited by cooldown policy with progressive escalation.
8. Snapshots are logged every 30 seconds.
9. Session is closed when last client disconnects.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/status` | Current shared runtime state |
| GET | `/api/health` | Service readiness and pipeline state |
| GET | `/api/sessions` | Recent sessions |
| GET | `/api/sessions/{id}/events` | Alert events for a session |
| GET | `/api/sessions/{id}/snapshots` | Periodic detector snapshots |
| GET | `/api/analytics` | Recent snapshots and aggregate event counts |
| GET | `/api/calibration` | Calibration phase and flags |
| GET | `/api/daily-summary` | Daily aggregated health report |
| GET | `/api/weekly-report` | Weekly trend summary |
| GET | `/api/break-stats` | Break compliance data |
| POST | `/api/recalibrate` | Trigger recalibration |

## Configuration

Runtime defaults live in `config.py`, and can be overridden with environment variables via `.env`.

Common backend variables:

- `ERGOVISION_API_HOST`, `ERGOVISION_API_PORT`, `ERGOVISION_LOG_LEVEL`
- `ERGOVISION_CORS_ALLOWED_ORIGINS` (comma-separated)
- `ERGOVISION_CAMERA_INDEX`, `ERGOVISION_CAMERA_WIDTH`, `ERGOVISION_CAMERA_HEIGHT`, `ERGOVISION_TARGET_FPS`
- `ERGOVISION_DATA_DIR`, `ERGOVISION_DB_PATH`, `ERGOVISION_DB_TIMEOUT_SECONDS`

Common frontend variables:

- `VITE_WS_URL` (explicit websocket URL override)
- `VITE_BACKEND_HOST`, `VITE_BACKEND_PORT` (used by fallback URL and Vite proxy)

Detector tuning still lives in `config.py`:

- Detection thresholds (`EAR_THRESHOLD`, `MIN_DISTANCE_CM`, `HEAD_TILT_THRESHOLD_DEG`, etc.)
- Alert cooldown (`ALERT_COOLDOWN_SECONDS`)
- Break intervals (`BREAK_INTERVAL_SECONDS`, `MIN_BREAK_DURATION_SECONDS`)
- Pomodoro settings (`POMODORO_WORK_MINUTES`, `POMODORO_SHORT_BREAK_MINUTES`, `POMODORO_LONG_BREAK_MINUTES`)
- Hydration settings (`HYDRATION_INTERVAL_SECONDS`, `HYDRATION_DAILY_GOAL`)
- Gaze tracking (`GAZE_STARE_SECONDS`, `GAZE_MOVEMENT_THRESHOLD`)
- Stretch exercises (`STRETCH_EXERCISES` — list of 6 routines)
- Posture streak milestones (`POSTURE_STREAK_MILESTONES`)

## Data Persistence

- SQLite database: `data/wellness.db`
- Calibration cache: `data/calibration.json`
- Tables: `sessions`, `events`, `snapshots`, `break_events`, `daily_summaries`

Back up the `data/` folder if you want to preserve history and calibration across machines.

## Testing

Run backend tests from repository root:

```bash
pytest -q
```

Frontend checks:

```bash
cd frontend
npm run lint
npm run build
```

## Privacy

- Processing is local only.
- Raw frames are streamed to local dashboard only; not persisted.
- SQLite stores derived numeric metrics and alert metadata.
- Zero data leaves the machine.

## Camera Permissions

ErgoVision opens the webcam from the Python backend (OpenCV) and streams frames to the dashboard over WebSocket.

The dashboard also requests browser camera permission when you click Connect (so you see a standard browser permission prompt). This is an explicit consent step; the monitoring pipeline still runs in the local Python backend.

On Windows, backend camera access is controlled by OS privacy settings:

- Settings → Privacy & security → Camera
- Turn on **Camera access**
- Turn on **Let desktop apps access your camera**

## Troubleshooting

- Camera unavailable: verify camera permissions and ensure no other app is locking the webcam.
- WebSocket not connecting: check backend logs and verify `.env` host/port values.
- No detection data: ensure face and shoulders are visible during calibration.
- Frontend can load but no realtime stream: set `VITE_WS_URL` or `VITE_BACKEND_HOST`/`VITE_BACKEND_PORT` in `frontend/.env`.
- Port already in use: set `ERGOVISION_API_PORT` to a free value and restart.
- `AttributeError: module 'mediapipe' has no attribute 'solutions'`: recreate `.venv` with Python 3.12 and reinstall dependencies (`scripts/setup.ps1` or `scripts/setup.sh`).
