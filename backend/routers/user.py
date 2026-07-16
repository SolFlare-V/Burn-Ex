"""
TASK-11.9 — User profile REST endpoints.

GET /api/v1/user?user_id={id}
PUT /api/v1/user

Design ref: §3.1, §3.3. REQs: REQ-9.1–REQ-9.5.

Error codes:
  422 INVALID_WEIGHT       — weight_kg outside 20–300 range
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


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class UserProfile(BaseModel):
    id: int
    name: Optional[str] = None
    weight_kg: float
    created_at: datetime


class UserUpdate(BaseModel):
    user_id: int
    name: Optional[str] = None
    weight_kg: Optional[float] = None


class UserCreate(BaseModel):
    name: Optional[str] = None
    weight_kg: float



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
        return UserProfile(
            id=row.id,
            name=row.name,
            weight_kg=row.weight_kg,
            created_at=row.created_at,
        )
    finally:
        db.close()


# ---------------------------------------------------------------------------
# TASK-11.10 — POST /api/v1/user
# ---------------------------------------------------------------------------

@router.post("", response_model=UserProfile)
def create_user(body: UserCreate):
    # Validate weight range before any DB work
    if body.weight_kg < 20 or body.weight_kg > 300:
        raise HTTPException(
            status_code=422,
            detail={
                "code": "INVALID_WEIGHT",
                "message": f"weight_kg must be between 20 and 300, got {body.weight_kg}",
            },
        )

    db = SessionLocal()
    try:
        row = User(
            name=body.name,
            weight_kg=body.weight_kg,
        )
        db.add(row)
        db.commit()
        db.refresh(row)
        return UserProfile(
            id=row.id,
            name=row.name,
            weight_kg=row.weight_kg,
            created_at=row.created_at,
        )
    finally:
        db.close()



# ---------------------------------------------------------------------------
# TASK-11.9b — PUT /api/v1/user
# ---------------------------------------------------------------------------

@router.put("", response_model=UserProfile)
def update_user(body: UserUpdate):
    # Validate weight range before any DB work
    if body.weight_kg is not None:
        if body.weight_kg < 20 or body.weight_kg > 300:
            raise HTTPException(
                status_code=422,
                detail={
                    "code": "INVALID_WEIGHT",
                    "message": f"weight_kg must be between 20 and 300, got {body.weight_kg}",
                },
            )
        # Block weight change during active session
        if session_manager.active_session_id is not None:
            raise HTTPException(
                status_code=409,
                detail={
                    "code": "WEIGHT_LOCKED_DURING_SESSION",
                    "message": "Cannot update weight while a session is active",
                },
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

        db.commit()
        db.refresh(row)
        return UserProfile(
            id=row.id,
            name=row.name,
            weight_kg=row.weight_kg,
            created_at=row.created_at,
        )
    finally:
        db.close()
