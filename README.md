# ErgoVision

ErgoVision is a realtime workstation wellness monitor built with Python, FastAPI, MediaPipe, and React.

It tracks four health signals from a standard webcam and provides immediate alerts plus session analytics:

- Eye fatigue (EAR + blink rate)
- Posture drift (nose-shoulder baseline deviation)
- Screen distance (iris-based pinhole estimation)
- Fatigue trend (yawn pattern + composite score)

## Why This Project Is Production-Oriented

- Clear separation between API transport and runtime orchestration.
- Detector logic isolated into focused modules.
- Frontend split into reusable components and a dedicated WebSocket hook.
- Persistent local analytics with SQLite.
- Runtime calibration persistence for repeat sessions.
- Unit tests for state and alert engine behavior.

## Architecture

```text
Webcam -> MediaPipe landmarks -> Detector modules -> SessionState -> AlertEngine
                                                  -> Snapshot/Event logging (SQLite)
                                                  -> WebSocket stream -> React dashboard
```

### Backend Layers

- `server.py`: FastAPI entrypoint and HTTP/WebSocket routes.
- `src/runtime.py`: monitoring lifecycle, frame processing, command handling.
- `src/detectors/`: eye, posture, distance, and fatigue detectors.
- `src/alert_engine.py`: alert cooldown and dispatch.
- `src/calibration.py`: posture/distance calibration state machine.
- `src/database.py`: SQLite schema and query operations.

### Frontend Layers

- `frontend/src/App.jsx`: top-level page composition.
- `frontend/src/hooks/useErgoVisionSocket.js`: stream state and reconnection.
- `frontend/src/components/`: modular UI sections.
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
│   ├── calibration.py
│   ├── database.py
│   ├── voice_alert.py
│   └── detectors/
│       ├── eye_fatigue.py
│       ├── posture.py
│       ├── distance.py
│       └── fatigue_score.py
├── frontend/
│   ├── package.json
│   └── src/
│       ├── App.jsx
│       ├── index.css
│       ├── hooks/
│       ├── components/
│       └── constants/
└── tests/
    ├── test_session_state.py
    └── test_alert_engine.py
```

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Webcam

### 1. Install backend dependencies

```bash
pip install -r requirements.txt
```

### 2. Install frontend dependencies

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

1. Frontend connects to `ws://localhost:8000/ws`.
2. Backend starts camera + monitoring session on first client connect.
3. Calibration runs if not previously stored.
4. Each frame updates detector state and optional alerts.
5. Alerts are rate-limited by cooldown policy.
6. Snapshots are logged every 30 seconds.
7. Session is closed when last client disconnects.

## API Endpoints

- `GET /api/status`: current shared runtime state.
- `GET /api/sessions`: recent sessions.
- `GET /api/sessions/{id}/events`: alert events for a session.
- `GET /api/sessions/{id}/snapshots`: periodic detector snapshots.
- `GET /api/analytics`: recent snapshots and aggregate event counts.
- `GET /api/calibration`: calibration phase and flags.

## Configuration

Edit `config.py` for:

- Detection thresholds (`EAR_THRESHOLD`, `MIN_DISTANCE_CM`, etc.)
- Alert cooldown (`ALERT_COOLDOWN_SECONDS`)
- Camera settings (`CAMERA_WIDTH`, `CAMERA_HEIGHT`, `TARGET_FPS`)
- Paths (`DATA_DIR`, `DB_PATH`)

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

## Troubleshooting

- Camera unavailable: verify camera is not locked by another process.
- WebSocket not connecting: confirm backend is running on port 8000.
- No detection data: ensure face and shoulders are visible during calibration.
- Missing frontend data: confirm browser can reach `ws://localhost:8000/ws`.
