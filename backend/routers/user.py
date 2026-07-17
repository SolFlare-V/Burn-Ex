"""
TASK-11.9 — User profile REST endpoints.

GET /api/v1/user?user_id={id}
PUT /api/v1/user

Design ref: §3.1, §3.3. REQs: REQ-9.1–REQ-9.5.

Error codes:
  422 INVALID_WEIGHT       — weight_kg outside 20–300 range
  422 INVALID_HEIGHT       — height_cm outside 50–300 range
  409 WEIGHT_LOCKED_DURING_SESSION — weight update attempted while session active
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.database import SessionLocal
from backend.models.users import User
from backend.session.manager import session_manager

router = APIRouter(prefix="/api/v1/user", tags=["user"])

FITNESS_GOALS = {
    "lose_weight", "build_muscle", "get_toned", "stay_fit", "improve_endurance"
}

# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    id: int
    name: Optional[str] = None
    weight_kg: float
    height_cm: Optional[float] = None
    fitness_goal: Optional[str] = None
    created_at: datetime


class UserUpdate(BaseModel):
    user_id: int
    name: Optional[str] = None
    weight_kg: Optional[float] = None
    height_cm: Optional[float] = None
    fitness_goal: Optional[str] = None


class UserCreate(BaseModel):
    name: Optional[str] = None
    weight_kg: float
    height_cm: Optional[float] = None
    fitness_goal: Optional[str] = None


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _row_to_profile(row: User) -> UserProfile:
    return UserProfile(
        id=row.id,
        name=row.name,
        weight_kg=row.weight_kg,
        height_cm=row.height_cm,
        fitness_goal=row.fitness_goal,
        created_at=row.created_at,
    )


# ---------------------------------------------------------------------------
# TASK-11.9a — GET /api/v1/user
# ---------------------------------------------------------------------------

@router.get("", response_model=UserProfile)
def get_user(user_id: int):
    db = SessionLocal()
    try:
        row = db.query(User).filter(User.id == user_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")
        return _row_to_profile(row)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.10 — POST /api/v1/user
# ---------------------------------------------------------------------------

@router.post("", response_model=UserProfile)
def create_user(body: UserCreate):
    if body.weight_kg < 20 or body.weight_kg > 300:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_WEIGHT", "message": f"weight_kg must be 20–300, got {body.weight_kg}"},
        )
    if body.height_cm is not None and (body.height_cm < 50 or body.height_cm > 300):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_HEIGHT", "message": f"height_cm must be 50–300, got {body.height_cm}"},
        )
    if body.fitness_goal is not None and body.fitness_goal not in FITNESS_GOALS:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_GOAL", "message": f"fitness_goal must be one of {sorted(FITNESS_GOALS)}"},
        )

    db = SessionLocal()
    try:
        row = User(
            name=body.name,
            weight_kg=body.weight_kg,
            height_cm=body.height_cm,
            fitness_goal=body.fitness_goal,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return _row_to_profile(row)
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.9b — PUT /api/v1/user
# ---------------------------------------------------------------------------

@router.put("", response_model=UserProfile)
def update_user(body: UserUpdate):
    if body.weight_kg is not None:
        if body.weight_kg < 20 or body.weight_kg > 300:
            raise HTTPException(
                status_code=422,
                detail={"code": "INVALID_WEIGHT", "message": f"weight_kg must be 20–300, got {body.weight_kg}"},
            )
        if session_manager.active_session_id is not None:
            raise HTTPException(
                status_code=409,
                detail={"code": "WEIGHT_LOCKED_DURING_SESSION", "message": "Cannot update weight while a session is active"},
            )
    if body.height_cm is not None and (body.height_cm < 50 or body.height_cm > 300):
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_HEIGHT", "message": f"height_cm must be 50–300, got {body.height_cm}"},
        )
    if body.fitness_goal is not None and body.fitness_goal not in FITNESS_GOALS:
        raise HTTPException(
            status_code=422,
            detail={"code": "INVALID_GOAL", "message": f"fitness_goal must be one of {sorted(FITNESS_GOALS)}"},
        )

    db = SessionLocal()
    try:
        row = db.query(User).filter(User.id == body.user_id).first()
        if row is None:
            raise HTTPException(status_code=404, detail="User not found")

        if body.name is not None:
            row.name = body.name
        if body.weight_kg is not None:
            row.weight_kg = body.weight_kg
        if body.height_cm is not None:
            row.height_cm = body.height_cm
        if body.fitness_goal is not None:
            row.fitness_goal = body.fitness_goal

        db.commit()
        db.refresh(row)
        return _row_to_profile(row)
    finally:
        db.close()
