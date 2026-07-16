"""
TASK-11.7 — Streaks REST endpoint.

GET /api/v1/streaks?user_id={id}

Design ref: §3.1. REQs: REQ-7.5, REQ-7.6.
"""
from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.models.streaks import Streak

router = APIRouter(prefix="/api/v1/streaks", tags=["streaks"])


class StreakResponse(BaseModel):
    current: int
    best: int


@router.get("", response_model=StreakResponse)
def get_streaks(user_id: int):
    """Return current and best streak for user_id."""
    db = SessionLocal()
    try:
        row = db.query(Streak).filter(Streak.user_id == user_id).first()
        if row is None:
            return StreakResponse(current=0, best=0)
        return StreakResponse(current=row.current, best=row.best)
    finally:
        db.close()
