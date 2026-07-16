"""
TASK-11.1 / 11.2 / 11.3 / 11.4 — Session REST endpoints.

POST  /api/v1/sessions/start
POST  /api/v1/sessions/{id}/end
GET   /api/v1/sessions
GET   /api/v1/sessions/{id}

Design ref: §3.1, §3.3. REQs: REQ-6.1, REQ-6.2, REQ-7.1, REQ-7.2.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.models.calorie_segments import CalorieSegment as CalorieSegmentModel
from backend.models.sessions import Session as SessionModel
from backend.models.sets import Set as SetModel
from backend.session.manager import (
    SessionAlreadyActiveError,
    WeightRequiredError,
    session_manager,
)

router = APIRouter(prefix="/api/v1/sessions", tags=["sessions"])


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class StartRequest(BaseModel):
    user_id: int


class StartResponse(BaseModel):
    session_id: str
    started_at: datetime


class SetSummary(BaseModel):
    id: int
    set_number: int
    exercise: str
    reps: int
    hold_seconds: Optional[int] = None
    avg_form_score: Optional[float] = None
    closed_at: Optional[datetime] = None


class CalorieSegmentSummary(BaseModel):
    exercise: str
    calories: Optional[float] = None
    duration_seconds: Optional[int] = None
    started_at: datetime
    ended_at: Optional[datetime] = None


class SessionSummary(BaseModel):
    session_id: str
    started_at: datetime
    ended_at: Optional[datetime] = None
    status: str
    total_reps: int
    total_calories: float
    avg_form_score: Optional[float] = None
    duration_seconds: Optional[int] = None


class SessionDetail(SessionSummary):
    sets: List[SetSummary] = []
    form_score_trend: List[float] = []
    calorie_segments: List[CalorieSegmentSummary] = []


# ---------------------------------------------------------------------------
# TASK-11.1 — POST /api/v1/sessions/start
# ---------------------------------------------------------------------------

@router.post("/start", response_model=StartResponse)
def start_session(body: StartRequest):
    from backend.database import SessionLocal
    from backend.models.users import User

    db = SessionLocal()
    try:
        user = db.query(User).filter(User.id == body.user_id).first()
        if user is None:
            raise HTTPException(status_code=404, detail="User not found")
        weight_kg = float(user.weight_kg)
    finally:
        db.close()

    try:
        session_id = session_manager.start_session(
            user_id=body.user_id, weight_kg=weight_kg
        )
    except WeightRequiredError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": "WEIGHT_REQUIRED", "message": str(exc)},
        )
    except SessionAlreadyActiveError as exc:
        raise HTTPException(
            status_code=409,
            detail={"code": "SESSION_ALREADY_ACTIVE", "message": str(exc)},
        )

    db = SessionLocal()
    try:
        row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        started_at = row.started_at
    finally:
        db.close()

    return StartResponse(session_id=session_id, started_at=started_at)


# ---------------------------------------------------------------------------
# TASK-11.2 — POST /api/v1/sessions/{id}/end
# ---------------------------------------------------------------------------

@router.post("/{session_id}/end", response_model=SessionSummary)
def end_session(session_id: str):
    from backend.session.manager import SessionNotFoundError

    try:
        row = session_manager.end_session(session_id)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SessionSummary(
        session_id=row.id,
        started_at=row.started_at,
        ended_at=row.ended_at,
        status=row.status,
        total_reps=row.total_reps,
        total_calories=row.total_calories,
        avg_form_score=row.avg_form_score,
        duration_seconds=row.duration_seconds,
    )


# ---------------------------------------------------------------------------
# TASK-11.3 — GET /api/v1/sessions
# ---------------------------------------------------------------------------

@router.get("", response_model=List[SessionSummary])
def list_sessions(limit: int = 20, offset: int = 0):
    db = SessionLocal()
    try:
        rows = (
            db.query(SessionModel)
            .order_by(SessionModel.started_at.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )
        return [
            SessionSummary(
                session_id=r.id,
                started_at=r.started_at,
                ended_at=r.ended_at,
                status=r.status,
                total_reps=r.total_reps,
                total_calories=r.total_calories,
                avg_form_score=r.avg_form_score,
                duration_seconds=r.duration_seconds,
            )
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.4 — GET /api/v1/sessions/{id}
# ---------------------------------------------------------------------------

@router.get("/{session_id}", response_model=SessionDetail)
def get_session(session_id: str):
    db = SessionLocal()
    try:
        row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found")

        sets = (
            db.query(SetModel)
            .filter(SetModel.session_id == session_id)
            .order_by(SetModel.set_number)
            .all()
        )
        segs = (
            db.query(CalorieSegmentModel)
            .filter(CalorieSegmentModel.session_id == session_id)
            .order_by(CalorieSegmentModel.started_at)
            .all()
        )

        form_scores = [s.avg_form_score for s in sets if s.avg_form_score is not None]

        return SessionDetail(
            session_id=row.id,
            started_at=row.started_at,
            ended_at=row.ended_at,
            status=row.status,
            total_reps=row.total_reps,
            total_calories=row.total_calories,
            avg_form_score=row.avg_form_score,
            duration_seconds=row.duration_seconds,
            sets=[
                SetSummary(
                    id=s.id,
                    set_number=s.set_number,
                    exercise=s.exercise,
                    reps=s.reps,
                    hold_seconds=s.hold_seconds,
                    avg_form_score=s.avg_form_score,
                    closed_at=s.closed_at,
                )
                for s in sets
            ],
            form_score_trend=form_scores,
            calorie_segments=[
                CalorieSegmentSummary(
                    exercise=seg.exercise,
                    calories=seg.calories,
                    duration_seconds=seg.duration_seconds,
                    started_at=seg.started_at,
                    ended_at=seg.ended_at,
                )
                for seg in segs
            ],
        )
    finally:
        db.close()
