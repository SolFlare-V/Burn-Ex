"""
Tests for backend/reps/pause_timer.py — TASK-7.3.

Verifies:
1. Same angle for 9 cumulative seconds → True on the tick that crosses 8 s.
2. Movement mid-pause resets the timer; True is never returned.
3. One-shot behaviour: after True is returned, further same-angle ticks return False.
4. reset() clears stationary_seconds and lets the timer fire again.
5. Jitter within 2° still counts as stationary (accumulates normally).
"""

import pytest

from backend.reps.pause_timer import PauseTimer


# ---------------------------------------------------------------------------
# Test 1: stationary for 9 s → True on the tick that crosses 8 s
# ---------------------------------------------------------------------------

def test_crosses_8s_threshold():
    """
    Sending tick(90.0, 1.0) nine times should return True on the 9th call
    (cumulative = 9 s, which is the first tick to cross the 8 s threshold).
    """
    timer = PauseTimer()
    results = [timer.tick(90.0, 1.0) for _ in range(9)]

    # Exactly one True in the sequence, and it occurs on tick 9
    assert results.count(True) == 1, "Expected exactly one True signal"
    assert results[8] is True, "True should be returned on the 9th tick (9 s total)"

    # Ticks 1-8 must all be False
    assert all(r is False for r in results[:8]), "First 8 ticks should return False"


def test_stationary_seconds_accumulates():
    """stationary_seconds should reflect cumulative elapsed time."""
    timer = PauseTimer()
    timer.tick(45.0, 2.0)
    timer.tick(45.0, 3.0)
    assert timer.stationary_seconds == pytest.approx(5.0)


# ---------------------------------------------------------------------------
# Test 2: movement mid-pause resets; timer never fires
# ---------------------------------------------------------------------------

def test_movement_resets_timer():
    """
    5 stationary ticks followed by a movement tick should reset the timer.
    Subsequent stationary ticks restart the count from 0 and True is never
    returned for the first partial sequence.
    """
    timer = PauseTimer()

    # 5 stationary seconds
    for _ in range(5):
        result = timer.tick(90.0, 1.0)
        assert result is False

    # Movement detected (angle changes by > 2°)
    result = timer.tick(93.0, 1.0)
    assert result is False, "Movement tick must return False"

    # stationary_seconds should be reset to 0 (or just the new tick's elapsed)
    # After reset, a fresh tick with the new angle starts the accumulator.
    # The movement tick itself resets, then the *next* tick starts fresh from
    # the new angle.  Verify accumulator was cleared.
    assert timer.stationary_seconds == pytest.approx(0.0), (
        "stationary_seconds should be 0 after movement (before new accumulation)"
    )

    # 3 more ticks — still well below 8 s, so still False
    for _ in range(3):
        result = timer.tick(93.0, 1.0)
        assert result is False


def test_movement_then_long_stationary_fires():
    """
    After movement resets the timer, a subsequent 9-second stationary
    sequence should still fire correctly.
    """
    timer = PauseTimer()

    # 5 s stationary
    for _ in range(5):
        timer.tick(90.0, 1.0)

    # Movement
    timer.tick(95.0, 0.1)

    # 9 more stationary ticks at the new angle
    results = [timer.tick(95.0, 1.0) for _ in range(9)]
    assert results.count(True) == 1
    assert results[8] is True


# ---------------------------------------------------------------------------
# Test 3: one-shot — after True, further ticks return False
# ---------------------------------------------------------------------------

def test_one_shot_after_true():
    """
    After the timer fires (returns True), all subsequent ticks with the same
    angle must return False until reset() is called.
    """
    timer = PauseTimer()

    # Drive to threshold
    for _ in range(9):
        timer.tick(90.0, 1.0)

    # All subsequent ticks at same angle must be False
    for _ in range(5):
        result = timer.tick(90.0, 1.0)
        assert result is False, "Post-fire ticks must return False (one-shot)"


# ---------------------------------------------------------------------------
# Test 4: reset() clears state so the timer can fire again
# ---------------------------------------------------------------------------

def test_reset_allows_refiring():
    """
    reset() should clear stationary_seconds, last_angle, and fired flag so
    that the timer can fire again in a new sequence.
    """
    timer = PauseTimer()

    # First fire
    for _ in range(9):
        timer.tick(90.0, 1.0)

    # Reset
    timer.reset()
    assert timer.stationary_seconds == pytest.approx(0.0)

    # Second fire
    results = [timer.tick(90.0, 1.0) for _ in range(9)]
    assert results.count(True) == 1
    assert results[8] is True


def test_reset_before_threshold_clears_accumulation():
    """reset() mid-accumulation should zero the counter."""
    timer = PauseTimer()

    timer.tick(70.0, 3.0)
    timer.tick(70.0, 3.0)
    assert timer.stationary_seconds == pytest.approx(6.0)

    timer.reset()
    assert timer.stationary_seconds == pytest.approx(0.0)

    # After reset, need a full 8 s again
    results = [timer.tick(70.0, 1.0) for _ in range(9)]
    assert results[8] is True


# ---------------------------------------------------------------------------
# Test 5: jitter within 2° counts as stationary
# ---------------------------------------------------------------------------

def test_jitter_within_threshold_counts_as_stationary():
    """
    Angle values that oscillate within MOVEMENT_THRESHOLD (2°) must still
    accumulate stationary time and fire normally.

    Sequence: 90.0 → 91.0 → 90.5 → 90.8 → 89.9 … all delta < 2°
    """
    timer = PauseTimer()
    angles = [90.0, 91.0, 90.5, 90.8, 89.9, 91.1, 90.3, 90.7, 90.1]
    # 9 ticks × 1 s each → 9 s cumulative, crosses 8 s on 9th tick

    results = [timer.tick(a, 1.0) for a in angles]
    assert results.count(True) == 1
    assert results[8] is True


def test_exactly_2_degrees_does_not_trigger_movement():
    """
    A delta of exactly MOVEMENT_THRESHOLD (2.0°) must NOT be treated as
    movement (threshold is strict >), so accumulation continues.
    """
    timer = PauseTimer()

    timer.tick(90.0, 1.0)
    # Delta == 2.0 exactly — should NOT reset
    timer.tick(92.0, 1.0)
    # Delta back within jitter
    timer.tick(91.0, 1.0)

    # Timer should still have 3 s accumulated
    assert timer.stationary_seconds == pytest.approx(3.0)


def test_just_above_2_degrees_triggers_movement():
    """A delta > 2.0° triggers a reset."""
    timer = PauseTimer()

    timer.tick(90.0, 4.0)
    assert timer.stationary_seconds == pytest.approx(4.0)

    timer.tick(92.01, 1.0)  # delta = 2.01° > MOVEMENT_THRESHOLD
    assert timer.stationary_seconds == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

def test_first_tick_always_false():
    """The very first tick must always return False (no prior angle to compare)."""
    timer = PauseTimer()
    assert timer.tick(45.0, 100.0) is False


def test_sub_threshold_never_fires():
    """
    If total elapsed time is always just under 8 s, the timer must not fire.
    """
    timer = PauseTimer()
    # 7 ticks of 1 s = 7 s total — below threshold
    results = [timer.tick(90.0, 1.0) for _ in range(7)]
    assert all(r is False for r in results)
    assert timer.stationary_seconds == pytest.approx(7.0)


def test_stationary_seconds_property_reflects_accumulation():
    """stationary_seconds property tracks cumulative time correctly."""
    timer = PauseTimer()
    timer.tick(30.0, 2.5)
    timer.tick(30.0, 1.5)
    assert timer.stationary_seconds == pytest.approx(4.0)
