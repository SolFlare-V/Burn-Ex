"""
Unit tests for TASK-7.2 — backend/reps/state_machine.py

Tests:
1. Full squat ROM: 170 → 85 → 170  →  rep_counted=True exactly once
2. Partial squat (never reaches depth 100):  170 → 130 → 170  →  rep_counted never True
3. Bicep curl full ROM: 40 → 155 → 40  →  rep_counted=True
4. rep_count increments on each completed rep
5. reset() clears rep_count and returns to NEUTRAL

Squat config (from rep_phases.yaml):
  eccentric_threshold: 160   (angle drops below → ECCENTRIC)
  depth_threshold:     100   (angle drops below → CONCENTRIC)
  return_threshold:    160   (angle rises above → NEUTRAL; counted if from CONCENTRIC)

Bicep curl config (from rep_phases.yaml):
  eccentric_threshold:  60   (angle rises above → ECCENTRIC — arm lowering)
  depth_threshold:     150   (angle rises above → CONCENTRIC — fully extended)
  return_threshold:     60   (angle drops below → NEUTRAL — curled back up; counted if from CONCENTRIC)

Validates: REQ-4.1, REQ-4.2, REQ-4.3 (§2.4)
"""

from __future__ import annotations

import pytest

from backend.reps.state_machine import Phase, RepStateMachine


# ---------------------------------------------------------------------------
# Helper: drive the state machine through a sequence of angles
# ---------------------------------------------------------------------------

def _feed(sm: RepStateMachine, angles: list[float]) -> list[bool]:
    """Feed a list of angles and collect the rep_counted booleans."""
    return [sm.update(a) for a in angles]


# ---------------------------------------------------------------------------
# Test 1: Full squat ROM — rep counted exactly once
# ---------------------------------------------------------------------------

def test_full_squat_counts_one_rep():
    """
    Feed a squat angle sequence that goes through full ROM:
      170 (neutral) → 85 (below depth threshold 100 → CONCENTRIC) → 170 (above return 160 → REP COUNTED)

    Expects rep_counted=True exactly once, on the final return.
    """
    sm = RepStateMachine("squat")
    results = _feed(sm, [
        170.0,   # NEUTRAL — above eccentric_threshold 160
        155.0,   # crosses eccentric_threshold (< 160) → ECCENTRIC
        130.0,   # still ECCENTRIC — not yet at depth (> 100)
        95.0,    # crosses depth_threshold (< 100) → CONCENTRIC
        85.0,    # deep; still CONCENTRIC
        130.0,   # rising; still CONCENTRIC (< return_threshold 160)
        165.0,   # crosses return_threshold (> 160) → NEUTRAL — REP COUNTED
    ])

    assert results.count(True) == 1, (
        f"Expected exactly 1 rep, got {results.count(True)}: {results}"
    )
    assert results[-1] is True, "Rep should be counted on the final transition to NEUTRAL"
    assert sm.rep_count == 1
    assert sm.phase is Phase.NEUTRAL


# ---------------------------------------------------------------------------
# Test 2: Partial squat — never reaches depth — no rep counted
# ---------------------------------------------------------------------------

def test_partial_squat_no_rep():
    """
    Feed a partial squat that enters ECCENTRIC but never reaches depth_threshold 100.
    The angle reverses at 130 and returns above return_threshold 160.
    No rep should be counted.
    """
    sm = RepStateMachine("squat")
    results = _feed(sm, [
        170.0,   # NEUTRAL
        155.0,   # crosses eccentric_threshold → ECCENTRIC
        130.0,   # ECCENTRIC — still above depth_threshold (130 > 100)
        165.0,   # returns above return_threshold (> 160) → NEUTRAL (partial — NOT counted)
    ])

    assert results.count(True) == 0, (
        f"Expected 0 reps for partial squat, got {results.count(True)}: {results}"
    )
    assert sm.rep_count == 0
    assert sm.phase is Phase.NEUTRAL


# ---------------------------------------------------------------------------
# Test 3: Full bicep curl ROM — rep counted
# ---------------------------------------------------------------------------

def test_full_bicep_curl_counts_one_rep():
    """
    Bicep curl uses increasing-direction logic (depth_threshold > eccentric_threshold).
    Sequence: 40 (curled/neutral) → 155 (fully extended → CONCENTRIC) → 40 (curled back → REP COUNTED)
    """
    sm = RepStateMachine("bicep_curl")
    results = _feed(sm, [
        40.0,    # NEUTRAL — below eccentric_threshold 60
        65.0,    # crosses eccentric_threshold (> 60) → ECCENTRIC
        110.0,   # ECCENTRIC — still below depth_threshold (< 150)
        155.0,   # crosses depth_threshold (> 150) → CONCENTRIC
        140.0,   # rising back; still CONCENTRIC (> return_threshold 60)
        55.0,    # drops below return_threshold (< 60) → NEUTRAL — REP COUNTED
    ])

    assert results.count(True) == 1, (
        f"Expected 1 bicep curl rep, got {results.count(True)}: {results}"
    )
    assert results[-1] is True, "Rep should be counted on the final drop below return_threshold"
    assert sm.rep_count == 1
    assert sm.phase is Phase.NEUTRAL


