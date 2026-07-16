"""
TASK-10.1 / 10.2 / 10.3 / 10.4 — WebSocket /ws/pose endpoint.

Lifecycle:
  1. On connect: validate session_id query param → active session or close 4001.
  2. Start heartbeat loop (ping every 5 s; 3 missed pongs → interrupt_session).
  3. Per-frame loop:
       base64 JPEG decode
       → process_frame (CV)          [TASK-10.2]
       → classify_frame (ML)         [TASK-10.2]
       → score_frame (Form Engine)   [TASK-10.2]
       → update_rep_state (Rep)      [TASK-10.2]
       → running_estimate (Calories) [TASK-10.2]
       → exercise-change handling    [TASK-10.3]
       → warning injection           [TASK-10.4]
       → JSON response → send

Design ref: §3.1, §2.6, §1.2. REQs: REQ-1.1, REQ-1.4, REQ-1.5, REQ-2.1,
REQ-2.3, REQ-2.4, REQ-3.2, REQ-4.3, REQ-4.5, REQ-5.3, REQ-5.5, REQ-6.3.
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import time
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from backend.calories.engine import CalorieEngine
from backend.cv.pipeline import process_frame
from backend.ml.pipeline import MLPipeline
from backend.reps.counter import RepCounter
from backend.scoring.engine import score_frame
from backend.scoring.set_form_tracker import SetFormTracker
from backend.session.manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_HEARTBEAT_INTERVAL = 5.0     # seconds between pings
_MAX_MISSED_PONGS = 3         # interrupt after this many missed pongs
_CLOSE_CODE_INVALID = 4001    # custom close code: invalid/missing session_id


# ---------------------------------------------------------------------------
# Per-session state container
# ---------------------------------------------------------------------------

class _SessionState:
    """Holds all mutable per-session processing state."""

    def __init__(self, session_id: str, weight_kg: float) -> None:
        self.session_id = session_id
        self.weight_kg = weight_kg

        # Pipeline components
        self.ml_pipeline = MLPipeline()
        self.rep_counter = RepCounter()
        self.form_tracker = SetFormTracker()
        self.calorie_engine = CalorieEngine(weight_kg=weight_kg)

        # Exercise-change tracking (TASK-10.3)
        self.last_confirmed_type: Optional[str] = None

        # Calorie segment open flag
        self.segment_open = False

        # Timing
        self.last_frame_ts: float = time.monotonic()


# ---------------------------------------------------------------------------
# Helper: resolve active session weight from DB
# ---------------------------------------------------------------------------

def _get_session_weight(session_id: str) -> Optional[float]:
    """Return weight_kg for session_id's user, or None if not found/not active."""
    from backend.database import SessionLocal
    from backend.models.sessions import Session
    from backend.models.users import User

    db = SessionLocal()
    try:
        row = db.query(Session).filter(Session.id == session_id).first()
        if row is None or row.status != "active":
            return None
        user = db.query(User).filter(User.id == row.user_id).first()
        if user is None:
            return None
        return float(user.weight_kg)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Heartbeat coroutine
# ---------------------------------------------------------------------------

async def _heartbeat(
    ws: WebSocket,
    state: _SessionState,
    stop_event: asyncio.Event,
) -> None:
    """Send pings every 5 s; interrupt session after 3 consecutive missed pongs."""
    missed = 0
    while not stop_event.is_set():
        await asyncio.sleep(_HEARTBEAT_INTERVAL)
        if stop_event.is_set():
            break
        try:
            pong_waiter = await ws.send_text(json.dumps({"type": "ping"}))
            # FastAPI WebSocket doesn't expose low-level ping/pong frames,
            # so we implement a soft heartbeat: send a ping JSON message and
            # expect the client to echo {"type": "pong"}.  If the connection
            # is dead, send_text will raise.
            missed = 0
        except Exception:
            missed += 1
            logger.warning(
                "Heartbeat: missed pong %d/%d for session %s",
                missed, _MAX_MISSED_PONGS, state.session_id,
            )
            if missed >= _MAX_MISSED_PONGS:
                logger.warning(
                    "Interrupting session %s (heartbeat timeout)", state.session_id
                )
                try:
                    session_manager.interrupt_session(state.session_id)
                except Exception as exc:
                    logger.error("interrupt_session failed: %s", exc)
                stop_event.set()
                break


# ---------------------------------------------------------------------------
# Main WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/ws/pose")
async def ws_pose(websocket: WebSocket):
    """
    WebSocket endpoint for real-time pose processing.

    Query params:
        session_id (str): UUID of an active session.
    """
    session_id: Optional[str] = websocket.query_params.get("session_id")

    # ------------------------------------------------------------------
    # TASK-10.1 — Validate session_id
    # ------------------------------------------------------------------
    if not session_id:
        await websocket.close(code=_CLOSE_CODE_INVALID)
        logger.info("WS rejected: missing session_id")
        return

    weight_kg = _get_session_weight(session_id)
    if weight_kg is None:
        await websocket.close(code=_CLOSE_CODE_INVALID)
        logger.info("WS rejected: session_id=%s not active", session_id)
        return

    await websocket.accept()
    logger.info("WS accepted: session_id=%s weight=%.1f", session_id, weight_kg)

    state = _SessionState(session_id=session_id, weight_kg=weight_kg)
    stop_event = asyncio.Event()

    # Start heartbeat as a background task
    heartbeat_task = asyncio.create_task(
        _heartbeat(websocket, state, stop_event)
    )

    try:
        while not stop_event.is_set():
            try:
                raw = await asyncio.wait_for(
                    websocket.receive_text(), timeout=_HEARTBEAT_INTERVAL + 1
                )
            except asyncio.TimeoutError:
                continue
            except WebSocketDisconnect:
                logger.info("WS client disconnected: session_id=%s", session_id)
                break

            # ------------------------------------------------------------------
            # Handle heartbeat pong from client
            # ------------------------------------------------------------------
            try:
                msg = json.loads(raw)
                if isinstance(msg, dict) and msg.get("type") == "pong":
                    continue
            except (json.JSONDecodeError, TypeError):
                pass

            # ------------------------------------------------------------------
            # TASK-10.2 — Per-frame pipeline
            # ------------------------------------------------------------------
            now = time.monotonic()
            elapsed = now - state.last_frame_ts
            state.last_frame_ts = now

            response = await _process_frame_message(raw, elapsed, state)
            await websocket.send_text(json.dumps(response))

    except WebSocketDisconnect:
        logger.info("WS disconnected during processing: session_id=%s", session_id)
    except Exception as exc:
        logger.error("WS error for session %s: %s", session_id, exc)
    finally:
        stop_event.set()
        heartbeat_task.cancel()
        try:
            await heartbeat_task
        except asyncio.CancelledError:
            pass
        logger.info("WS handler exited: session_id=%s", session_id)


