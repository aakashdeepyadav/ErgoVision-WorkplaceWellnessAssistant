"""
ErgoVision — FastAPI Server (Enhanced)
WebSocket video pipeline + REST API for analytics, breaks, and daily summaries.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

import config

# Ensure `src` is importable when running ``python server.py`` from the repository root.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.runtime import ErgoVisionRuntime  # noqa: E402


logger = logging.getLogger("ergovision.server")
logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s | %(name)s | %(levelname)s | %(message)s")


app = FastAPI(title="ErgoVision", version="2.0.0")

# ── CORS ─────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Runtime ──────────────────────────────────────────

runtime = ErgoVisionRuntime()
runtime.bootstrap_calibration()


# ── REST endpoints ───────────────────────────────────

@app.get("/api/status")
async def api_status():
    """Return current session state snapshot for debugging or external polling."""
    return runtime.session_state.get_all()


@app.get("/api/health")
async def api_health():
    """Readiness probe: reports whether the pipeline is active and current session info."""
    return {
        "status": "ok",
        "running": runtime.is_running,
        "session_id": runtime.current_session_id,
        "client_count": runtime.client_count(),
    }


@app.get("/api/sessions")
async def api_sessions():
    """Return the most recent monitoring sessions."""
    rows = runtime.db.get_recent_sessions(limit=20)
    return [dict(r) for r in rows]


@app.get("/api/sessions/{session_id}/events")
async def api_session_events(session_id: int):
    """Return alert events for a given session."""
    rows = runtime.db.get_session_events(session_id)
    return [dict(r) for r in rows]


@app.get("/api/sessions/{session_id}/snapshots")
async def api_session_snapshots(session_id: int):
    """Return periodic health snapshots for a given session."""
    rows = runtime.db.get_session_snapshots(session_id)
    return [dict(r) for r in rows]


@app.get("/api/analytics")
async def api_analytics():
    """Return recent snapshots and event counts for dashboard analytics."""
    snapshots = runtime.db.get_all_snapshots_last_n_days(days=7)
    event_counts = runtime.db.get_event_counts_by_type()
    return {
        "snapshots": [dict(r) for r in snapshots],
        "event_counts": event_counts,
    }


@app.get("/api/calibration")
async def api_calibration():
    """Return current calibration state."""
    return {
        "phase": runtime.calibration.phase,
        "is_complete": runtime.calibration.is_complete(),
        "posture_calibrated": runtime.posture_detector.is_calibrated,
        "distance_calibrated": runtime.distance_detector.is_calibrated,
    }


@app.get("/api/daily-summary")
async def api_daily_summary(date: str | None = None):
    """Return daily aggregated health report for a specific date (default: today)."""
    runtime.db.update_daily_summary(date)
    summary = runtime.db.get_daily_summary(date)
    return summary or {"message": "No data available for this date."}


@app.get("/api/weekly-report")
async def api_weekly_report(days: int = 7):
    """Return daily summaries for the last N days."""
    rows = runtime.db.get_weekly_summaries(days=days)
    return [dict(r) for r in rows]


@app.get("/api/break-stats")
async def api_break_stats():
    """Return break compliance statistics."""
    session_stats = runtime.break_manager.get_status()
    db_stats = runtime.db.get_break_stats(runtime.current_session_id)
    return {
        "current_session": session_stats,
        "database": db_stats,
    }


@app.post("/api/recalibrate")
async def api_recalibrate():
    """Trigger recalibration via REST."""
    runtime.calibration.start_posture_calibration()
    return {"status": "calibration_started", "phase": runtime.calibration.phase}


# ── WebSocket ────────────────────────────────────────

@app.websocket("/ws")
async def websocket_monitor(websocket: WebSocket):
    """
    Main monitoring endpoint.

    Each connected client receives a stream of frames (base64 JPEG) with
    detection data.  The very first client triggers camera + session start;
    the last disconnect stops it.
    """
    await websocket.accept()

    try:
        runtime.ensure_pipeline_started()
    except Exception as exc:
        logger.exception("Pipeline failed to start during WebSocket connect.")
        await websocket.send_json({"type": "error", "message": str(exc)})
        await websocket.close()
        return

    runtime.add_client(websocket)
    logger.info("Client connected (total: %d).", runtime.client_count())

    receive_task = asyncio.create_task(_receive_client_commands(websocket))
    stream_task = asyncio.create_task(_stream_frames(websocket))

    try:
        done, pending = await asyncio.wait(
            {receive_task, stream_task}, return_when=asyncio.FIRST_COMPLETED
        )
        for task in pending:
            task.cancel()
    except WebSocketDisconnect:
        pass
    finally:
        receive_task.cancel()
        stream_task.cancel()
        runtime.remove_client(websocket)
        ended_id = runtime.stop_pipeline_if_idle()
        if ended_id:
            logger.info("Session %s ended (last client disconnected).", ended_id)


async def _receive_client_commands(websocket: WebSocket) -> None:
    """Forward incoming client messages to the runtime command handler."""
    try:
        while True:
            raw = await websocket.receive_text()
            await runtime.handle_client_message(raw)
    except WebSocketDisconnect:
        return


async def _stream_frames(websocket: WebSocket) -> None:
    """Continuously process frames and push results to the client."""
    target_delay = 1.0 / config.TARGET_FPS

    while True:
        t_start = asyncio.get_event_loop().time()

        try:
            frame_b64, data = await asyncio.to_thread(runtime.process_frame)
        except Exception:
            logger.exception("Frame processing error.")
            await asyncio.sleep(target_delay)
            continue

        if frame_b64 is None:
            await asyncio.sleep(target_delay)
            continue

        payload = json.dumps({"frame": frame_b64, "data": data})

        try:
            await websocket.send_text(payload)
        except WebSocketDisconnect:
            return
        except Exception:
            return

        elapsed = asyncio.get_event_loop().time() - t_start
        sleep_time = max(0.005, target_delay - elapsed)
        await asyncio.sleep(sleep_time)


# ── Entry point ──────────────────────────────────────

if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host=config.API_HOST,
        port=config.API_PORT,
        log_level=config.LOG_LEVEL.lower(),
        reload=False,
    )
