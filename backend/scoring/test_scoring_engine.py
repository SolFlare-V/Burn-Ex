"""
Tests for backend/scoring/engine.py (TASK-6.6).

Covers:
  1. Occluded frame → ScoringResult(cues=[], score=0, warning="Move into frame")
  2. confirmed_type="plank" → routes to plank scorer (non-zero score, plank cues)
  3. confirmed_type="squat" with violations → cues + reduced score from regular path
  4. confirmed_type=None → ScoringResult(cues=[], score=0, warning=None)
  5. Non-occluded, perfect squat angles → score==100, cues==[]
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import pytest

from backend.scoring.engine import ScoringResult, score_frame


# ---------------------------------------------------------------------------
# Minimal stand-in for ProcessedFrame (avoids importing the full CV pipeline)
# ---------------------------------------------------------------------------

@dataclass
class _FakeFrame:
    """Lightweight substitute for cv.pipeline.ProcessedFrame."""
    angle_map: dict[str, float] = field(default_factory=dict)
    occluded: bool = False
    landmarks: list[Any] = field(default_factory=list)
    warning: str = ""


# ---------------------------------------------------------------------------
# 1. Occluded frame
# ---------------------------------------------------------------------------

def test_occluded_frame_returns_move_into_frame_warning():
    """When occluded=True the engine must return the occlusion guard result."""
    frame = _FakeFrame(
        occluded=True,
        angle_map={"left_knee": 90.0, "right_knee": 90.0},  # angles present but irrelevant
    )
    result = score_frame(frame, confirmed_type="squat")

    assert result.cues == [], "Cues must be empty for an occluded frame"
    assert result.score == 0, "Score must be 0 for an occluded frame"
    assert result.warning == "Move into frame", (
        "Warning must be 'Move into frame' for an occluded frame"
    )


def test_occluded_frame_ignores_confirmed_type_plank():
    """Occlusion guard fires regardless of confirmed_type."""
    frame = _FakeFrame(occluded=True, angle_map={})
    result = score_frame(frame, confirmed_type="plank")

    assert result.cues == []
    assert result.score == 0
    assert result.warning == "Move into frame"


# ---------------------------------------------------------------------------
# 2. Plank routing
# ---------------------------------------------------------------------------

def test_plank_type_routes_to_plank_scorer_perfect_form():
    """Perfect plank angles → score==100, no cues, no warning."""
    # Angles within plank thresholds from form_thresholds.yaml
    # left_hip min=160 max=185, right_hip min=160 max=185,
    # left_shoulder min=40 max=80, trunk min=165 max=185
    frame = _FakeFrame(
        occluded=False,
        angle_map={
            "left_hip": 175.0,      # within [160, 185]
            "right_hip": 175.0,     # within [160, 185]
            "left_shoulder": 60.0,  # within [40, 80]
            "trunk": 175.0,         # within [165, 185]
        },
    )
    result = score_frame(frame, confirmed_type="plank")

    assert isinstance(result, ScoringResult)
    assert result.score == 100, "Perfect plank form should score 100"
    assert result.cues == [], "No cues expected for perfect plank form"
    assert result.warning is None


def test_plank_type_routes_to_plank_scorer_violation():
    """Plank with hip violation → cue returned + reduced score."""
    # Set hips WAY too high (above max 185) to trigger cue_high
    frame = _FakeFrame(
        occluded=False,
        angle_map={
            "left_hip": 200.0,   # > 185 → "Raise hips — don't let them sag" violation
            "right_hip": 200.0,
            "left_shoulder": 60.0,
            "trunk": 200.0,      # > 185 → trunk violation too
        },
    )
    result = score_frame(frame, confirmed_type="plank")

    assert isinstance(result, ScoringResult)
    assert result.score < 100, "Violations must reduce score below 100"
    assert len(result.cues) > 0, "Violations must produce at least one cue"
    assert result.warning is None


def test_plank_routing_not_confused_with_regular_path():
    """Engine returns a ScoringResult (not raises) for plank confirmed_type."""
    frame = _FakeFrame(
        occluded=False,
        angle_map={"left_hip": 170.0, "trunk": 170.0},
    )
    result = score_frame(frame, confirmed_type="plank")
    assert isinstance(result, ScoringResult)


# ---------------------------------------------------------------------------
# 3. Regular exercise — squat with violations
# ---------------------------------------------------------------------------

def test_squat_with_violations_returns_cues_and_reduced_score():
    """Squat angles violating thresholds → at most 2 cues, score < 100."""
    # left_knee below min=70 → violation (penalty 25)
    # left_hip below min=60 → violation (penalty 15)
    # trunk above max=90 → violation (penalty 20)
    frame = _FakeFrame(
        occluded=False,
        angle_map={
            "left_knee": 50.0,   # < 70 → cue_low
            "right_knee": 90.0,  # within range
            "left_hip": 40.0,    # < 60 → cue_low
            "right_hip": 90.0,
            "trunk": 100.0,      # > 90 → cue_high
        },
    )
    result = score_frame(frame, confirmed_type="squat")

    assert isinstance(result, ScoringResult)
    assert result.score < 100, "Violations must reduce score below 100"
    assert 1 <= len(result.cues) <= 2, "Engine must return 1–2 cues (top-2 prioritisation)"
    assert result.warning is None, "Non-occluded squat should have no warning"


def test_squat_violation_score_deduction():
    """Score deduction matches the configured penalty values."""
    # Violate only left_knee (penalty=25) → expected score = 100 - 25 = 75
    frame = _FakeFrame(
        occluded=False,
        angle_map={
            "left_knee": 50.0,   # < 70 → penalty 25
            "right_knee": 120.0,
            "left_hip": 90.0,
            "right_hip": 90.0,
            "trunk": 70.0,
        },
    )
    result = score_frame(frame, confirmed_type="squat")
    assert result.score == 75, f"Expected 75 but got {result.score}"


# ---------------------------------------------------------------------------
# 4. confirmed_type is None
# ---------------------------------------------------------------------------

def test_none_confirmed_type_returns_empty_result():
    """When no exercise is confirmed yet, all fields are at their zero state."""
    frame = _FakeFrame(occluded=False, angle_map={"left_knee": 90.0})
    result = score_frame(frame, confirmed_type=None)

    assert result.cues == []
    assert result.score == 0
    assert result.warning is None


# ---------------------------------------------------------------------------
# 5. Perfect squat angles → score 100, empty cues
# ---------------------------------------------------------------------------

def test_perfect_squat_angles_score_100_no_cues():
    """All squat angles within thresholds → score 100 and no cues."""
    # Thresholds from form_thresholds.yaml:
    # left_knee  [70, 175], right_knee  [70, 175]
    # left_hip   [60, 175], right_hip   [60, 175]
    # trunk      [40,  90]
    frame = _FakeFrame(
        occluded=False,
        angle_map={
            "left_knee": 120.0,
            "right_knee": 120.0,
            "left_hip": 100.0,
            "right_hip": 100.0,
            "trunk": 65.0,
        },
    )
    result = score_frame(frame, confirmed_type="squat")

    assert result.score == 100, f"Expected 100 but got {result.score}"
    assert result.cues == [], f"Expected no cues but got: {result.cues}"
    assert result.warning is None


# ---------------------------------------------------------------------------
# 6. ScoringResult dataclass structure
# ---------------------------------------------------------------------------

def test_scoring_result_default_values():
    """ScoringResult can be created with defaults."""
    r = ScoringResult()
    assert r.cues == []
    assert r.score == 0
    assert r.warning is None


def test_scoring_result_explicit_values():
    """ScoringResult stores provided values."""
    r = ScoringResult(cues=["Keep chest up"], score=75, warning=None)
    assert r.cues == ["Keep chest up"]
    assert r.score == 75
    assert r.warning is None


def test_scoring_result_warning_field():
    """ScoringResult with warning stores warning string."""
    r = ScoringResult(cues=[], score=0, warning="Move into frame")
    assert r.warning == "Move into frame"
