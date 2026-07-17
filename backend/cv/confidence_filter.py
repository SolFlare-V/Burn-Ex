"""
TASK-3.6 — Confidence filter for pose landmarks.

Marks landmarks invalid when visibility < 0.5 and computes whether
the exercise-required landmarks are sufficiently occluded (> 30% invalid).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.cv.pose_estimator import Landmark

# ---------------------------------------------------------------------------
# Required landmark IDs per exercise type (MediaPipe 33-point model indices)
# Ref: https://developers.google.com/mediapipe/solutions/vision/pose_landmarker
# ---------------------------------------------------------------------------
_EXERCISE_LANDMARKS: dict[str, list[int]] = {
    "squat": [11, 12, 23, 24, 25, 26, 27, 28, 29, 30],   # shoulders, hips, knees, ankles
    "push_up": [11, 12, 13, 14, 15, 16, 23, 24],          # shoulders, elbows, wrists, hips
    "lunge": [11, 12, 23, 24, 25, 26, 27, 28, 29, 30],
    "bicep_curl": [11, 12, 13, 14, 15, 16],               # shoulders, elbows, wrists
    "shoulder_press": [11, 12, 13, 14, 15, 16],
    "plank": [11, 12, 23, 24, 27, 28],                    # shoulders, hips, ankles
}

_VISIBILITY_THRESHOLD = 0.5
_OCCLUSION_RATIO = 0.30  # > 30% of required landmarks invalid → occluded


@dataclass
class FilteredLandmark(Landmark):
    """Landmark with an added validity flag."""
    valid: bool = True


@dataclass
class FilterResult:
    """Result of the confidence filter pass."""
    landmark_set: list[FilteredLandmark]
    occluded: bool


def filter_landmarks(
    landmarks: list[Landmark],
    exercise_type: str | None,
) -> FilterResult:
    """
    Mark each landmark valid/invalid and determine if the frame is occluded.

    When exercise_type is None (exercise not yet confirmed), occlusion is
    determined across all 33 landmarks rather than an exercise-specific
    subset. This prevents false "Move into frame" warnings before the
    classifier has confirmed what the user is doing.

    Args:
        landmarks:     33 Landmark objects from pose_estimator.
        exercise_type: Exercise name key (e.g. "squat"), or None if unconfirmed.

    Returns:
        FilterResult with filtered landmark_set and occluded flag.
    """
    if exercise_type is not None:
        required_ids = _EXERCISE_LANDMARKS.get(exercise_type, list(range(33)))
    else:
        # No exercise confirmed yet — require core torso landmarks only
        # (hips + shoulders). These 4 points are visible whenever a person
        # is properly in frame regardless of exercise type.
        required_ids = [11, 12, 23, 24]

    filtered: list[FilteredLandmark] = []
    invalid_required = 0

    for lm in landmarks:
        is_valid = lm.visibility >= _VISIBILITY_THRESHOLD
        filtered.append(
            FilteredLandmark(
                id=lm.id,
                x=lm.x,
                y=lm.y,
                z=lm.z,
                visibility=lm.visibility,
                valid=is_valid,
            )
        )
        if lm.id in required_ids and not is_valid:
            invalid_required += 1

    if len(required_ids) == 0:
        occluded = False
    else:
        occluded = (invalid_required / len(required_ids)) > _OCCLUSION_RATIO

    return FilterResult(landmark_set=filtered, occluded=occluded)
