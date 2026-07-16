"""
Tests for backend/reps/counter.py  (TASK-7.6)

Design ref: §2.4
REQs: REQ-4.1–REQ-4.7

Five targeted tests covering:
1. Full squat ROM  → rep_count == 1
2. 9 stationary frames (1 s each) in NEUTRAL → sets_closed has 1 entry
3. Exercise change squat → push_up → set_number increments after change with reps
4. Plank frames → hold_seconds > 0, rep_count == 0
5. confirmed_type=None → rep_count == 0, hold_seconds == 0
"""

import time
import pytest

from backend.reps.counter import RepCounter, RepState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_angle_map(exercise: str, angle: float) -> dict[str, float]:
    """Return an angle_map with the primary angle key for the given exercise."""
    # Primary angles from rep_phases.yaml
    _primary = {
        "squat": "left_knee",
        "push_up": "left_elbow",
        "lunge": "left_knee",
        "bicep_curl": "left_elbow",
        "shoulder_press": "left_elbow",
    }
    key = _primary.get(exercise, "left_knee")
    return {key: angle}


# ---------------------------------------------------------------------------
# Test 1 — Full squat ROM → rep_count == 1
#
# Squat thresholds (rep_phases.yaml):
#   eccentric_threshold = 160  (NEUTRAL → ECCENTRIC when angle < 160)
#   depth_threshold     = 100  (ECCENTRIC → CONCENTRIC when angle < 100)
#   return_threshold    = 160  (CONCENTRIC → NEUTRAL when angle > 160  → REP COUNTED)
#
# The state machine processes ONE phase transition per update() call, so
# the rep requires 4 frames:
#   170 (neutral) → 140 (enter eccentric) → 85 (reach depth → concentric)
#   → 170 (return to neutral → REP COUNTED)
# ---------------------------------------------------------------------------

def test_squat_full_rom_counts_one_rep():
    """Four frames covering full squat ROM should yield rep_count == 1."""
    counter = RepCounter()

    # 170 = standing neutral, 140 = eccentric entry, 85 = full depth, 170 = return
    angles = [170.0, 140.0, 85.0, 170.0]
    state = RepState()
    for angle in angles:
        state = counter.update_rep_state(
            angle_map=_make_angle_map("squat", angle),
            confirmed_type="squat",
            elapsed_seconds=0.033,  # ~30 FPS
        )

    assert state.rep_count == 1, (
        f"Expected rep_count=1 after full squat ROM, got {state.rep_count}"
    )


# ---------------------------------------------------------------------------
# Test 2 — 9 stationary frames at same angle (1 s each) in squat NEUTRAL
#           → sets_closed has 1 entry after the 9th frame
#
# PauseTimer fires when stationary_seconds > PAUSE_THRESHOLD (8.0 s).
# 9 frames × 1 s = 9 s > 8 s → should auto-close the set.
#
# However, SetTracker.exercise_changed / close_set only records a set if
# there are reps in it.  PauseTimer.tick always calls close_set(0.0) on
# the counter side, so even a zero-rep set gets closed.
# ---------------------------------------------------------------------------

def test_stationary_frames_auto_close_set():
    """9 stationary frames of 1 s each should auto-close the set."""
    counter = RepCounter()

    # Push one rep first so the set is non-empty (PauseTimer fires regardless,
    # but REQ-4.4 says "after completing at least one rep").  We satisfy this
    # by doing a full ROM first, then staying stationary.
    for angle in [170.0, 140.0, 85.0, 170.0]:
        counter.update_rep_state(
            angle_map=_make_angle_map("squat", angle),
            confirmed_type="squat",
            elapsed_seconds=0.033,
        )

    # Now stay stationary at 170° for 9 seconds (9 × 1.0 s frames).
    state = RepState()
    for _ in range(9):
        state = counter.update_rep_state(
            angle_map=_make_angle_map("squat", 170.0),
            confirmed_type="squat",
            elapsed_seconds=1.0,
        )

    assert len(state.sets_closed) == 1, (
        f"Expected 1 closed set after 9 stationary seconds, "
        f"got {len(state.sets_closed)}"
    )


# ---------------------------------------------------------------------------
# Test 3 — Exercise change squat → push_up → set_number increments after
#          change with reps
# ---------------------------------------------------------------------------

def test_exercise_change_increments_set_number():
    """Changing exercise from squat to push_up after reps → set_number > 1."""
    counter = RepCounter()

    # Do a full squat rep first.
    for angle in [170.0, 140.0, 85.0, 170.0]:
        counter.update_rep_state(
            angle_map=_make_angle_map("squat", angle),
            confirmed_type="squat",
            elapsed_seconds=0.033,
        )

    # Switch to push_up — triggers SetTracker.exercise_changed() → closes set.
    state = counter.update_rep_state(
        angle_map=_make_angle_map("push_up", 160.0),
        confirmed_type="push_up",
        elapsed_seconds=0.033,
    )

    assert state.set_number > 1, (
        f"Expected set_number > 1 after exercise change with reps, "
        f"got {state.set_number}"
    )
    assert len(state.sets_closed) == 1, (
        f"Expected 1 closed set (the squat set), got {len(state.sets_closed)}"
    )


# ---------------------------------------------------------------------------
# Test 4 — Plank frames → hold_seconds > 0 after elapsed_seconds accumulate,
#          rep_count == 0
#
# PlankTimer uses time.monotonic() internally.  We send several frames with
# confirmed_type="plank" and wait briefly so the real clock advances.
# ---------------------------------------------------------------------------

def test_plank_tracking_hold_seconds():
    """Plank frames should accumulate hold_seconds > 0 and keep rep_count == 0."""
    counter = RepCounter()

    # Start plank — this triggers plank_timer.start().
    counter.update_rep_state(
        angle_map={},
        confirmed_type="plank",
        elapsed_seconds=0.1,
    )

    # Wait briefly so PlankTimer can accumulate real monotonic time.
    time.sleep(1.1)

    state = counter.update_rep_state(
        angle_map={},
        confirmed_type="plank",
        elapsed_seconds=1.1,
    )

    assert state.rep_count == 0, (
        f"Expected rep_count=0 for plank, got {state.rep_count}"
    )
    assert state.hold_seconds > 0, (
        f"Expected hold_seconds > 0 after plank frames, got {state.hold_seconds}"
    )


# ---------------------------------------------------------------------------
# Test 5 — confirmed_type=None → rep_count == 0, hold_seconds == 0
# ---------------------------------------------------------------------------

def test_none_confirmed_type_returns_initial_state():
    """No confirmed exercise should return the initial zero state."""
    counter = RepCounter()

    state = counter.update_rep_state(
        angle_map={"left_knee": 90.0},
        confirmed_type=None,
        elapsed_seconds=0.033,
    )

    assert state.rep_count == 0, (
        f"Expected rep_count=0 with None confirmed_type, got {state.rep_count}"
    )
    assert state.hold_seconds == 0, (
        f"Expected hold_seconds=0 with None confirmed_type, got {state.hold_seconds}"
    )
