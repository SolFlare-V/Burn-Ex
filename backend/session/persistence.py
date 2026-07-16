"""
TASK-9.3 — Incremental persistence background task.

Runs as an asyncio periodic task every 30 seconds while a session is ACTIVE.
Writes current total_reps, total_calories, and avg_form_score to the
sessions row in the DB so that at most 30 seconds of data is lost on
abnormal termination.

Design ref: §2.6. REQs: REQ-6.6.

Usage (from the WebSocket handler or session start)::

    task = asyncio.create_task(
        run_persistence_loop(
            session_id=session_id,
            session_manager=mgr,
            get_rep_state=lambda: current_rep_state,
            get_calorie_engine=lambda: calorie_engine,
            get_form_tracker=lambda: form_tracker,
            stop_event=asyncio.Event(),
        )
    )
    # To stop: stop_event.set()
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from typing import Callable, Optional

from backend.database import SessionLocal
from backend.models.sessions import Session

logger = logging.getLogger(__name__)

PERSISTENCE_INTERVAL_SECONDS: float = 30.0


async def run_persistence_loop(
    session_id: str,
    get_rep_state: Callable,
    get_calorie_engine: Callable,
    get_form_tracker: Callable,
    stop_event: asyncio.Event,
    interval: float = PERSISTENCE_INTERVAL_SECONDS,
) -> None:
    """
    Periodically flush session state to the DB while the session is active.

    Args:
        session_id:         UUID of the active session.
        get_rep_state:      Zero-arg callable returning the current RepState.
        get_calorie_engine: Zero-arg callable returning the CalorieEngine.
        get_form_tracker:   Zero-arg callable returning the SetFormTracker.
        stop_event:         asyncio.Event — set this to stop the loop cleanly.
        interval:           Flush interval in seconds (default 30.0).
    """
    logger.info(
        "Persistence loop started for session %s (interval=%.0fs)",
        session_id, interval,
    )

    while not stop_event.is_set():
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            # stop_event was set — exit cleanly after one final flush
            await _flush(session_id, get_rep_state, get_calorie_engine, get_form_tracker)
            break
        except asyncio.TimeoutError:
            # Normal path: interval elapsed → flush
            await _flush(session_id, get_rep_state, get_calorie_engine, get_form_tracker)

    logger.info("Persistence loop stopped for session %s", session_id)


async def _flush(
    session_id: str,
    get_rep_state: Callable,
    get_calorie_engine: Callable,
    get_form_tracker: Callable,
) -> None:
    """Write current in-memory state to the sessions row."""
    import time

    rep_state = get_rep_state()
    calorie_engine = get_calorie_engine()
    form_tracker = get_form_tracker()

    # --- Compute totals ---
    total_reps = 0
    if rep_state is not None:
        total_reps = rep_state.rep_count
        if hasattr(rep_state, "sets_closed"):
            total_reps = (
                sum(getattr(s, "reps", 0) for s in rep_state.sets_closed)
                + rep_state.rep_count
            )

    total_calories = 0.0
    if calorie_engine is not None:
        total_calories = calorie_engine.running_estimate(time.time())

    avg_form_score: Optional[float] = None
    if form_tracker is not None:
        if hasattr(form_tracker, "sample_count") and form_tracker.sample_count > 0:
            avg_form_score = form_tracker.average()

    # --- DB write ---
    db = SessionLocal()
    try:
        row = db.query(Session).filter(Session.id == session_id).first()
        if row is None or row.status != "active":
            logger.warning(
                "Persistence flush skipped: session %s not found or not active",
                session_id,
            )
            return

        row.total_reps = total_reps
        row.total_calories = total_calories
        if avg_form_score is not None:
            row.avg_form_score = avg_form_score

        db.commit()
        logger.debug(
            "Flushed session %s: reps=%d calories=%.2f",
            session_id, total_reps, total_calories,
        )
    except Exception as exc:
        logger.error("Persistence flush failed for %s: %s", session_id, exc)
    finally:
        db.close()
