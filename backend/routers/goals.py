"""
TASK-11.8 — Goals REST endpoints.

GET  /api/v1/goals?user_id={id}
POST /api/v1/goals
GET  /api/v1/goals/progress?user_id={id}

Design ref: §3.1. REQs: REQ-7.7, REQ-7.8.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.models.goals import Goal
from backend.models.sessions import Session as SessionModel

router = APIRouter(prefix="/api/v1/goals", tags=["goals"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class GoalCreate(BaseModel):
    user_id: int
    type: str          # "daily" | "weekly"
    target_calories: float


class GoalResponse(BaseModel):
    id: int
    user_id: int
    type: str
    target_calories: float
    active: bool
    created_at: datetime


class GoalProgressItem(BaseModel):
    type: str
    target_calories: float
    achieved_calories: float
    achieved: bool


# ---------------------------------------------------------------------------
# TASK-11.8a — GET /api/v1/goals
# ---------------------------------------------------------------------------

@router.get("", response_model=List[GoalResponse])
def list_goals(user_id: int):
    db = SessionLocal()
    try:
        rows = (
            db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.active == True)
            .order_by(Goal.created_at.desc())
            .all()
        )
        return [
            GoalResponse(
                id=r.id,
                user_id=r.user_id,
                type=r.type,
                target_calories=r.target_calories,
                active=r.active,
                created_at=r.created_at,
            )
            for r in rows
        ]
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.8b — POST /api/v1/goals
# ---------------------------------------------------------------------------

@router.post("", response_model=GoalResponse, status_code=201)
def create_goal(body: GoalCreate):
    if body.type not in ("daily", "weekly"):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_GOAL_TYPE", "message": "type must be 'daily' or 'weekly'"},
        )
    if body.target_calories <= 0:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_TARGET", "message": "target_calories must be > 0"},
        )

    db = SessionLocal()
    try:
        # Deactivate any existing goal of the same type for this user
        db.query(Goal).filter(
            Goal.user_id == body.user_id,
            Goal.type == body.type,
            Goal.active == True,
        ).update({"active": False})

        row = Goal(
            user_id=body.user_id,
            type=body.type,
            target_calories=body.target_calories,
            active=True,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return GoalResponse(
            id=row.id,
            user_id=row.user_id,
            type=row.type,
            target_calories=row.target_calories,
            active=row.active,
            created_at=row.created_at,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.8c — GET /api/v1/goals/progress
# ---------------------------------------------------------------------------

@router.get("/progress", response_model=List[GoalProgressItem])
def goals_progress(user_id: int):
    """
    Return achieved vs target for each active goal.

    Daily:  sum completed session calories for today (UTC).
    Weekly: sum completed session calories for current Mon–Sun week (UTC).
    """
    db = SessionLocal()
    try:
        goals = (
            db.query(Goal)
            .filter(Goal.user_id == user_id, Goal.active == True)
            .all()
        )
        if not goals:
            return []

        now = datetime.now(timezone.utc)
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        week_start = today_start - timedelta(days=today_start.weekday())  # Monday

        def _sum_calories(since: datetime) -> float:
            rows = (
                db.query(SessionModel)
                .filter(
                    SessionModel.user_id == user_id,
                    SessionModel.status == "completed",
                    SessionModel.started_at >= since,
                )
                .all()
            )
            return sum(r.total_calories for r in rows)

        result = []
        for goal in goals:
            if goal.type == "daily":
                achieved = _sum_calories(today_start)
            else:  # weekly
                achieved = _sum_calories(week_start)

            result.append(
                GoalProgressItem(
                    type=goal.type,
                    target_calories=goal.target_calories,
                    achieved_calories=achieved,
                    achieved=achieved >= goal.target_calories,
                )
            )
        return result
    finally:
        db.close()
