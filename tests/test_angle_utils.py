"""
TASK-16.1 — Unit tests for calculate_angle and calculate_angle_map.

Verify: pytest tests/test_angle_utils.py passes.
"""
import math
import pytest

from backend.cv.angle_utils import calculate_angle, calculate_angle_map


# ---------------------------------------------------------------------------
# Helpers: minimal Landmark-like object
# ---------------------------------------------------------------------------

class FakeLandmark:
    def __init__(self, id_, x, y, z=0.0, visibility=1.0):
        self.id = id_
        self.x = x
        self.y = y
        self.z = z
        self.visibility = visibility
        self.valid = True  # satisfies FilteredLandmark interface


# ---------------------------------------------------------------------------
# calculate_angle tests
# ---------------------------------------------------------------------------

def test_right_angle_returns_90():
    """Vector (0,1) and (1,0) at origin form a 90° angle."""
    a = (0.0, 1.0)
    vertex = (0.0, 0.0)
    b = (1.0, 0.0)
    angle = calculate_angle(a, vertex, b)
    assert abs(angle - 90.0) < 0.01, f"Expected 90.0, got {angle}"


def test_straight_line_returns_180():
    """Collinear points (1,0)-(0,0)-(−1,0) form a 180° angle."""
    a = (1.0, 0.0)
    vertex = (0.0, 0.0)
    b = (-1.0, 0.0)
    angle = calculate_angle(a, vertex, b)
    assert abs(angle - 180.0) < 0.01, f"Expected 180.0, got {angle}"


def test_45_degree_angle():
    """45° angle: vectors at 45° apart."""
    a = (1.0, 0.0)
    vertex = (0.0, 0.0)
    b = (1.0, 1.0)
    angle = calculate_angle(a, vertex, b)
    assert abs(angle - 45.0) < 0.1, f"Expected 45.0, got {angle}"


def test_zero_magnitude_returns_zero():
    """Degenerate case: zero-length vector returns 0.0 instead of crashing."""
    a = (0.0, 0.0)  # same as vertex
    vertex = (0.0, 0.0)
    b = (1.0, 0.0)
    angle = calculate_angle(a, vertex, b)
    assert angle == 0.0


def test_acute_angle():
    """Vectors pointing mostly the same direction give angle < 90."""
    a = (1.0, 0.1)
    vertex = (0.0, 0.0)
    b = (1.0, -0.1)
    angle = calculate_angle(a, vertex, b)
    assert angle < 90.0


# ---------------------------------------------------------------------------
# calculate_angle_map tests
# ---------------------------------------------------------------------------

def _make_squat_landmarks():
    """
    Build a minimal landmark set covering the squat triplets.
    MediaPipe IDs used by squat:
      23 left_hip, 24 right_hip
      25 left_knee, 26 right_knee
      27 left_ankle, 28 right_ankle
      11 left_shoulder, 12 right_shoulder
      31 left_foot_index, 32 right_foot_index
    Place them at approximate standing positions.
    """
    positions = {
        11: (0.40, 0.10),   # left_shoulder
        12: (0.60, 0.10),   # right_shoulder
        23: (0.42, 0.45),   # left_hip
        24: (0.58, 0.45),   # right_hip
        25: (0.42, 0.65),   # left_knee
        26: (0.58, 0.65),   # right_knee
        27: (0.42, 0.85),   # left_ankle
        28: (0.58, 0.85),   # right_ankle
        31: (0.42, 0.95),   # left_foot_index
        32: (0.58, 0.95),   # right_foot_index
    }
    return [FakeLandmark(id_, x, y) for id_, (x, y) in positions.items()]


def test_squat_angle_map_has_expected_keys():
    """Squat angle map must contain all 7 expected angle names."""
    landmarks = _make_squat_landmarks()
    result = calculate_angle_map(landmarks, "squat")

    expected_keys = {
        "left_knee", "right_knee",
        "left_hip", "right_hip",
        "trunk",
        "left_ankle", "right_ankle",
    }
    assert expected_keys.issubset(set(result.keys())), (
        f"Missing keys: {expected_keys - set(result.keys())}"
    )


def test_squat_angle_map_values_in_range():
    """All computed angles should be in [0, 180]."""
    landmarks = _make_squat_landmarks()
    result = calculate_angle_map(landmarks, "squat")
    for name, angle in result.items():
        assert 0.0 <= angle <= 180.0, f"{name}={angle} out of [0,180] range"


def test_unknown_exercise_returns_empty():
    """Unsupported exercise type returns empty dict without crashing."""
    result = calculate_angle_map([], "unknown_exercise")
    assert result == {}


def test_missing_landmarks_omitted():
    """Angles whose required landmarks are missing are omitted from result."""
    # Only provide landmarks 23, 24 — most squat angles need more
    partial = [FakeLandmark(23, 0.4, 0.5), FakeLandmark(24, 0.6, 0.5)]
    result = calculate_angle_map(partial, "squat")
    # trunk requires 23, 11, 12 — 11 and 12 absent, so trunk should be missing
    assert "trunk" not in result


def test_push_up_angle_map_has_elbow_keys():
    """Push-up angle map must include elbow angles."""
    positions = {
        11: (0.3, 0.3), 12: (0.7, 0.3),  # shoulders
        13: (0.2, 0.5), 14: (0.8, 0.5),  # elbows
        15: (0.1, 0.7), 16: (0.9, 0.7),  # wrists
        23: (0.3, 0.6), 24: (0.7, 0.6),  # hips
        25: (0.3, 0.8), 26: (0.7, 0.8),  # knees
    }
    landmarks = [FakeLandmark(id_, x, y) for id_, (x, y) in positions.items()]
    result = calculate_angle_map(landmarks, "push_up")
    assert "left_elbow" in result
    assert "right_elbow" in result
