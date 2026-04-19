"""
ErgoVision — FastAPI WebSocket Server
Bridges the Python CV pipeline to the React frontend via WebSocket.
Streams webcam frames + detection data in real-time.
"""

import asyncio
import json
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn

import config
from src.runtime import ErgoVisionRuntime


# ─── App Setup ────────────────────────────────────────
app = FastAPI(title="ErgoVision API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Runtime State ───────────────────────────────────
runtime = ErgoVisionRuntime()


# ─── WebSocket Endpoint ───────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    runtime.add_client(websocket)
    print(f"[WS] Client connected. Total: {runtime.client_count()}")

    try:
        runtime.ensure_pipeline_started()
        print(f"[Camera] Started. Session ID: {runtime.current_session_id}")

        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                await runtime.handle_client_message(msg)
            except asyncio.TimeoutError:
                pass

            frame_b64, data = await asyncio.get_event_loop().run_in_executor(
                None,
                runtime.process_frame,
            )

            if frame_b64 is not None:
                payload = json.dumps({
                    "frame": frame_b64,
                    "data": data,
                })
                await websocket.send_text(payload)

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        print("[WS] Client disconnected.")
    except Exception as e:
        print(f"[WS] Error: {e}")
    finally:
        runtime.remove_client(websocket)
        ended_session_id = runtime.stop_pipeline_if_idle()
        if ended_session_id:
            print(f"[Camera] Stopped. Session {ended_session_id} saved.")


# ─── REST Endpoints ───────────────────────────────────
@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return JSONResponse(content=runtime.session_state.get_all())


@app.get("/api/sessions")
async def get_sessions():
    """Get recent session history."""
    sessions = runtime.db.get_recent_sessions(20)
    return JSONResponse(content=[dict(s) for s in sessions])


@app.get("/api/sessions/{session_id}/events")
async def get_session_events(session_id: int):
    """Get events for a specific session."""
    events = runtime.db.get_session_events(session_id)
    return JSONResponse(content=[dict(e) for e in events])


@app.get("/api/sessions/{session_id}/snapshots")
async def get_session_snapshots(session_id: int):
    """Get snapshots for a specific session."""
    snapshots = runtime.db.get_session_snapshots(session_id)
    return JSONResponse(content=[dict(s) for s in snapshots])


@app.get("/api/analytics")
async def get_analytics():
    """Get analytics data for the last N days."""
    snapshots = runtime.db.get_all_snapshots_last_n_days(7)
    event_counts = runtime.db.get_event_counts_by_type()
    return JSONResponse(content={
        "snapshots": [dict(s) for s in snapshots],
        "event_counts": [{"type": e[0], "count": e[1]} for e in event_counts],
    })


@app.get("/api/calibration")
async def get_calibration_status():
    """Get calibration status."""
    return JSONResponse(content={
        "phase": runtime.calibration.phase,
        "progress": runtime.calibration.progress,
        "posture_calibrated": runtime.posture_detector.is_calibrated,
        "distance_calibrated": runtime.distance_detector.is_calibrated,
        "needs_calibration": runtime.calibration.needs_calibration(),
    })


# ─── Serve React Build (Production) ──────────────────
frontend_build = os.path.join(os.path.dirname(__file__), "frontend", "dist")
if os.path.exists(frontend_build):
    app.mount("/", StaticFiles(directory=frontend_build, html=True), name="frontend")


# ─── Entry Point ──────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Try to load existing calibration
    if runtime.bootstrap_calibration():
        print("[Calibration] Loaded saved calibration data.")
    else:
        print("[Calibration] No saved data. Calibration will run on first connect.")

    print("\n+------------------------------------------+")
    print("|        ErgoVision Server Started        |")
    print("|   Backend:  http://localhost:8000       |")
    print("|   Frontend: http://localhost:5174       |")
    print("|   WebSocket: ws://localhost:8000/ws     |")
    print("+------------------------------------------+\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
