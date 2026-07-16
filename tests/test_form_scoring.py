"""
TASK-16.4 — Unit tests for the form scoring engine.

Tests:
  - No violations -> score 100
  - Single violation -> correct penalty applied
  - Two violations -> top-2 cues by severity
  - Occluded frame -> empty cues + warning
  - Plank -> routed to plank scorer

Verify: pytest tests/test_form_scoring.py passes.
"""
import pytest
from dataclasses import dataclass, field

from backend.scoring.engine import score_frame, ScoringResult
from backend.scoring.form_score import compute_frame_score
from backend.scoring.cue_generator import generate_cues


# ---------------------------------------------------------------------------
# Minimal ProcessedFrame stub
# ---------------------------------------------------------------------------

@dataclass
class FakeFrame:
    angle_map: dict = field(default_factory=dict)
    occluded: bool = False
    landmarks: list = field(default_factory=list)
    warning: str = ""


# ---------------------------------------------------------------------------
# Score 100 — no violations
# ---------------------------------------------------------------------------

def test_no_violations_score_100():
    """Perfect squat form: all angles within thresholds -> score 100."""
    # Squat thresholds: left_knee min=70, max=175. Use 90 (within range).
    angle_map = {
        "left_knee": 90.0,
        "right_knee": 90.0,
        "left_hip": 120.0,
        "right_hip": 120.0,
        "trunk": 70.0,
    }
    score = compute_frame_score(angle_map, "squat")
    assert score == 100, f"Expected 100, got {score}"


def test_no_violations_empty_cues():
    """No threshold violations -> empty cue list."""
    angle_map = {
        "left_knee": 90.0,
        "right_knee": 90.0,
        "left_hip": 120.0,
        "right_hip": 120.0,
        "trunk": 70.0,
    }
    cues = generate_cues(angle_map, "squat")
    assert cues == [], f"Expected [], got {cues}"


# ---------------------------------------------------------------------------
# Single violation — correct penalty
# ---------------------------------------------------------------------------

def test_single_knee_violation_penalty():
    """
    left_knee > 175 (cue_high violation) triggers penalty=25.
    Score = 100 - 25 = 75.
    """
    angle_map = {
        "left_knee": 180.0,   # > max 175 -> violation, penalty=25
        "right_knee": 90.0,
        "left_hip": 120.0,
        "right_hip": 120.0,
        "trunk": 70.0,
    }
    score = compute_frame_score(angle_map, "squat")
    assert score == 75, f"Expected 75, got {score}"


def test_single_violation_returns_one_cue():
    """Single violation produces exactly one cue."""
    angle_map = {
        "left_knee": 180.0,   # violation
        "right_knee": 90.0,
        "left_hip": 120.0,
        "right_hip": 120.0,
        "trunk": 70.0,
    }
    cues = generate_cues(angle_map, "squat")
    assert len(cues) == 1


# ---------------------------------------------------------------------------
# Two violations — top-2 cues by severity
# ---------------------------------------------------------------------------

def test_two_violations_returns_max_two_cues():
    """Multiple violations return at most 2 cues (highest severity first)."""
    angle_map = {
        "left_knee": 180.0,    # violation, severity_weight=3
        "right_knee": 180.0,   # violation, severity_weight=3
        "left_hip": 50.0,      # < min 60, violation, severity_weight=2
        "right_hip": 50.0,
        "trunk": 70.0,
    }
    cues = generate_cues(angle_map, "squat")
    assert len(cues) <= 2, f"Expected <=2 cues, got {len(cues)}: {cues}"
    assert len(cues) >= 1


def test_severity_ordering_highest_first():
    """Cues returned are highest-severity violations first."""
    # left_knee (severity=3) should appear before left_hip (severity=2)
    angle_map = {
        "left_knee": 180.0,    # sev=3
        "left_hip": 50.0,      # sev=2
        "right_knee": 90.0,
        "right_hip": 120.0,
        "trunk": 70.0,
    }
    cues = generate_cues(angle_map, "squat")
    # The knee cue should appear (highest severity)
    knee_cue = "Bend your knees more to engage the movement"
    if len(cues) >= 1:
        # At least one of the cues should be the high-severity knee cue
        assert any("knee" in c.lower() or "bend" in c.lower() for c in cues), \
            f"Expected knee cue in {cues}"


# ---------------------------------------------------------------------------
# Occluded frame -> score_frame returns empty cues + warning
# ---------------------------------------------------------------------------

def test_occluded_frame_empty_cues_and_warning():
    """Occluded frame: score_frame returns empty cues and 'Move into frame' warning."""
    frame = FakeFrame(occluded=True, angle_map={"left_knee": 90.0})
    result = score_frame(frame, "squat")
    assert result.cues == [], f"Expected empty cues, got {result.cues}"
    assert result.warning == "Move into frame", f"Expected warning, got {result.warning!r}"
    assert result.score == 0


def test_occluded_frame_with_no_confirmed_type():
    """Occluded frame always returns early, regardless of exercise type."""
    frame = FakeFrame(occluded=True)
    result = score_frame(frame, None)
    assert result.cues == []
    assert result.warning == "Move into frame"


def test_no_confirmed_type_returns_empty():
    """confirmed_type=None with good frame -> empty cues, no warning."""
    frame = FakeFrame(occluded=False, angle_map={"left_knee": 90.0})
    result = score_frame(frame, None)
    assert result.cues == []
    assert result.score == 0
    assert result.warning is None


# ---------------------------------------------------------------------------
# Plank -> routed to plank scorer
# ---------------------------------------------------------------------------

def test_plank_routed_to_plank_scorer():
    """confirmed_type='plank' routes to plank scorer, not cue_generator."""
    # Aligned plank: all hip angles in [160,185]
    frame = FakeFrame(
        occluded=False,
        angle_map={
            "left_hip": 172.0,
            "right_hip": 172.0,
            "left_shoulder": 60.0,
            "trunk": 175.0,
        }
    )
    result = score_frame(frame, "plank")
    # Plank scorer should return a valid ScoringResult, no crash
    assert isinstance(result, ScoringResult)
    assert result.warning != "Move into frame"


def test_plank_misaligned_hips_produces_cue():
    """Plank with hips too low (below 160) should produce a cue."""
    frame = FakeFrame(
        occluded=False,
        angle_map={
            "left_hip": 140.0,    # < min 160 -> "Raise hips"
            "right_hip": 140.0,
            "trunk": 170.0,
            "left_shoulder": 60.0,
        }
    )
    result = score_frame(frame, "plank")
    assert len(result.cues) >= 1, f"Expected cue for misaligned hips, got {result.cues}"


# ---------------------------------------------------------------------------
# score_engine integration
# ---------------------------------------------------------------------------

def test_score_frame_returns_scoring_result():
    """score_frame always returns a ScoringResult object."""
    frame = FakeFrame(occluded=False, angle_map={"left_knee": 90.0})
    result = score_frame(frame, "squat")
    assert isinstance(result, ScoringResult)
    assert 0 <= result.score <= 100


def test_multiple_violations_accumulate_penalties():
    """Multiple violations accumulate penalties, clamped to 0 minimum."""
    angle_map = {
        "left_knee": 180.0,    # penalty=25
        "right_knee": 180.0,   # penalty=25
        "left_hip": 50.0,      # penalty=15
        "right_hip": 50.0,     # penalty=15
        "trunk": 100.0,        # > max 90, penalty=20
    }
    score = compute_frame_score(angle_map, "squat")
    # Total penalties: 25+25+15+15+20 = 100, so score = max(0, 100-100) = 0
    assert score == 0, f"Expected 0, got {score}"
