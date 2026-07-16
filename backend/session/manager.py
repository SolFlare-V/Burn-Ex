"""
TASK-9.1 / TASK-9.2 / TASK-9.4 — Session Manager.

Lifecycle state machine:
    IDLE → ACTIVE → ENDED / INTERRUPTED

Design ref: §2.6, §7.3. REQs: REQ-6.1, REQ-6.2, REQ-6.3, REQ-5.2, REQ-6.5.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session as DBSession

from backend.database import SessionLocal
from backend.models.sessions import Session
from backend.models.sets import Set
from backend.models.calorie_segments import CalorieSegment


# ---------------------------------------------------------------------------
# Custom exceptions
# ---------------------------------------------------------------------------

class WeightRequiredError(ValueError):
    """Raised when weight_kg is zero or negative at session start."""


class SessionAlreadyActiveError(RuntimeError):
    """Raised when a second session is started while one is still active."""


class SessionNotFoundError(LookupError):
    """Raised when the requested session_id does not exist."""


# ---------------------------------------------------------------------------
# Session Manager
# ---------------------------------------------------------------------------

class SessionManager:
    """
    Manages the lifecycle of a single active workout session.

    Maintains a global ``active_session_id`` to enforce the single-session
    constraint (REQ-6.5).  All state is stored in SQLite so it survives
    process restarts after interruptions.
    """

    def __init__(self) -> None:
        # Global guard — only one active session at a time.
        self._active_session_id: Optional[str] = None

        # In-memory cache of the last-known rep/calorie/form state for the
        # incremental persistence task (TASK-9.3).
        self._rep_state = None
        self._calorie_engine = None
        self._form_tracker = None

    # ------------------------------------------------------------------
    # TASK-9.1 — start_session
    # ------------------------------------------------------------------

    def start_session(self, user_id: int, weight_kg: float) -> str:
        """
        Create a new active session for *user_id*.

        Args:
            user_id:   ID of the user starting the session.
            weight_kg: User's body weight in kg. Must be > 0.

        Returns:
            The new session's UUID string.

        Raises:
            WeightRequiredError:      If weight_kg <= 0.
            SessionAlreadyActiveError: If another session is already active.
        """
        if weight_kg <= 0:
            raise WeightRequiredError(
                f"weight_kg must be > 0 to start a session, got {weight_kg!r}. "
                "Please update your profile with a valid weight."
            )

        if self._active_session_id is not None:
            raise SessionAlreadyActiveError(
                f"Session {self._active_session_id!r} is already active. "
                "End or interrupt the current session before starting a new one."
            )

        session_id = str(uuid.uuid4())

        db: DBSession = SessionLocal()
        try:
            row = Session(
                id=session_id,
                user_id=user_id,
                started_at=datetime.now(timezone.utc),
                status="active",
                total_reps=0,
                total_calories=0.0,
            )
            db.add(row)
            db.commit()
        finally:
            db.close()

        self._active_session_id = session_id
        return session_id

    # ------------------------------------------------------------------
    # TASK-9.2 — end_session
    # ------------------------------------------------------------------

    def end_session(
        self,
        session_id: str,
        rep_state=None,
        calorie_engine=None,
        form_tracker=None,
    ) -> Session:
        """
        Finalise the session and write the complete summary to the DB.

        Computes total_calories from calorie_engine, avg_form_score from
        form_tracker, persists calorie_segments rows, closes open sets,
        and sets status="completed".

        Args:
            session_id:     The UUID of the session to end.
            rep_state:      RepState from the Rep Counter (or None).
            calorie_engine: CalorieEngine instance (or None).
            form_tracker:   SetFormTracker instance (or None).

        Returns:
            The updated Session ORM row.

        Raises:
            SessionNotFoundError: If session_id is not found in the DB.
        """
        import time
        from backend.calories.engine import CalorieEngine

        db: DBSession = SessionLocal()
        try:
            row = db.query(Session).filter(Session.id == session_id).first()
            if row is None:
                raise SessionNotFoundError(f"Session {session_id!r} not found.")

            now = datetime.now(timezone.utc)
            started_ts = row.started_at.timestamp() if row.started_at else 0.0
            ended_ts = now.timestamp()
            duration_s = int(ended_ts - started_ts)

            # --- Calorie finalisation ---
            total_calories = 0.0
            if calorie_engine is not None:
                # Close any open segment
                open_seg = calorie_engine._open_segment
                if open_seg is not None:
                    calorie_engine.close_segment(ended_ts)

                total_calories = calorie_engine.running_total()

                # Persist calorie_segments rows
                for seg in calorie_engine.segments:
                    if seg.end_time is not None:
                        cs = CalorieSegment(
                            session_id=session_id,
                            exercise=seg.exercise_type,
                            weight_kg=seg.weight_kg,
                            started_at=datetime.fromtimestamp(seg.start_time, tz=timezone.utc),
                            ended_at=datetime.fromtimestamp(seg.end_time, tz=timezone.utc),
                            calories=seg.calories,
                            duration_seconds=seg.duration_seconds,
                        )
                        db.add(cs)

            # --- Rep count ---
            total_reps = 0
            if rep_state is not None:
                total_reps = rep_state.rep_count
                # Count reps from all closed sets too
                if hasattr(rep_state, 'sets_closed'):
                    total_reps = sum(
                        getattr(s, 'reps', 0) for s in rep_state.sets_closed
                    ) + rep_state.rep_count

            # --- Form score ---
            avg_form_score = None
            if form_tracker is not None:
                avg = form_tracker.average()
                avg_form_score = avg if avg < 100.0 or (
                    hasattr(form_tracker, 'sample_count') and form_tracker.sample_count > 0
                ) else None

            # Close any open sets for this session
            open_sets = (
                db.query(Set)
                .filter(Set.session_id == session_id, Set.closed_at == None)
                .all()
            )
            for s in open_sets:
                s.closed_at = now

            # Write final session record
            row.ended_at = now
            row.status = "completed"
            row.total_reps = total_reps
            row.total_calories = total_calories
            row.avg_form_score = avg_form_score
            row.duration_seconds = duration_s

            db.commit()
            db.refresh(row)
            result = row
        finally:
            db.close()

        self._active_session_id = None
        self._rep_state = None
        self._calorie_engine = None
        self._form_tracker = None
        return result

    # ------------------------------------------------------------------
    # TASK-9.4 — interrupt_session
    # ------------------------------------------------------------------

    def interrupt_session(self, session_id: str) -> Session:
        """
        Flush current state to DB and set status="interrupted".

        Called by the WebSocket disconnect handler (TASK-10) when the
        heartbeat pong is missed 3× or the connection drops unexpectedly.

        Args:
            session_id: The UUID of the session to interrupt.

        Returns:
            The updated Session ORM row.

        Raises:
            SessionNotFoundError: If session_id not found.
        """
        db: DBSession = SessionLocal()
        try:
            row = db.query(Session).filter(Session.id == session_id).first()
            if row is None:
                raise SessionNotFoundError(f"Session {session_id!r} not found.")

            now = datetime.now(timezone.utc)
            started_ts = row.started_at.timestamp() if row.started_at else 0.0
            ended_ts = now.timestamp()
            duration_s = int(ended_ts - started_ts)

            # Write whatever partial state is cached in memory
            total_calories = 0.0
            if self._calorie_engine is not None:
                open_seg = self._calorie_engine._open_segment
                if open_seg is not None:
                    # Provisional estimate without closing the segment
                    from backend.calories.engine import _load_met_values
                    elapsed_h = max(0, ended_ts - open_seg.start_time) / 3600.0
                    met = _load_met_values().get(open_seg.exercise_type, 0.0)
                    provisional = met * open_seg.weight_kg * elapsed_h
                    total_calories = self._calorie_engine.running_total() + provisional
                else:
                    total_calories = self._calorie_engine.running_total()

            total_reps = 0
            if self._rep_state is not None:
                total_reps = self._rep_state.rep_count
                if hasattr(self._rep_state, 'sets_closed'):
                    total_reps = sum(
                        getattr(s, 'reps', 0) for s in self._rep_state.sets_closed
                    ) + self._rep_state.rep_count

            row.status = "interrupted"
            row.total_reps = total_reps
            row.total_calories = total_calories
            row.duration_seconds = duration_s

            db.commit()
            db.refresh(row)
            result = row
        finally:
            db.close()

        self._active_session_id = None
        self._rep_state = None
        self._calorie_engine = None
        self._form_tracker = None
        return result

    # ------------------------------------------------------------------
    # State cache updater (called by persistence task and WS loop)
    # ------------------------------------------------------------------

    def update_state_cache(self, rep_state, calorie_engine, form_tracker) -> None:
        """Update the in-memory state cache used by persistence and interrupt."""
        self._rep_state = rep_state
        self._calorie_engine = calorie_engine
        self._form_tracker = form_tracker

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def active_session_id(self) -> Optional[str]:
        """The currently active session ID, or None."""
        return self._active_session_id


# ---------------------------------------------------------------------------
# Module-level singleton (shared by routers, WS handler, persistence task)
# ---------------------------------------------------------------------------
session_manager = SessionManager()
