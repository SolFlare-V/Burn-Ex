"""
Tests for TASK-6.5 — plank_scorer.py

Covers:
1. left_hip=190.0 (above max 185, penalty 30) → score == 70, cues non-empty
2. left_hip=190.0 → cues[0] contains "Drop hips" or "Raise hips" (cue_high from YAML)
3. All angles in-bounds → score == 100, cues == []
4. Return type is tuple[list, int]
"""

import pytest
from backend.scoring.plank_scorer import score_plank


# ---------------------------------------------------------------------------
# Test 1 & 2 — left_hip above max (190 > 185): penalty 30, cue produced
# ---------------------------------------------------------------------------

class TestPlankHipsTooHigh:
    """left_hip=190 violates max=185 (penalty=30)."""

    def setup_method(self):
        # Only left_hip violates; other angles within plank thresholds.
        self.angle_map = {
            "left_hip": 190.0,       # > max 185 → violation (penalty 30)
            "right_hip": 170.0,      # within [160, 185]
            "trunk": 175.0,          # within [165, 185]
            "left_shoulder": 60.0,   # within [40, 80]
        }
        self.cues, self.score = score_plank(self.angle_map)

    def test_score_is_70(self):
        """100 - 30 (left_hip penalty) == 70."""
        assert self.score == 70

    def test_cues_non_empty(self):
        """At least one cue returned when a threshold is violated."""
        assert len(self.cues) > 0

    def test_cue_text_mentions_hips(self):
        """
        The cue for left_hip high-violation should mention hips.

        YAML cue_high = "Raise hips — don't let them sag"
        (cue_low = "Drop hips slightly — they're too high" fires when < min)
        """
        first_cue = self.cues[0].lower()
        assert "hips" in first_cue or "hip" in first_cue, (
            f"Expected cue to mention hips, got: {self.cues[0]!r}"
        )

    def test_cue_matches_drop_or_raise(self):
        """
        Accept either 'Drop hips' (low violation cue) or 'Raise hips' (high
        violation cue) — both are plank hip cues from the YAML config.

        For left_hip=190 (> max 185) the cue_high fires:
        'Raise hips — don't let them sag'
        """
        first_cue = self.cues[0].lower()
        assert "drop hips" in first_cue or "raise hips" in first_cue, (
            f"Expected 'drop hips' or 'raise hips' in cue, got: {self.cues[0]!r}"
        )


# ---------------------------------------------------------------------------
# Test 3 — All angles in bounds → perfect score, no cues
# ---------------------------------------------------------------------------

class TestPlankPerfectForm:
    """All angles within plank thresholds → score=100, cues=[]."""

    def setup_method(self):
        self.angle_map = {
            "left_hip": 170.0,      # within [160, 185]
            "right_hip": 170.0,     # within [160, 185]
            "trunk": 175.0,         # within [165, 185]
            "left_shoulder": 60.0,  # within [40, 80]
        }
        self.cues, self.score = score_plank(self.angle_map)

    def test_score_is_100(self):
        """No violations → score == 100."""
        assert self.score == 100

    def test_no_cues(self):
        """No violations → empty cue list."""
        assert self.cues == []


# ---------------------------------------------------------------------------
# Test 4 — Return type is tuple[list, int]
# ---------------------------------------------------------------------------

class TestPlankReturnType:
    """score_plank must return (list, int)."""

    def test_return_is_tuple(self):
        cues, score = score_plank({"left_hip": 175.0})
        # Unpacking itself verifies the 2-element structure.
        assert isinstance(cues, list)
        assert isinstance(score, int)

    def test_empty_angle_map_returns_perfect_score(self):
        """No angles → no violations → 100."""
        cues, score = score_plank({})
        assert score == 100
        assert cues == []


# ---------------------------------------------------------------------------
# Additional edge-case: both hips violated → score floor test
# ---------------------------------------------------------------------------

class TestPlankMultipleViolations:
    """Two hip violations (30+30=60) → score == 40."""

    def test_both_hips_violated(self):
        angle_map = {
            "left_hip": 190.0,   # > 185, penalty 30
            "right_hip": 190.0,  # > 185, penalty 30
            "trunk": 175.0,
            "left_shoulder": 60.0,
        }
        cues, score = score_plank(angle_map)
        assert score == 40

    def test_score_floor_at_zero(self):
        """All four angles violated; total penalty > 100 → floored at 0."""
        angle_map = {
            "left_hip": 195.0,       # penalty 30
            "right_hip": 195.0,      # penalty 30
            "trunk": 190.0,          # penalty 25
            "left_shoulder": 10.0,   # < 40, penalty 15
        }
        cues, score = score_plank(angle_map)
        assert score == 0
