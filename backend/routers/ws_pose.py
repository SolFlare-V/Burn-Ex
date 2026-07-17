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
from concurrent.futures import ThreadPoolExecutor
from typing import Optional

from fastapi import WebSocket, WebSocketDisconnect
from fastapi.routing import APIRouter

from backend.calories.engine import CalorieEngine
from backend.calories.intensity import IntensityEstimator
from backend.cv.pipeline import process_frame
from backend.identity.manager import PersonSessionManager
from backend.ml.pipeline import MLPipeline
from backend.reps.counter import RepCounter
from backend.scoring.engine import score_frame
from backend.scoring.set_form_tracker import SetFormTracker
from backend.session.manager import session_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Thread pool for CPU-heavy synchronous work (MediaPipe + ML inference).
# Running these on the asyncio event loop thread blocked frame reception,
# causing a backlog of stale frames that processed long after movement stopped.
_cpu_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="cv_worker")

# ---------------------------------------------------------------------------
# Per-session person state cache (for /api/v1/persons query)
# Maps session_id → PersonSessionManager so the REST endpoint can read it.
# ---------------------------------------------------------------------------
_session_person_managers: dict[str, "PersonSessionManager"] = {}


# ---------------------------------------------------------------------------
# REST endpoint — persons summary (History / Sessions page)
# ---------------------------------------------------------------------------

from fastapi import Query
from fastapi.responses import JSONResponse

@router.get("/api/v1/persons")
async def get_persons(session_id: str = Query(...)):
    """
    Return all detected persons and their set history for the given session.
    Used by the History/Sessions UI page.

    Response shape:
      {
        "active_person_id": "uuid|null",
        "persons": [
          {
            "person_id": "uuid",
            "display_name": "Person 1",
            "first_seen_at": 1720000000.0,
            "last_seen_at":  1720000120.0,
            "total_calories": 42.3,
            "total_reps": 30,
            "sets": [
              { "set_number":1, "exercise":"squat", "reps":10,
                "calories":8.2, "avg_form_score":81.0,
                "timestamp":1720000050.0, "partial":false },
              ...
            ]
          },
          ...
        ]
      }
    """
    mgr = _session_person_managers.get(session_id)
    if mgr is None:
        return JSONResponse({"active_person_id": None, "persons": []})

    active_state = mgr.get_active_state()
    active_id = active_state.person_id if active_state else None

    # Include live running calorie estimate for the active person
    persons = []
    for ps in mgr.get_all_states():
        summary = ps.to_summary_dict()
        # For the active person, include the live running estimate
        if ps.person_id == active_id and ps.segment_open:
            summary["total_calories"] = round(
                ps.calorie_engine.running_estimate(
                    time.time(),
                    intensity_multiplier=ps.intensity_multiplier,
                ),
                3,
            )
        persons.append(summary)

    return JSONResponse({
        "active_person_id": active_id,
        "persons": persons,
    })

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

    def __init__(self, session_id: str, weight_kg: float, height_cm: float = 0.0) -> None:
        self.session_id = session_id
        self.weight_kg = weight_kg

        # Pipeline components
        self.ml_pipeline = MLPipeline()
        self.rep_counter = RepCounter()
        self.form_tracker = SetFormTracker()
        self.calorie_engine = CalorieEngine(weight_kg=weight_kg)
        # height_m is used by IntensityEstimator for height-calibrated COM scaling.
        # Falls back gracefully to uncalibrated mode if 0.0 (height not stored).
        height_m = (height_cm / 100.0) if (height_cm and height_cm > 0) else 0.0
        self.intensity_estimator = IntensityEstimator(fps=15.0, height_m=height_m)

        # Current smoothed intensity multiplier (updated every frame)
        self.intensity_multiplier: float = 1.0

        # Exercise-change tracking (TASK-10.3)
        self.last_confirmed_type: Optional[str] = None

        # Calorie segment open flag
        self.segment_open = False

        # Timing
        self.last_frame_ts: float = time.monotonic()

        # Person identification manager (Step 4).
        # Runs InsightFace in a background thread every ~25 frames.
        # The calorie engine and per-frame pipeline state above are the
        # *fallback* single-user state used when the manager has no active
        # person yet (first ~2s before first identification completes).
        self.person_manager = PersonSessionManager(
            weight_kg=weight_kg,
            height_cm=height_cm,
        )


