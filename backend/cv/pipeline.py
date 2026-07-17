"""
CV pipeline: process_frame(jpeg_bytes, exercise_type) -> ProcessedFrame

Pipeline order:
  decode -> MediaPipe Pose (full frame) -> confidence filter -> angle map

Person detection (EfficientDet) has been removed from the hot path.
MediaPipe Pose handles its own person detection internally and runs
significantly faster without the additional detection stage (~100ms saved).
The crop+remap logic is also removed — MediaPipe returns normalized coords
relative to the full frame when given the full frame directly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.cv.pose_estimator import estimate_pose, Landmark
from backend.cv.confidence_filter import filter_landmarks, FilteredLandmark, FilterResult
from backend.cv.angle_utils import calculate_angle_map


@dataclass
class ProcessedFrame:
    """Result of the full CV pipeline for one frame."""
    landmarks: list[FilteredLandmark] = field(default_factory=list)
    angle_map: dict[str, float] = field(default_factory=dict)
    occluded: bool = False
    warning: str = ""


def process_frame(
    jpeg_bytes: bytes,
    exercise_type: str | None,
) -> ProcessedFrame:
    """
    Run the CV pipeline on a single JPEG frame.

    Args:
        jpeg_bytes:    Raw JPEG bytes from the browser.
        exercise_type: Confirmed exercise key, or None when unconfirmed.

    Returns:
        ProcessedFrame with landmarks, angle_map, occluded flag, warning.
    """
    # ---- Decode JPEG --------------------------------------------------------
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if frame is None:
        return ProcessedFrame(warning="Failed to decode JPEG frame")

    # ---- MediaPipe Pose (full frame) ----------------------------------------
    raw_landmarks: list[Landmark] = estimate_pose(frame)
    if not raw_landmarks:
        return ProcessedFrame(occluded=True, warning="No person detected in frame")

    # ---- Confidence filter --------------------------------------------------
    # Pass None before exercise is confirmed so we only check torso landmarks,
    # preventing false "Move into frame" warnings during initial classification.
    filter_result: FilterResult = filter_landmarks(raw_landmarks, exercise_type)

    # ---- Angle map ----------------------------------------------------------
    angles = calculate_angle_map(filter_result.landmark_set, exercise_type)

    warning = "Move into frame" if filter_result.occluded else ""

    return ProcessedFrame(
        landmarks=filter_result.landmark_set,
        angle_map=angles,
        occluded=filter_result.occluded,
        warning=warning,
    )
