"""
TASK-3.7 — Joint angle calculation utilities.

calculate_angle(a, vertex, b) -> float   : dot-product formula on 2D (x,y)
calculate_angle_map(landmark_set, exercise_type) -> dict[str, float]
"""

from __future__ import annotations

import math
from typing import Union

from backend.cv.pose_estimator import Landmark
from backend.cv.confidence_filter import FilteredLandmark

# ---------------------------------------------------------------------------
# Per-exercise angle triplet config
# Each entry: angle_name -> (landmark_id_a, landmark_id_vertex, landmark_id_b)
# MediaPipe landmark IDs: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
# ---------------------------------------------------------------------------
_ANGLE_TRIPLETS: dict[str, dict[str, tuple[int, int, int]]] = {
    "squat": {
        "left_knee":     (23, 25, 27),   # left_hip, left_knee, left_ankle
        "right_knee":    (24, 26, 28),
        "left_hip":      (11, 23, 25),   # left_shoulder, left_hip, left_knee
        "right_hip":     (12, 24, 26),
        "trunk":         (23, 11, 12),   # left_hip, left_shoulder, right_shoulder (inclination proxy)
        "left_ankle":    (25, 27, 31),
        "right_ankle":   (26, 28, 32),
    },
    "push_up": {
        "left_elbow":    (11, 13, 15),   # left_shoulder, left_elbow, left_wrist
        "right_elbow":   (12, 14, 16),
        "left_shoulder": (13, 11, 23),   # left_elbow, left_shoulder, left_hip
        "right_shoulder":(14, 12, 24),
        "left_hip":      (11, 23, 25),
        "right_hip":     (12, 24, 26),
        "trunk":         (23, 11, 12),
    },
    "lunge": {
        "left_knee":     (23, 25, 27),
        "right_knee":    (24, 26, 28),
        "left_hip":      (11, 23, 25),
        "right_hip":     (12, 24, 26),
        "trunk":         (23, 11, 12),
    },
    "bicep_curl": {
        "left_elbow":    (11, 13, 15),
        "right_elbow":   (12, 14, 16),
        "left_shoulder": (13, 11, 23),
        "right_shoulder":(14, 12, 24),
        "left_hip":      (11, 23, 25),
        "right_hip":     (12, 24, 26),
    },
    "shoulder_press": {
        "left_elbow":    (11, 13, 15),
        "right_elbow":   (12, 14, 16),
        "left_shoulder": (13, 11, 23),
        "right_shoulder":(14, 12, 24),
        "trunk":         (23, 11, 12),
    },
    "plank": {
        "left_hip":      (11, 23, 25),
        "right_hip":     (12, 24, 26),
        "left_shoulder": (13, 11, 23),
        "right_shoulder":(14, 12, 24),
        "left_ankle":    (25, 27, 31),
        "right_ankle":   (26, 28, 32),
        "trunk":         (23, 11, 12),
    },
}

_LandmarkLike = Union[Landmark, FilteredLandmark]


def calculate_angle(
    a: tuple[float, float],
    vertex: tuple[float, float],
    b: tuple[float, float],
) -> float:
    """
    Calculate the angle (in degrees) at `vertex` formed by vectors vertex→a
    and vertex→b using the dot-product formula on 2D (x, y) coordinates.

    Returns a value in [0.0, 180.0].
    """
    ax, ay = a[0] - vertex[0], a[1] - vertex[1]
    bx, by = b[0] - vertex[0], b[1] - vertex[1]

    dot = ax * bx + ay * by
    mag_a = math.sqrt(ax * ax + ay * ay)
    mag_b = math.sqrt(bx * bx + by * by)

    if mag_a == 0.0 or mag_b == 0.0:
        return 0.0

    cos_angle = dot / (mag_a * mag_b)
    # Clamp to [-1, 1] to guard against floating-point errors
    cos_angle = max(-1.0, min(1.0, cos_angle))
    return math.degrees(math.acos(cos_angle))


def calculate_angle_map(
    landmark_set: list[_LandmarkLike],
    exercise_type: str,
) -> dict[str, float]:
    """
    Compute all relevant joint angles for the given exercise.

    Args:
        landmark_set:  List of 33 Landmark or FilteredLandmark objects.
        exercise_type: Exercise name key (e.g. "squat").

    Returns:
        Dict mapping angle name -> degrees. Angles whose required landmarks
        are missing or have id out of range are omitted from the result.
    """
    triplets = _ANGLE_TRIPLETS.get(exercise_type, {})
    if not triplets:
        return {}

    # Build id -> landmark lookup
    lm_map: dict[int, _LandmarkLike] = {lm.id: lm for lm in landmark_set}

    angle_map: dict[str, float] = {}
    for angle_name, (id_a, id_vertex, id_b) in triplets.items():
        lm_a = lm_map.get(id_a)
        lm_v = lm_map.get(id_vertex)
        lm_b = lm_map.get(id_b)

        if lm_a is None or lm_v is None or lm_b is None:
            continue

        # Skip if any of the three is invalid (FilteredLandmark)
        if hasattr(lm_a, "valid") and not lm_a.valid:
            continue
        if hasattr(lm_v, "valid") and not lm_v.valid:
            continue
        if hasattr(lm_b, "valid") and not lm_b.valid:
            continue

        angle = calculate_angle(
            (lm_a.x, lm_a.y),
            (lm_v.x, lm_v.y),
            (lm_b.x, lm_b.y),
        )
        angle_map[angle_name] = angle

    return angle_map