# ---------------------------------------------------------------------------
# Helper: resolve active session weight from DB
# ---------------------------------------------------------------------------

def _get_session_weight(session_id: str) -> Optional[tuple[float, float]]:
    """
    Return (weight_kg, height_cm) for session_id's user, or None if not found/active.

    height_cm may be None in the DB (field added later); defaults to 0.0 so
    the caller can pass it to _SessionState without a None-check.
    """
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
        weight = float(user.weight_kg)
        height = float(user.height_cm) if getattr(user, "height_cm", None) else 0.0
        return weight, height
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

    result = _get_session_weight(session_id)
    if result is None:
        await websocket.close(code=_CLOSE_CODE_INVALID)
        logger.info("WS rejected: session_id=%s not active", session_id)
        return
    weight_kg, height_cm = result

    await websocket.accept()
    logger.info("WS accepted: session_id=%s weight=%.1f", session_id, weight_kg)

    state = _SessionState(session_id=session_id, weight_kg=weight_kg, height_cm=height_cm)

    # Register manager in the global cache so /api/v1/persons can read it
    _session_person_managers[session_id] = state.person_manager

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

            # Drop stale frames: if the previous frame took >150ms to process,
            # the client may have queued several more. Drain them without
            # processing so we only act on the most current frame.
            if elapsed > 0.15:
                try:
                    # Non-blocking drain of any buffered messages
                    while True:
                        drained = await asyncio.wait_for(
                            websocket.receive_text(), timeout=0.001
                        )
                        try:
                            dm = json.loads(drained)
                            if isinstance(dm, dict) and dm.get("type") == "pong":
                                continue  # keep pong handling
                        except Exception:
                            pass
                        raw = drained  # use the most recent frame
                        now = time.monotonic()
                        elapsed = now - state.last_frame_ts
                        state.last_frame_ts = now
                except asyncio.TimeoutError:
                    pass  # nothing more buffered

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
        # Remove manager from global cache
        _session_person_managers.pop(session_id, None)
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
            # Echo capture timestamp back to client for round-trip lag measurement
            capture_ts_echo = msg.get("capture_ts")
        else:
            b64 = str(msg)
            capture_ts_echo = None
    except (json.JSONDecodeError, TypeError):
        b64 = raw.strip()
        capture_ts_echo = None

    # Decode base64 JPEG
    try:
        jpeg_bytes = base64.b64decode(b64)
    except Exception:
        return {"error": "Invalid base64 frame data"}

    t_start = time.monotonic()

    # --- Person identification tick (Step 4) ---
    # Runs InsightFace in the background thread pool every ~25 frames.
    # Returns the active person_id (may be None for first ~2s).
    # Does NOT block the frame pipeline — identification is async.
    loop = asyncio.get_event_loop()
    active_person_id = state.person_manager.tick(jpeg_bytes, loop, _cpu_executor)
    active_ps = state.person_manager.get_active_state()

    # If a person is identified, use their per-person pipeline components;
    # otherwise fall back to the top-level _SessionState components.
    # The calorie engine and all stateful components are independent per person.
    if active_ps is not None:
        ml_pipeline      = active_ps.ml_pipeline
        rep_counter      = active_ps.rep_counter
        form_tracker     = active_ps.form_tracker
        calorie_engine   = active_ps.calorie_engine
        intensity_est    = active_ps.intensity_estimator
        person_weight    = active_ps.weight_kg
        segment_open_ref = active_ps   # mutable attrs read/written via active_ps
    else:
        # No person confirmed yet — use session-level fallback
        ml_pipeline      = state.ml_pipeline
        rep_counter      = state.rep_counter
        form_tracker     = state.form_tracker
        calorie_engine   = state.calorie_engine
        intensity_est    = state.intensity_estimator
        person_weight    = state.weight_kg
        segment_open_ref = state

    # --- Stage 1: CV pipeline (run in thread pool so event loop stays free) ---
    # Previously this ran synchronously on the event loop thread, blocking
    # frame reception for ~80-120ms per frame. Frames queued in the OS socket
    # buffer and processed long after the user stopped moving.
    exercise_for_cv = segment_open_ref.last_confirmed_type
    processed = await loop.run_in_executor(
        _cpu_executor,
        process_frame,
        jpeg_bytes,
        exercise_for_cv,
    )

    # Notify calorie engine that a real frame arrived (gates idle detection).
    current_ts = time.time()
    calorie_engine.notify_frame(current_ts)

    # If no person is detected (screen black, camera covered) close any open
    # calorie segment so calories stop accumulating during the blackout.
    if processed.occluded and not processed.landmarks:
        if segment_open_ref.segment_open and calorie_engine._open_segment is not None:
            calorie_engine.close_segment(
                current_ts,
                intensity_multiplier=segment_open_ref.intensity_multiplier,
            )
            segment_open_ref.segment_open = False
            logger.debug("Calorie segment closed: no person in frame (session %s)", state.session_id)

    # --- Stage 2: ML classification (also in thread pool) ---
    classification = await loop.run_in_executor(
        _cpu_executor,
        ml_pipeline.classify_frame,
        processed.angle_map,
        elapsed_seconds,
    )
    confirmed_type = classification.confirmed_type

    # --- TASK-10.3: Exercise-change handling ---
    if (
        confirmed_type is not None
        and confirmed_type != segment_open_ref.last_confirmed_type
    ):
        _handle_exercise_change(
            confirmed_type, segment_open_ref,
            calorie_engine=calorie_engine,
            intensity_est=intensity_est,
            class_probabilities=classification.class_probabilities,
        )

    # --- Drop-out handling ---
    elif confirmed_type is None and segment_open_ref.last_confirmed_type is not None:
        ts = time.time()
        if segment_open_ref.segment_open:
            try:
                calorie_engine.close_segment(
                    ts,
                    intensity_multiplier=segment_open_ref.intensity_multiplier,
                    class_probabilities=classification.class_probabilities,
                )
            except RuntimeError:
                pass
            segment_open_ref.segment_open = False
        segment_open_ref.last_confirmed_type = None

    # --- Stage 3: Intensity estimation ---
    intensity_result = intensity_est.update(
        landmarks=processed.landmarks or [],
        angle_map=processed.angle_map,
        exercise_type=confirmed_type,
        elapsed_s=elapsed_seconds,
        classifier_confidence=classification.confidence,
        weight_kg=person_weight,
    )
    segment_open_ref.intensity_multiplier = intensity_result.multiplier

    # --- Stage 4: Form scoring ---
    scoring = score_frame(processed, confirmed_type)

    # --- Stage 5: Rep counting ---
    rep_state = rep_counter.update_rep_state(
        processed.angle_map, confirmed_type, elapsed_seconds
    )

    # --- Stage 6: Calorie running estimate ---
    calories_running = calorie_engine.running_estimate(
        current_ts,
        intensity_multiplier=segment_open_ref.intensity_multiplier,
        class_probabilities=classification.class_probabilities,
        general_activity_met=intensity_result.general_activity_met,
    )

    # General activity calories when no segment is open (P1-I4).
    if not segment_open_ref.segment_open and intensity_result.general_activity_met > 0.0:
        elapsed_h = elapsed_seconds / 3600.0
        calories_running += (
            intensity_result.general_activity_met * person_weight * elapsed_h
        )

    # --- Add form score sample (only when not occluded and type confirmed) ---
    # --- Update session manager state cache ---
    session_manager.update_state_cache(
        rep_state, calorie_engine, form_tracker
    )

    # --- Add form score sample ---
    if not processed.occluded and confirmed_type is not None:
        form_tracker.add_sample(scoring.score)

    t_end = time.monotonic()
    latency_ms = (t_end - t_start) * 1000.0

    # --- TASK-10.4: Warning injection ---
    # Priority: no-body > occluded > step-back > unrecognised
    warning = ""

    # Detect face-only framing: landmarks present but none of the key
    # exercise landmarks (shoulders=11,12, hips=23,24) are visible.
    # This means the camera is too close / pointed at face only.
    # Use a lower visibility threshold (0.3) for shoulder presence check
    # since MediaPipe often returns shoulders at low confidence in close-up views.
    landmark_ids_any = {lm.id for lm in (processed.landmarks or []) if lm.visibility >= 0.3}
    landmark_ids_confident = {lm.id for lm in (processed.landmarks or []) if lm.visibility >= 0.5}
    has_shoulders = bool(landmark_ids_confident & {11, 12})
    has_hips = bool(landmark_ids_confident & {23, 24})
    has_elbows = bool(landmark_ids_confident & {13, 14})

    # No useful body landmarks at all — face close-up
    body_landmark_count = len(landmark_ids_confident & set(range(11, 33)))

    if processed.landmarks and body_landmark_count < 4:
        warning = "Step back — point camera at your full body"
    elif processed.occluded:
        warning = "Move into frame"
    elif has_shoulders and not has_elbows and confirmed_type is None:
        warning = "Move back so your arms are fully visible"
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

    # Compute weighted MET for debug output
    from backend.calories.engine import _compute_weighted_met, _load_met_values
    _wmet = _compute_weighted_met(classification.class_probabilities)
    if _wmet <= 0.0 and confirmed_type:
        _wmet = _load_met_values().get(confirmed_type, 0.0)

    return {
        "exercise": confirmed_type,
        "rep_count": rep_state.rep_count,
        "set_number": rep_state.set_number,
        "form_score": scoring.score,
        "corrections": scoring.cues,
        "calories_running": round(calories_running, 4),
        "calorie_confidence": round(intensity_result.calorie_confidence, 3),
        "calorie_ci_lower": round(calories_running * (1 - intensity_result.calorie_ci_relative_error), 3),
        "calorie_ci_upper": round(calories_running * (1 + intensity_result.calorie_ci_relative_error), 3),
        "warning": warning,
        "landmarks": landmarks_out,
        "latency_ms": round(latency_ms, 1),
        "capture_ts_echo": capture_ts_echo,
        "_confidence": round(classification.confidence, 3),
        "_angle_count": len(processed.angle_map),
        "_intensity_multiplier": round(segment_open_ref.intensity_multiplier, 3),
        "_intensity_is_resting": intensity_result.is_resting,
        "_intensity_is_static": intensity_result.is_static_hold,
        "_intensity_height_scale": round(intensity_est._scale_m_per_norm, 4),
        "_weighted_met": round(_wmet, 3),
        "_fatigue_index": round(intensity_result.fatigue_index, 3),
        "_symmetry_index": round(intensity_result.symmetry_index, 3),
        "_general_activity_met": round(intensity_result.general_activity_met, 2),
        # Person identification fields (Step 4)
        "active_person_id": active_person_id,
        "active_person_name": active_ps.display_name if active_ps else None,
        "person_count": state.person_manager.person_count(),
    }


