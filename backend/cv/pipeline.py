"""
TASK-3.8 — Full CV pipeline: process_frame(jpeg_bytes, exercise_type) -> ProcessedFrame

Pipeline order (per design.md §2.1):
  decode -> person detect -> nearest-person select -> crop ->
  MediaPipe Pose -> confidence filter -> angle map
"""

from __future__ import annotations

from dataclasses import dataclass, field

import cv2
import numpy as np

from backend.cv.person_detector import detect_persons
from backend.cv.person_selector import select_nearest_person
from backend.cv.frame_utils import crop_with_padding
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
    exercise_type: str,
) -> ProcessedFrame:
    """
    Run the full CV pipeline on a single JPEG frame.

    Args:
        jpeg_bytes:    Raw JPEG bytes as received from the browser.
        exercise_type: Exercise name key (e.g. "squat", "push_up").

    Returns:
        ProcessedFrame with landmarks, angle_map, occluded flag, and
        an optional warning string.
    """
    # ---- Stage 1: Decode JPEG -----------------------------------------------
    arr = np.frombuffer(jpeg_bytes, dtype=np.uint8)
    frame = cv2.imdecode(arr, cv2.IMREAD_COLOR)  # BGR, uint8
    if frame is None:
        return ProcessedFrame(warning="Failed to decode JPEG frame")

    # ---- Stage 2: Person detection ------------------------------------------
    boxes = detect_persons(frame)

    # ---- Stage 3: Nearest-person selection ----------------------------------
    roi = select_nearest_person(boxes)
    if roi is None:
        return ProcessedFrame(occluded=True, warning="No person detected in frame")

    # ---- Stage 4: Crop with padding -----------------------------------------
    h, w = frame.shape[:2]
    cropped, bounds = crop_with_padding(frame, roi, padding=0.10)

    # ---- Stage 5: MediaPipe Pose --------------------------------------------
    raw_landmarks: list[Landmark] = estimate_pose(cropped)
    if not raw_landmarks:
        return ProcessedFrame(occluded=True, warning="Pose estimation failed")

    # ---- Map landmarks back to full-frame normalized coordinates ------------
    px1_px, py1_px, px2_px, py2_px = bounds
    crop_w = px2_px - px1_px
    crop_h = py2_px - py1_px

    full_landmarks: list[Landmark] = []
    for lm in raw_landmarks:
        # Avoid division by zero if crop width or height is degenerate
        orig_x = (px1_px + lm.x * crop_w) / w if w > 0 else lm.x
        orig_y = (py1_px + lm.y * crop_h) / h if h > 0 else lm.y
        full_landmarks.append(
            Landmark(
                id=lm.id,
                x=orig_x,
                y=orig_y,
                z=lm.z,
                visibility=lm.visibility,
            )
        )

    # ---- Stage 6: Confidence filter -----------------------------------------
    filter_result: FilterResult = filter_landmarks(full_landmarks, exercise_type)

    # ---- Stage 7: Angle map --------------------------------------------------
    angles = calculate_angle_map(filter_result.landmark_set, exercise_type)

    warning = "Move into frame" if filter_result.occluded else ""

    return ProcessedFrame(
        landmarks=filter_result.landmark_set,
        angle_map=angles,
        occluded=filter_result.occluded,
        warning=warning,
    )