# ---------------------------------------------------------------------------
# Test 4: rep_count increments on each completed rep
# ---------------------------------------------------------------------------

def test_multiple_squats_increment_rep_count():
    """
    Perform 3 full squats sequentially; rep_count should reach 3.
    """
    sm = RepStateMachine("squat")

    # One full squat cycle: neutral → eccentric → concentric → neutral
    def one_squat():
        _feed(sm, [155.0, 95.0, 165.0])

    assert sm.rep_count == 0

    one_squat()
    assert sm.rep_count == 1

    one_squat()
    assert sm.rep_count == 2

    one_squat()
    assert sm.rep_count == 3


# ---------------------------------------------------------------------------
# Test 5: reset() clears rep_count and returns to NEUTRAL
# ---------------------------------------------------------------------------

def test_reset_clears_state():
    """
    After completing 2 reps, reset() should set rep_count=0 and phase=NEUTRAL.
    """
    sm = RepStateMachine("squat")

    # Complete 2 reps
    for _ in range(2):
        _feed(sm, [155.0, 95.0, 165.0])

    assert sm.rep_count == 2

    sm.reset()

    assert sm.rep_count == 0
    assert sm.phase is Phase.NEUTRAL


def test_reset_clears_mid_rep_phase():
    """
    Even if the machine is mid-rep (ECCENTRIC phase), reset() returns to NEUTRAL.
    """
    sm = RepStateMachine("squat")

    sm.update(155.0)  # → ECCENTRIC
    assert sm.phase is Phase.ECCENTRIC

    sm.reset()

    assert sm.phase is Phase.NEUTRAL
    assert sm.rep_count == 0


# ---------------------------------------------------------------------------
# Test 6: Phase boundary edge cases — boundary angles
# ---------------------------------------------------------------------------

def test_squat_at_exact_eccentric_threshold_not_entered():
    """
    An angle exactly equal to eccentric_threshold (160) should NOT trigger
    the ECCENTRIC transition (condition is strict < 160 for decreasing exercises).
    """
    sm = RepStateMachine("squat")
    sm.update(160.0)  # equal — not strictly less → stays NEUTRAL
    assert sm.phase is Phase.NEUTRAL


def test_squat_just_below_eccentric_threshold_enters_eccentric():
    """
    An angle just below eccentric_threshold (159.9) triggers ECCENTRIC.
    """
    sm = RepStateMachine("squat")
    sm.update(159.9)
    assert sm.phase is Phase.ECCENTRIC


def test_squat_partial_rep_mid_eccentric_then_new_full_rep():
    """
    After abandoning a partial rep (ECCENTRIC → NEUTRAL without depth),
    the machine should accept a fresh full squat normally.
    """
    sm = RepStateMachine("squat")

    # Partial rep
    _feed(sm, [155.0, 130.0, 165.0])
    assert sm.rep_count == 0
    assert sm.phase is Phase.NEUTRAL

    # Full rep
    _feed(sm, [155.0, 95.0, 165.0])
    assert sm.rep_count == 1
    assert sm.phase is Phase.NEUTRAL


# ---------------------------------------------------------------------------
# Test 7: lunge (same direction as squat) — quick sanity check
# ---------------------------------------------------------------------------

def test_lunge_full_rep():
    """Lunge uses same decreasing-direction logic as squat."""
    sm = RepStateMachine("lunge")
    # lunge: eccentric=160, depth=100, return=160
    results = _feed(sm, [
        155.0,   # < 160 → ECCENTRIC
        95.0,    # < 100 → CONCENTRIC
        165.0,   # > 160 → NEUTRAL + REP
    ])
    assert results[-1] is True
    assert sm.rep_count == 1


# ---------------------------------------------------------------------------
# Test 8: Partial bicep curl (never reaches depth) — no rep
# ---------------------------------------------------------------------------

def test_partial_bicep_curl_no_rep():
    """
    Bicep curl that enters ECCENTRIC (> 60) but does not reach depth (> 150),
    then returns to neutral (< 60).  No rep counted.
    """
    sm = RepStateMachine("bicep_curl")
    results = _feed(sm, [
        65.0,    # > 60 → ECCENTRIC
        120.0,   # ECCENTRIC — still below depth_threshold (< 150)
        50.0,    # drops below return_threshold (< 60) → partial — NOT counted
    ])
    assert results.count(True) == 0
    assert sm.rep_count == 0
    assert sm.phase is Phase.NEUTRAL
