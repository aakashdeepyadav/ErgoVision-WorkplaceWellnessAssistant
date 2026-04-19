# ErgoVision Frontend

React + Vite dashboard for realtime visualization and control of the ErgoVision backend.

## Responsibilities

- Render live webcam stream from backend WebSocket payloads.
- Show realtime detector metrics (eye, posture, distance, fatigue).
- Surface alert timeline and toast notifications.
- Provide settings panel for threshold updates.
- Show session analytics charts.

## Local Development

1. Install dependencies:

```bash
npm install
```

2. Start the frontend dev server:

```bash
npm run dev
```

3. Open the URL printed by Vite (default: http://localhost:5174).

## Backend Dependency

The dashboard expects the backend WebSocket at:

- `ws://localhost:8000/ws`

Override by setting `VITE_WS_URL` in your environment.

## Build and Preview

```bash
npm run build
npm run preview
```

## Main Frontend Structure

- `src/App.jsx`: top-level dashboard composition.
- `src/hooks/useErgoVisionSocket.js`: WebSocket lifecycle + stream state.
- `src/components/`: reusable UI modules.
- `src/constants/alerts.js`: alert metadata and defaults.
- `src/index.css`: design tokens and global styles.
