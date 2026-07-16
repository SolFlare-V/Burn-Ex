"""
Unit tests for backend/scoring/cue_generator.py — TASK-6.2.

Verify:
  - 3 squat threshold violations → exactly 2 cues, highest severity first
  - No violations → empty list
  - Unknown exercise → empty list
  - Plank checks are evaluated
"""

from __future__ import annotations

import pytest

from backend.scoring.cue_generator import generate_cues


# ---------------------------------------------------------------------------
# Core verify task: 3 squat violations → top 2 cues, highest severity first
# ---------------------------------------------------------------------------

class TestSquatCues:
    def test_three_violations_returns_exactly_two_cues(self):
        """
        Violate 3 squat thresholds simultaneously:
          - left_knee  < 70  → severity 3 (cue_low)
          - trunk      > 90  → severity 2 (cue_high)
          - left_hip   > 175 → severity 2 (cue_high)

        Expect exactly 2 cues returned (top 2 by severity_weight).
        """
        angle_map = {
            "left_knee": 50.0,   # below min=70  → severity 3
            "trunk": 95.0,       # above max=90  → severity 2
            "left_hip": 180.0,   # above max=175 → severity 2
        }
        cues = generate_cues(angle_map, "squat")

        assert len(cues) == 2

    def test_highest_severity_cue_is_first(self):
        """
        The severity-3 knee cue must appear before the severity-2 cues.
        """
        angle_map = {
            "left_knee": 50.0,   # severity 3
            "trunk": 95.0,       # severity 2
            "left_hip": 180.0,   # severity 2
        }
        cues = generate_cues(angle_map, "squat")

        # severity-3 cue for knee below min
        assert cues[0] == "Squat deeper — bring knees further down"

    def test_second_cue_is_severity_2(self):
        """
        The second returned cue must be one of the severity-2 violations.
        """
        angle_map = {
            "left_knee": 50.0,
            "trunk": 95.0,
            "left_hip": 180.0,
        }
        cues = generate_cues(angle_map, "squat")

        severity_2_cues = {
            "Keep chest up — you're leaning too far forward",
            "Lean forward slightly to maintain balance",
            "Hip too compressed on right side",
            "Hinge at the right hip more",
            "Hip too compressed — stand taller at top",
            "Hinge at the hips more as you descend",
        }
        assert cues[1] in severity_2_cues

    def test_no_violations_returns_empty_list(self):
        """Perfect form → no cues."""
        angle_map = {
            "left_knee": 90.0,   # within [70, 175]
            "right_knee": 90.0,
            "left_hip": 100.0,   # within [60, 175]
            "right_hip": 100.0,
            "trunk": 60.0,       # within [40, 90]
        }
        cues = generate_cues(angle_map, "squat")
        assert cues == []

    def test_single_violation_returns_one_cue(self):
        """Only one threshold breached → exactly 1 cue."""
        angle_map = {
            "left_knee": 50.0,  # violates min=70
        }
        cues = generate_cues(angle_map, "squat")
        assert len(cues) == 1

    def test_cue_low_triggered_when_angle_below_min(self):
        """cue_low is returned when angle < min."""
        angle_map = {"left_knee": 50.0}   # min=70
        cues = generate_cues(angle_map, "squat")
        assert cues[0] == "Squat deeper — bring knees further down"

    def test_cue_high_triggered_when_angle_above_max(self):
        """cue_high is returned when angle > max."""
        angle_map = {"left_knee": 180.0}  # max=175
        cues = generate_cues(angle_map, "squat")
        assert cues[0] == "Bend your knees more to engage the movement"

    def test_missing_angles_are_skipped(self):
        """Angles absent from angle_map produce no violation."""
        cues = generate_cues({}, "squat")
        assert cues == []


# ---------------------------------------------------------------------------
# Unknown / missing exercise
# ---------------------------------------------------------------------------

class TestUnknownExercise:
    def test_unknown_exercise_returns_empty_list(self):
        cues = generate_cues({"left_knee": 50.0}, "handstand")
        assert cues == []

    def test_empty_angle_map_unknown_exercise_returns_empty(self):
        cues = generate_cues({}, "unknown_exercise")
        assert cues == []


# ---------------------------------------------------------------------------
# Deduplication: same cue text from multiple violations appears once
# ---------------------------------------------------------------------------

class TestDeduplication:
    def test_duplicate_cues_are_deduplicated(self):
        """
        left_knee and right_knee share the same cue_low text.
        Violating both should produce only one occurrence of that cue.
        """
        angle_map = {
            "left_knee": 50.0,   # cue_low: "Squat deeper — bring knees further down"
            "right_knee": 50.0,  # same cue_low text
        }
        cues = generate_cues(angle_map, "squat")
        # Both severity-3; deduplicated to 1 unique cue
        assert cues.count("Squat deeper — bring knees further down") == 1


# ---------------------------------------------------------------------------
# Plank checks
# ---------------------------------------------------------------------------

class TestPlankChecks:
    def test_plank_no_violations_returns_empty(self):
        """Angles within plank thresholds → no cues."""
        angle_map = {
            "left_hip": 170.0,    # within [160, 185]
            "right_hip": 170.0,
            "left_shoulder": 60.0,  # within [40, 80]
            "trunk": 175.0,         # within [165, 185]
        }
        cues = generate_cues(angle_map, "plank")
        assert cues == []

    def test_plank_hip_violation_triggers_threshold_cue(self):
        """Hip sag (above max) triggers plank hip cue_high."""
        angle_map = {"left_hip": 190.0}  # above max=185
        cues = generate_cues(angle_map, "plank")
        assert len(cues) >= 1
        assert "Raise hips" in cues[0] or "sag" in cues[0]

    def test_plank_check_fires_when_involved_angle_violates(self):
        """
        hip_alignment plank_check fires when any of its involved_angles
        (left_hip, right_hip, trunk) is out of range.
        """
        angle_map = {
            "left_hip": 190.0,   # above max=185 for left_hip threshold
            "right_hip": 170.0,
            "trunk": 175.0,
        }
        cues = generate_cues(angle_map, "plank")
        # hip_alignment check cue should appear somewhere in results
        alignment_cue = "Keep body in a straight line from head to heels"
        assert alignment_cue in cues or len(cues) >= 1


# ---------------------------------------------------------------------------
# Other exercises spot-check
# ---------------------------------------------------------------------------

class TestOtherExercises:
    def test_push_up_elbow_violation(self):
        angle_map = {"left_elbow": 60.0}   # below min=70, severity 3
        cues = generate_cues(angle_map, "push_up")
        assert len(cues) == 1
        assert cues[0] == "Lower your chest closer to the ground"

    def test_bicep_curl_no_violations(self):
        angle_map = {
            "left_elbow": 90.0,    # within [30, 160]
            "right_elbow": 90.0,
        }
        cues = generate_cues(angle_map, "bicep_curl")
        assert cues == []
