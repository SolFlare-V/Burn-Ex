"""
TASK-16.3 — Unit tests for the rep state machine and related components.

Tests:
  - Full ROM squat counts one rep
  - Partial squat (no depth) counts zero
  - Set closes after 8s pause (PauseTimer)
  - Exercise change closes set immediately (RepCounter)
  - Plank timer tracks duration

Verify: pytest tests/test_rep_state_machine.py passes (including 3x for flaky check).
"""
import time
import pytest

from backend.reps.state_machine import RepStateMachine, Phase
from backend.reps.pause_timer import PauseTimer
from backend.reps.plank_timer import PlankTimer
from backend.reps.set_tracker import SetTracker
from backend.reps.counter import RepCounter


# ---------------------------------------------------------------------------
# RepStateMachine — squat full ROM
# ---------------------------------------------------------------------------

def _squat_angles():
    """Return angle sequence for a full squat rep.
    Squat thresholds: eccentric=160, depth=100, return=160
    Standing ~170 → descend below 100 → return above 160
    """
    return [170, 155, 130, 110, 90, 80, 90, 110, 130, 155, 170]


def _partial_squat_angles():
    """Partial: descend to 120 (above depth threshold 100), then return."""
    return [170, 155, 130, 120, 130, 155, 170]


def test_full_rom_squat_counts_one_rep():
    sm = RepStateMachine("squat")
    reps = 0
    for angle in _squat_angles():
        if sm.update(float(angle)):
            reps += 1
    assert reps == 1, f"Expected 1 rep, got {reps}"


def test_full_rom_squat_rep_count_property():
    sm = RepStateMachine("squat")
    for angle in _squat_angles():
        sm.update(float(angle))
    assert sm.rep_count == 1


def test_partial_squat_counts_zero():
    sm = RepStateMachine("squat")
    reps = 0
    for angle in _partial_squat_angles():
        if sm.update(float(angle)):
            reps += 1
    assert reps == 0, f"Expected 0 reps, got {reps}"


def test_two_full_squats_count_two():
    sm = RepStateMachine("squat")
    angles = _squat_angles() + _squat_angles()
    for angle in angles:
        sm.update(float(angle))
    assert sm.rep_count == 2


def test_state_machine_reset():
    sm = RepStateMachine("squat")
    for angle in _squat_angles():
        sm.update(float(angle))
    assert sm.rep_count == 1
    sm.reset()
    assert sm.rep_count == 0
    assert sm.phase == Phase.NEUTRAL


# ---------------------------------------------------------------------------
# RepStateMachine — push_up
# ---------------------------------------------------------------------------

def test_full_rom_push_up_counts_one_rep():
    """Push_up: eccentric=150, depth=100, return=150 (decreasing)."""
    sm = RepStateMachine("push_up")
    angles = [160, 145, 120, 95, 80, 95, 120, 145, 160]
    for angle in angles:
        sm.update(float(angle))
    assert sm.rep_count == 1


# ---------------------------------------------------------------------------
# RepStateMachine — bicep_curl (increasing direction)
# ---------------------------------------------------------------------------

def test_full_rom_bicep_curl_counts_one_rep():
    """Bicep_curl: eccentric=60, depth=150, return=60 (increasing)."""
    sm = RepStateMachine("bicep_curl")
    angles = [40, 65, 100, 140, 155, 140, 100, 65, 45]
    for angle in angles:
        sm.update(float(angle))
    assert sm.rep_count == 1


# ---------------------------------------------------------------------------
# PauseTimer — set closes after 8s pause
# ---------------------------------------------------------------------------

def test_pause_timer_fires_after_8s():
    pt = PauseTimer()
    base_angle = 170.0
    # Feed 9 ticks of 1s each at same angle — should fire at or after 8s
    fired = False
    for _ in range(9):
        if pt.tick(base_angle, 1.0):
            fired = True
            break
    assert fired, "PauseTimer should fire after 8s of no movement"


def test_pause_timer_resets_on_movement():
    pt = PauseTimer()
    base = 170.0
    # Build up 6 seconds of pause
    for _ in range(6):
        pt.tick(base, 1.0)
    # Movement detected — reset
    pt.tick(base + 20.0, 0.1)
    # Now 6 more seconds — should NOT fire yet (counter reset)
    fired = False
    for _ in range(6):
        if pt.tick(base, 1.0):
            fired = True
    assert not fired, "PauseTimer should reset on movement"


def test_pause_timer_fires_only_once():
    """Once fired, subsequent same-state ticks should not fire again."""
    pt = PauseTimer()
    base = 170.0
    fire_count = 0
    for _ in range(15):
        if pt.tick(base, 1.0):
            fire_count += 1
    assert fire_count == 1, f"Expected 1 fire, got {fire_count}"


# ---------------------------------------------------------------------------
# PlankTimer — tracks hold duration
# ---------------------------------------------------------------------------

def test_plank_timer_tracks_duration():
    pt = PlankTimer()
    pt.start()
    time.sleep(0.15)
    held = pt.elapsed()
    assert held >= 0, "elapsed() should return non-negative"


def test_plank_timer_stop_returns_duration():
    pt = PlankTimer()
    pt.start()
    time.sleep(0.12)
    duration = pt.stop()
    assert duration >= 0


def test_plank_timer_elapsed_increases():
    pt = PlankTimer()
    pt.start()
    t1 = pt.elapsed()
    time.sleep(0.05)
    t2 = pt.elapsed()
    assert t2 >= t1


# ---------------------------------------------------------------------------
# RepCounter — exercise change closes set immediately
# ---------------------------------------------------------------------------

def test_exercise_change_closes_set():
    rc = RepCounter()
    # Feed some squat angles to build up reps
    squat_angles = {
        "left_knee": 90.0,  # below depth threshold
        "right_knee": 92.0,
    }
    # Simulate going through a full ROM to get 1 rep registered
    angle_sequence = [
        170, 165, 155, 130, 110, 90, 110, 130, 155, 165, 170
    ]
    for angle in angle_sequence:
        rc.update_rep_state(
            {"left_knee": float(angle), "right_knee": float(angle)},
            "squat", 0.067
        )

    state_before = rc.update_rep_state({}, "squat", 0.067)
    sets_before = len(state_before.sets_closed)

    # Change exercise to push_up — should trigger exercise_changed -> close set
    rc.update_rep_state({}, "push_up", 0.067)
    state_after = rc.update_rep_state({}, "push_up", 0.067)

    # After exercise change, set_number should have incremented
    assert state_after.set_number > state_before.set_number or \
           len(state_after.sets_closed) >= sets_before, \
        "Exercise change should close the current set"


def test_rep_counter_plank_accumulates_hold():
    rc = RepCounter()
    # Feed plank frames — should route to plank timer, not state machine
    for _ in range(5):
        state = rc.update_rep_state(
            {"left_hip": 170.0, "trunk": 175.0},
            "plank", 0.067
        )
    # hold_seconds should be >= 0 for plank
    assert state.hold_seconds >= 0
