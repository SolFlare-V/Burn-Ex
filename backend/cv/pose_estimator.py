"""
TASK-3.5 — MediaPipe Pose inference wrapper.

Initialises mp.solutions.pose.Pose() ONCE at module load (not per-frame).
Accepts JPEG bytes or a numpy array, returns 33 Landmark objects.
"""

from __future__ import annotations

import io
from dataclasses import dataclass

import cv2
import mediapipe as mp
import numpy as np

# ---------------------------------------------------------------------------
# Module-level singleton — one Pose object for the lifetime of the process
# ---------------------------------------------------------------------------
_pose = mp.solutions.pose.Pose(
    static_image_mode=False,
    model_complexity=1,
    smooth_landmarks=True,
    min_detection_confidence=0.5,
    min_tracking_confidence=0.5,
)


@dataclass
class Landmark:
    """Single pose landmark with normalised coordinates."""
    id: int
    x: float
    y: float
    z: float
    visibility: float


def estimate_pose(frame: np.ndarray | bytes) -> list[Landmark]:
    """
    Run MediaPipe Pose on a single frame.

    Args:
        frame: Either a numpy array (H, W, 3) BGR/RGB uint8,
               or raw JPEG bytes.

    Returns:
        List of 33 Landmark objects. Returns an empty list if pose
        detection fails or no person is found.
    """
    # Decode JPEG bytes to numpy if needed
    if isinstance(frame, (bytes, bytearray)):
        arr = np.frombuffer(frame, dtype=np.uint8)
        img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
        if img is None:
            return []
    else:
        img = frame

    if img is None or img.size == 0:
        return []

    # MediaPipe Pose expects RGB
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    results = _pose.process(rgb)

    if not results.pose_landmarks:
        return []

    landmarks: list[Landmark] = []
    for idx, lm in enumerate(results.pose_landmarks.landmark):
        landmarks.append(
            Landmark(
                id=idx,
                x=float(lm.x),
                y=float(lm.y),
                z=float(lm.z),
                visibility=float(lm.visibility),
            )
        )

    return landmarks