# ---------------------------------------------------------------------------
# Per-frame processing (async wrapper around sync pipeline)
# ---------------------------------------------------------------------------

async def _process_frame_message(
    raw: str,
    elapsed_seconds: float,
    state: _SessionState,
) -> dict:
    """
    Decode a client message, run the full pipeline, return response dict.

    Expected message format:
        {"frame": "<base64-encoded JPEG>", "exercise_hint": "squat"}
        OR raw base64 string (legacy).
    """
    # --- Decode message ---
    try:
        msg = json.loads(raw)
        if isinstance(msg, dict):
            b64 = msg.get("frame", "")
            exercise_hint = msg.get("exercise_hint", "squat")
        else:
            b64 = str(msg)
            exercise_hint = "squat"
    except (json.JSONDecodeError, TypeError):
        b64 = raw.strip()
        exercise_hint = "squat"

    # Decode base64 JPEG
    try:
        jpeg_bytes = base64.b64decode(b64)
    except Exception:
        return {"error": "Invalid base64 frame data"}

    t_start = time.monotonic()

    # --- Stage 1: CV pipeline ---
    exercise_for_cv = state.last_confirmed_type or exercise_hint
    processed = process_frame(jpeg_bytes, exercise_for_cv)

    # --- Stage 2: ML classification ---
    classification = state.ml_pipeline.classify_frame(
        processed.angle_map, elapsed_seconds
    )
    confirmed_type = classification.confirmed_type

    # --- TASK-10.3: Exercise-change handling ---
    if (
        confirmed_type is not None
        and confirmed_type != state.last_confirmed_type
    ):
        _handle_exercise_change(confirmed_type, state)

    # --- Stage 3: Form scoring ---
    scoring = score_frame(processed, confirmed_type)

    # --- Stage 4: Rep counting ---
    rep_state = state.rep_counter.update_rep_state(
        processed.angle_map, confirmed_type, elapsed_seconds
    )

    # --- Stage 5: Calorie running estimate ---
    current_ts = time.time()
    calories_running = state.calorie_engine.running_estimate(current_ts)

    # --- Update session manager state cache for persistence/interrupt ---
    session_manager.update_state_cache(
        rep_state, state.calorie_engine, state.form_tracker
    )

    # --- Add form score sample (only when not occluded and type confirmed) ---
    if not processed.occluded and confirmed_type is not None:
        state.form_tracker.add_sample(scoring.score)

    t_end = time.monotonic()
    latency_ms = (t_end - t_start) * 1000.0

    # --- TASK-10.4: Warning injection ---
    # Occlusion warning overrides unrecognised warning
    warning = ""
    if processed.occluded:
        warning = "Move into frame"
    elif classification.unrecognised_warning:
        warning = "Exercise not recognized — adjust position"

    # --- Serialize landmarks ---
    landmarks_out = []
    for lm in (processed.landmarks or []):
        if hasattr(lm, "id"):
            landmarks_out.append({
                "id": lm.id,
                "x": round(getattr(lm, "x", 0.0), 4),
                "y": round(getattr(lm, "y", 0.0), 4),
                "z": round(getattr(lm, "z", 0.0), 4),
                "visibility": round(getattr(lm, "visibility", 0.0), 4),
            })

    return {
        "exercise": confirmed_type,
        "rep_count": rep_state.rep_count,
        "set_number": rep_state.set_number,
        "form_score": scoring.score,
        "corrections": scoring.cues,
        "calories_running": round(calories_running, 4),
        "warning": warning,
        "landmarks": landmarks_out,
        "latency_ms": round(latency_ms, 1),
    }


# ---------------------------------------------------------------------------
# TASK-10.3 — Exercise-change handler
# ---------------------------------------------------------------------------

def _handle_exercise_change(new_type: str, state: _SessionState) -> None:
    """
    Handle a confirmed exercise-type transition.

    - Closes the open calorie segment and opens a new one for new_type.
    - SetTracker.exercise_changed() is called inside RepCounter already.
    - Updates state.last_confirmed_type.
    """
    ts = time.time()

    if state.segment_open:
        # Close current segment and open a new one
        state.calorie_engine.change_exercise(new_type, ts)
        logger.info(
            "Exercise change: %s → %s (session %s)",
            state.last_confirmed_type, new_type, state.session_id,
        )
    else:
        # First exercise confirmation this session — open initial segment
        state.calorie_engine.start_segment(new_type, ts)
        state.segment_open = True
        logger.info(
            "Exercise started: %s (session %s)", new_type, state.session_id
        )

    state.last_confirmed_type = new_type
