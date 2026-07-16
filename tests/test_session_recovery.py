"""
TASK-16.6 — Integration test for interrupted session recovery.

Tests:
  1. Start a session, simulate incremental persistence write,
     call interrupt_session, assert DB row has status='interrupted'
     and non-zero rep/calorie data.
  2. Seed a row with status='interrupted' and confirm
     GET /api/v1/sessions returns it.

Verify: pytest tests/test_session_recovery.py passes.
"""
import sys
import os
import uuid
import time
from datetime import datetime, timezone

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from backend.database import Base, SessionLocal, engine
import backend.models.users, backend.models.sessions, backend.models.sets
import backend.models.calorie_segments, backend.models.streaks, backend.models.goals
Base.metadata.create_all(engine)

from backend.models.users import User
from backend.models.sessions import Session as SessionModel
from backend.session.manager import SessionManager
from backend.session.persistence import run_persistence_loop
from backend.calories.engine import CalorieEngine
from backend.scoring.set_form_tracker import SetFormTracker
from backend.reps.counter import RepState
from starlette.testclient import TestClient
from backend.main import app  # safe: conftest patches person_detector first


# ---------------------------------------------------------------------------
# Test 1 — interrupt_session writes partial data
# ---------------------------------------------------------------------------

def test_interrupt_session_writes_interrupted_status():
    """
    Start session, cache partial state, call interrupt_session.
    DB row must have status='interrupted' and non-zero reps and calories.
    """
    db = SessionLocal()
    user = User(name="RecoveryTest1", weight_kg=75.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    mgr = SessionManager()
    session_id = mgr.start_session(user_id=user_id, weight_kg=75.0)

    # Simulate some reps and a calorie segment
    rep_state = RepState(rep_count=5, set_number=1, sets_closed=[], hold_seconds=0)
    cal = CalorieEngine(weight_kg=75.0)
    t0 = time.time()
    cal.start_segment("squat", t0)
    time.sleep(0.05)

    form = SetFormTracker()
    form.add_sample(85)
    form.add_sample(90)

    mgr.update_state_cache(rep_state, cal, form)

    # Interrupt the session
    result = mgr.interrupt_session(session_id)

    assert result.status == "interrupted", \
        f"Expected 'interrupted', got {result.status!r}"
    assert result.total_reps == 5, \
        f"Expected 5 reps, got {result.total_reps}"
    assert result.total_calories > 0, \
        f"Expected calories > 0, got {result.total_calories}"


def test_interrupt_session_persists_to_db():
    """
    After interrupt_session, re-read the row from DB to confirm persistence.
    """
    db = SessionLocal()
    user = User(name="RecoveryTest2", weight_kg=68.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    mgr = SessionManager()
    session_id = mgr.start_session(user_id=user_id, weight_kg=68.0)

    rep_state = RepState(rep_count=3, set_number=1, sets_closed=[], hold_seconds=0)
    cal = CalorieEngine(weight_kg=68.0)
    cal.start_segment("push_up", time.time())
    time.sleep(0.05)
    mgr.update_state_cache(rep_state, cal, None)
    mgr.interrupt_session(session_id)

    # Re-read from DB
    db = SessionLocal()
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    db.close()

    assert row is not None
    assert row.status == "interrupted"
    assert row.total_reps == 3
    assert row.total_calories > 0


# ---------------------------------------------------------------------------
# Test 2 — GET /api/v1/sessions returns interrupted sessions
# ---------------------------------------------------------------------------

def test_get_sessions_returns_interrupted_row():
    """
    Seed a row with status='interrupted'.
    GET /api/v1/sessions should return it in the list.
    """
    db = SessionLocal()
    user = User(name="RecoveryTest3", weight_kg=70.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    interrupted_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(SessionModel(
        id=interrupted_id,
        user_id=user_id,
        started_at=now,
        ended_at=now,
        status="interrupted",
        total_reps=7,
        total_calories=1.5,
        duration_seconds=30,
    ))
    db.commit()
    db.close()

    with TestClient(app) as client:
        resp = client.get("/api/v1/sessions", params={"limit": 50})

    assert resp.status_code == 200
    sessions = resp.json()
    ids = [s["session_id"] for s in sessions]
    assert interrupted_id in ids, \
        f"interrupted session {interrupted_id} not found in list"

    # Find the specific session and verify fields
    matched = next(s for s in sessions if s["session_id"] == interrupted_id)
    assert matched["status"] == "interrupted"
    assert matched["total_reps"] == 7


def test_interrupted_session_detail_accessible():
    """
    GET /api/v1/sessions/{id} for an interrupted session returns 200
    with correct status field.
    """
    db = SessionLocal()
    user = User(name="RecoveryTest4", weight_kg=70.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id

    sid = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    db.add(SessionModel(
        id=sid, user_id=user_id, started_at=now, ended_at=now,
        status="interrupted", total_reps=4, total_calories=0.8,
        duration_seconds=20,
    ))
    db.commit()
    db.close()

    with TestClient(app) as client:
        resp = client.get(f"/api/v1/sessions/{sid}")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "interrupted"
    assert data["total_reps"] == 4


# ---------------------------------------------------------------------------
# Test 3 — Incremental persistence (sync version, no real 35s wait)
# ---------------------------------------------------------------------------

def test_incremental_persistence_flush_updates_db():
    """
    Run one flush of the persistence logic synchronously and confirm DB updated.
    (The full 35s async test is in verify_9_3.py — this is the unit-level check.)
    """
    import asyncio
    from backend.session.persistence import _flush

    db = SessionLocal()
    user = User(name="RecoveryTest5", weight_kg=80.0)
    db.add(user)
    db.commit()
    db.refresh(user)
    user_id = user.id
    db.close()

    mgr = SessionManager()
    session_id = mgr.start_session(user_id=user_id, weight_kg=80.0)

    rep_state = RepState(rep_count=6, set_number=1, sets_closed=[], hold_seconds=0)
    cal = CalorieEngine(weight_kg=80.0)
    cal.start_segment("lunge", time.time())
    time.sleep(0.02)
    form = SetFormTracker()
    form.add_sample(92)

    # Run one flush synchronously
    asyncio.run(_flush(
        session_id,
        get_rep_state=lambda: rep_state,
        get_calorie_engine=lambda: cal,
        get_form_tracker=lambda: form,
    ))

    db = SessionLocal()
    row = db.query(SessionModel).filter(SessionModel.id == session_id).first()
    db.close()

    assert row.total_reps == 6
    assert row.total_calories > 0
    assert row.status == "active"

    mgr.end_session(session_id)
