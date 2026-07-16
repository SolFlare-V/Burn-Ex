"""
TASK-11.5 / 11.6 -- Progress REST endpoints.

GET /api/v1/progress/calories  -- last 30 sessions calorie totals by date
GET /api/v1/progress/form      -- per-exercise form score trends

Design ref: sec 3.1. REQs: REQ-7.3, REQ-7.4.
"""
from __future__ import annotations

from collections import defaultdict
from typing import List, Optional

from fastapi import APIRouter
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.models.sessions import Session as SessionModel

router = APIRouter(prefix="/api/v1/progress", tags=["progress"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CaloriesEntry(BaseModel):
    date: str          # ISO date string YYYY-MM-DD
    calories: float


class FormTrend(BaseModel):
    exercise: str
    trend: List[float]


# ---------------------------------------------------------------------------
# TASK-11.5 -- GET /api/v1/progress/calories
# ---------------------------------------------------------------------------

@router.get("/calories", response_model=List[CaloriesEntry])
def progress_calories(user_id: Optional[int] = None):
    """Return last 30 completed sessions as [{ date, calories }], most recent first."""
    db = SessionLocal()
    try:
        q = db.query(SessionModel).filter(SessionModel.status == "completed")
        if user_id is not None:
            q = q.filter(SessionModel.user_id == user_id)
        rows = q.order_by(SessionModel.started_at.desc()).limit(30).all()
        return [
            CaloriesEntry(
                date=r.started_at.strftime("%Y-%m-%d"),
                calories=r.total_calories,
            )
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.6 -- GET /api/v1/progress/form
# ---------------------------------------------------------------------------

@router.get("/form", response_model=List[FormTrend])
def progress_form(user_id: Optional[int] = None):
    """
    Return per-exercise form score trends.

    For each exercise type that has >= 2 completed sessions with a non-null
    avg_form_score, return the last 10 scores in chronological order.
    Optionally filter by user_id.
    """
    db = SessionLocal()
    try:
        from backend.models.calorie_segments import CalorieSegment

        q = db.query(SessionModel).filter(
            SessionModel.status == "completed",
            SessionModel.avg_form_score.isnot(None),
        )
        if user_id is not None:
            q = q.filter(SessionModel.user_id == user_id)

        rows = q.order_by(SessionModel.started_at.asc()).all()

        # Group by exercise -- use first calorie segment's exercise type
        exercise_scores: dict[str, list[float]] = defaultdict(list)
        for row in rows:
            segs = (
                db.query(CalorieSegment)
                .filter(CalorieSegment.session_id == row.id)
                .order_by(CalorieSegment.started_at)
                .all()
            )
            if segs:
                exercise = segs[0].exercise
                exercise_scores[exercise].append(float(row.avg_form_score))

        result = []
        for exercise, scores in exercise_scores.items():
            if len(scores) >= 2:
                result.append(FormTrend(exercise=exercise, trend=scores[-10:]))

        return result
    finally:
        db.close()