# ---------------------------------------------------------------------------
# TASK-10.3 — Exercise-change handler
# ---------------------------------------------------------------------------

def _handle_exercise_change(
    new_type: str,
    state_ref,   # _SessionState or PersonSessionState — duck-typed
    calorie_engine=None,
    intensity_est=None,
    class_probabilities: Optional[dict[str, float]] = None,
) -> None:
    """
    Handle a confirmed exercise-type transition.

    Accepts either a _SessionState or PersonSessionState via duck-typing.
    calorie_engine and intensity_est are passed explicitly so the per-person
    components are used rather than the fallback session-level ones.
    """
    # Resolve components — explicit params take priority over state attributes
    _ce = calorie_engine if calorie_engine is not None else state_ref.calorie_engine
    _ie = intensity_est if intensity_est is not None else state_ref.intensity_estimator

    ts = time.time()

    if state_ref.segment_open:
        _ce.change_exercise(
            new_type,
            ts,
            intensity_multiplier=state_ref.intensity_multiplier,
            class_probabilities=class_probabilities,
        )
        _ie.reset()
        logger.info(
            "Exercise change: %s → %s",
            state_ref.last_confirmed_type, new_type,
        )
    else:
        _ce.start_segment(new_type, ts)
        state_ref.segment_open = True
        logger.info("Exercise started: %s", new_type)

    state_ref.last_confirmed_type = new_type
