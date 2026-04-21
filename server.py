"""
ErgoVision — FastAPI WebSocket Server
Bridges the Python CV pipeline to the React frontend via WebSocket.
Streams webcam frames + detection data in real-time.
"""

from __future__ import annotations

import asyncio
import errno
import json
import logging
import os

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse
import uvicorn

import config
from src.runtime import ErgoVisionRuntime


logging.basicConfig(
    level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("ergovision.server")


# ─── App Setup ────────────────────────────────────────
app = FastAPI(title="ErgoVision API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ALLOWED_ORIGINS,
    allow_credentials=config.CORS_ALLOW_CREDENTIALS,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Runtime State ───────────────────────────────────
runtime = ErgoVisionRuntime()


async def _safe_send_json(websocket: WebSocket, payload: dict) -> bool:
    """Send payload to client and return False when the socket is no longer writable."""
    try:
        await websocket.send_text(json.dumps(payload))
        return True
    except WebSocketDisconnect:
        return False
    except RuntimeError:
        logger.info("WebSocket closed while sending payload.")
        return False
    except Exception:
        logger.exception("Unexpected error while sending WebSocket payload.")
        return False


def _format_local_urls() -> tuple[str, str, str]:
    """Build readable backend/frontend/ws URLs for startup logs."""
    display_host = "localhost" if config.API_HOST in {"0.0.0.0", "::"} else config.API_HOST
    backend_url = f"http://{display_host}:{config.API_PORT}"
    frontend_url = os.getenv(
        "ERGOVISION_FRONTEND_URL",
        f"http://localhost:{config.FRONTEND_DEV_PORT}",
    )
    ws_scheme = "wss" if backend_url.startswith("https://") else "ws"
    ws_url = f"{ws_scheme}://{display_host}:{config.API_PORT}/ws"
    return backend_url, frontend_url, ws_url


# ─── WebSocket Endpoint ───────────────────────────────
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    runtime.add_client(websocket)
    logger.info("WebSocket client connected. clients=%s", runtime.client_count())

    try:
        runtime.ensure_pipeline_started()
        logger.info("Camera pipeline started. session_id=%s", runtime.current_session_id)
    except Exception as exc:
        logger.exception("Failed to start runtime pipeline.")
        await _safe_send_json(
            websocket,
            {
                "type": "error",
                "message": f"Cannot start monitoring pipeline: {exc}",
            },
        )
        await websocket.close(code=1011)
        runtime.remove_client(websocket)
        runtime.stop_pipeline_if_idle()
        return

    try:
        while True:
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.01)
                await runtime.handle_client_message(msg)
            except asyncio.TimeoutError:
                pass

            frame_b64, data = await asyncio.get_running_loop().run_in_executor(
                None,
                runtime.process_frame,
            )

            if frame_b64 is not None:
                delivered = await _safe_send_json(
                    websocket,
                    {
                        "frame": frame_b64,
                        "data": data,
                    },
                )
                if not delivered:
                    break

            await asyncio.sleep(0.05)

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected.")
    except Exception:
        logger.exception("Unhandled WebSocket loop error.")
    finally:
        runtime.remove_client(websocket)
        ended_session_id = runtime.stop_pipeline_if_idle()
        if ended_session_id:
            logger.info("Camera pipeline stopped. session_id=%s saved.", ended_session_id)


# ─── REST Endpoints ───────────────────────────────────
@app.get("/api/status")
async def get_status():
    """Get current system status."""
    return JSONResponse(content=runtime.session_state.get_all())


@app.get("/api/health")
async def get_health():
    """Lightweight health endpoint for readiness checks."""
    return JSONResponse(
        content={
            "status": "ok",
            "clients": runtime.client_count(),
            "pipeline_running": runtime.is_running,
        }
    )


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
else:
    logger.info(
        "Frontend build not found at '%s'. Run 'cd frontend && npm run build' to serve static files.",
        frontend_build,
    )


# ─── Entry Point ──────────────────────────────────────
if __name__ == "__main__":
    os.makedirs(config.DATA_DIR, exist_ok=True)

    # Try to load existing calibration
    if runtime.bootstrap_calibration():
        logger.info("Loaded saved calibration data.")
    else:
        logger.info("No saved calibration data. Calibration will run on first connect.")

    backend_url, frontend_url, ws_url = _format_local_urls()
    logger.info("+------------------------------------------+")
    logger.info("|        ErgoVision Server Started        |")
    logger.info("|   Backend:  %-28s|", backend_url)
    logger.info("|   Frontend: %-28s|", frontend_url)
    logger.info("|   WebSocket: %-27s|", ws_url)
    logger.info("+------------------------------------------+")

    try:
        uvicorn.run(
            app,
            host=config.API_HOST,
            port=config.API_PORT,
            log_level=config.LOG_LEVEL,
        )
    except OSError as exc:
        if exc.errno in {errno.EADDRINUSE, 10048}:
            logger.error(
                "Port %s is already in use. Set ERGOVISION_API_PORT to another port.",
                config.API_PORT,
            )
        else:
            logger.exception("Failed to start server due to OS error.")
        raise
