"""
Unit tests for backend/reps/set_tracker.py — TASK-7.4.

Tests:
1. count_rep() ×5 then close_set(80.0) → ClosedSet(set_number=1, reps=5, avg_form_score=80.0)
2. exercise_changed() with 3 reps → ClosedSet.reps == 3
3. exercise_changed() with 0 reps → returns None, no set added to closed_sets
4. After close_set(), current_set_number==2 and current_rep_count==0
5. closed_sets list grows with each close_set() call
6. Two sequential sets: first 5 reps, second 3 reps → closed_sets has both in order
"""

import pytest

from backend.reps.set_tracker import ClosedSet, SetTracker


# ---------------------------------------------------------------------------
# Test 1: count 5 reps, close_set(80.0) → ClosedSet(1, 5, 80.0)
# ---------------------------------------------------------------------------

def test_close_set_after_five_reps() -> None:
    tracker = SetTracker()
    for _ in range(5):
        tracker.count_rep()

    result = tracker.close_set(avg_form_score=80.0)

    assert isinstance(result, ClosedSet)
    assert result.set_number == 1
    assert result.reps == 5
    assert result.avg_form_score == 80.0


# ---------------------------------------------------------------------------
# Test 2: exercise_changed() with 3 reps → ClosedSet.reps == 3
# ---------------------------------------------------------------------------

def test_exercise_changed_with_reps() -> None:
    tracker = SetTracker()
    for _ in range(3):
        tracker.count_rep()

    result = tracker.exercise_changed()

    assert result is not None
    assert result.reps == 3


# ---------------------------------------------------------------------------
# Test 3: exercise_changed() with 0 reps → None, no closed set added
# ---------------------------------------------------------------------------

def test_exercise_changed_with_no_reps_returns_none() -> None:
    tracker = SetTracker()

    result = tracker.exercise_changed()

    assert result is None
    assert len(tracker.closed_sets) == 0


# ---------------------------------------------------------------------------
# Test 4: after close_set(), current_set_number==2 and current_rep_count==0
# ---------------------------------------------------------------------------

def test_close_set_advances_number_and_resets_reps() -> None:
    tracker = SetTracker()
    tracker.count_rep()
    tracker.count_rep()
    tracker.close_set(avg_form_score=90.0)

    assert tracker.current_set_number == 2
    assert tracker.current_rep_count == 0


# ---------------------------------------------------------------------------
# Test 5: closed_sets list grows with each close_set() call
# ---------------------------------------------------------------------------

def test_closed_sets_list_grows() -> None:
    tracker = SetTracker()

    assert len(tracker.closed_sets) == 0

    tracker.close_set()
    assert len(tracker.closed_sets) == 1

    tracker.close_set()
    assert len(tracker.closed_sets) == 2

    tracker.close_set()
    assert len(tracker.closed_sets) == 3


# ---------------------------------------------------------------------------
# Test 6: two sequential sets — first 5 reps, second 3 reps → both in order
# ---------------------------------------------------------------------------

def test_two_sequential_sets_recorded_in_order() -> None:
    tracker = SetTracker()

    # First set: 5 reps
    for _ in range(5):
        tracker.count_rep()
    tracker.close_set(avg_form_score=75.0)

    # Second set: 3 reps
    for _ in range(3):
        tracker.count_rep()
    tracker.close_set(avg_form_score=85.0)

    closed = tracker.closed_sets
    assert len(closed) == 2

    assert closed[0].set_number == 1
    assert closed[0].reps == 5
    assert closed[0].avg_form_score == 75.0

    assert closed[1].set_number == 2
    assert closed[1].reps == 3
    assert closed[1].avg_form_score == 85.0


# ---------------------------------------------------------------------------
# Additional edge cases
# ---------------------------------------------------------------------------

def test_close_set_with_zero_reps_is_allowed() -> None:
    """close_set() always closes even when reps == 0 (REQ-4.4 auto-close path)."""
    tracker = SetTracker()
    result = tracker.close_set(avg_form_score=0.0)

    assert result.reps == 0
    assert result.set_number == 1
    assert len(tracker.closed_sets) == 1


def test_closed_sets_returns_copy_not_internal_list() -> None:
    """Mutating the returned list must not affect internal state."""
    tracker = SetTracker()
    tracker.count_rep()
    tracker.close_set()

    snapshot = tracker.closed_sets
    snapshot.clear()  # mutate the returned copy

    # Internal state must be unchanged
    assert len(tracker.closed_sets) == 1


def test_initial_state() -> None:
    tracker = SetTracker()

    assert tracker.current_set_number == 1
    assert tracker.current_rep_count == 0
    assert tracker.closed_sets == []


def test_exercise_changed_does_not_leave_empty_set_open() -> None:
    """After exercise_changed() with reps, set_number advances and reps reset."""
    tracker = SetTracker()
    tracker.count_rep()
    tracker.exercise_changed()

    assert tracker.current_set_number == 2
    assert tracker.current_rep_count == 0


def test_exercise_changed_with_no_reps_does_not_advance_set_number() -> None:
    """When there are no reps, exercise_changed() must not advance the set number."""
    tracker = SetTracker()
    tracker.exercise_changed()

    assert tracker.current_set_number == 1
