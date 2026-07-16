"""
Unit tests for TASK-6.3 — backend/scoring/form_score.py

Tests:
1. Perfect squat angles (all within thresholds)  → score == 100
2. left_knee = 50.0 (below squat min of 70, penalty 25) → score == 75
3. Multiple simultaneous violations summing > 100 penalties → score == 0 (floor)
4. Unknown exercise type → score == 100
5. Empty angle_map → score == 100 (no angles to violate)

Validates: REQ-3.4, REQ-3.5 (§2.3)
"""

from __future__ import annotations

import pytest
from backend.scoring.form_score import compute_frame_score


# ---------------------------------------------------------------------------
# Test 1: Perfect squat — all angles within thresholds → 100
# ---------------------------------------------------------------------------
def test_perfect_squat_returns_100():
    """All squat angles within valid bounds → no penalties → score 100."""
    angle_map = {
        "left_knee": 120.0,   # min 70, max 175 ✓
        "right_knee": 120.0,  # min 70, max 175 ✓
        "left_hip": 110.0,    # min 60, max 175 ✓
        "right_hip": 110.0,   # min 60, max 175 ✓
        "trunk": 65.0,        # min 40, max 90 ✓
    }
    assert compute_frame_score(angle_map, "squat") == 100


# ---------------------------------------------------------------------------
# Test 2: Knee-cave violation (left_knee below min) → score 75
# ---------------------------------------------------------------------------
def test_knee_cave_violation_returns_75():
    """left_knee = 50.0 is below squat min of 70 → penalty 25 → score 75."""
    # Provide only the violating angle; all other angles absent (skipped).
    angle_map = {
        "left_knee": 50.0,    # below min 70 → penalty 25
    }
    assert compute_frame_score(angle_map, "squat") == 75


# ---------------------------------------------------------------------------
# Test 3: Multiple violations summing > 100 → floor at 0
# ---------------------------------------------------------------------------
def test_multiple_violations_floored_at_zero():
    """
    Violate left_knee (25), right_knee (25), left_hip (15), right_hip (15),
    and trunk (20) simultaneously.
    Total penalty = 25+25+15+15+20 = 100 → score = max(0, 100-100) = 0.
    Add an extra violation to push past 100 (e.g. also violate push_up angles
    by using a separate exercise with high combined penalties, or re-use squat
    with all 5 violations = 100 → 0, then check floor holds).
    """
    # All 5 squat angles simultaneously violated: 25+25+15+15+20 = 100 → 0
    angle_map = {
        "left_knee": 50.0,    # below 70 → 25
        "right_knee": 50.0,   # below 70 → 25
        "left_hip": 30.0,     # below 60 → 15
        "right_hip": 30.0,    # below 60 → 15
        "trunk": 20.0,        # below 40 → 20
    }
    # total_penalty = 100 → score = max(0, 0) = 0
    assert compute_frame_score(angle_map, "squat") == 0


def test_multiple_violations_far_exceeding_100_floored_at_zero():
    """
    Use push_up with left_hip penalty 30 + trunk 20 + left_elbow 25 + right_elbow 25
    = 100, plus left_shoulder 10 → total 110 → score = max(0, 100-110) = 0.
    """
    angle_map = {
        "left_elbow": 50.0,   # below min 70 → 25
        "right_elbow": 50.0,  # below min 70 → 25
        "left_hip": 140.0,    # below min 160 → 30
        "trunk": 140.0,       # below min 155 → 20
        "left_shoulder": 10.0, # below min 30 → 10
    }
    # Total penalty = 25+25+30+20+10 = 110 → max(0, 100-110) = 0
    assert compute_frame_score(angle_map, "push_up") == 0


# ---------------------------------------------------------------------------
# Test 4: Unknown exercise type → score 100
# ---------------------------------------------------------------------------
def test_unknown_exercise_returns_100():
    """An exercise key not in the YAML returns 100 (no config → no penalty)."""
    angle_map = {"left_knee": 50.0, "right_knee": 50.0}
    assert compute_frame_score(angle_map, "unknown_exercise_xyz") == 100


# ---------------------------------------------------------------------------
# Test 5: Empty angle_map → score 100
# ---------------------------------------------------------------------------
def test_empty_angle_map_returns_100():
    """With no angles provided, no thresholds can be violated → score 100."""
    assert compute_frame_score({}, "squat") == 100
    assert compute_frame_score({}, "push_up") == 100
    assert compute_frame_score({}, "plank") == 100


# ---------------------------------------------------------------------------
# Extra: alias calculate_frame_score also works
# ---------------------------------------------------------------------------
def test_alias_calculate_frame_score():
    """Backwards-compat alias must behave identically."""
    from backend.scoring.form_score import calculate_frame_score
    assert calculate_frame_score({}, "squat") == 100
    assert calculate_frame_score({"left_knee": 50.0}, "squat") == 75
