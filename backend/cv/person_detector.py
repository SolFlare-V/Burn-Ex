"""
TASK-3.2 — Person detection using MediaPipe Tasks ObjectDetector.

Loads efficientdet_lite0.tflite locally (no runtime network calls).
Returns normalised bounding boxes [(x1, y1, x2, y2)] for all detected persons.
"""

import os
import numpy as np
import mediapipe as mp
from mediapipe.tasks import python as mp_python
from mediapipe.tasks.python import vision as mp_vision

# Resolve model path relative to project root (two levels up from this file)
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "efficientdet_lite0.tflite")


def _build_detector() -> mp_vision.ObjectDetector:
    """Initialise the ObjectDetector once at module load."""
    if not os.path.exists(_MODEL_PATH):
        raise FileNotFoundError(
            f"efficientdet_lite0.tflite not found at {_MODEL_PATH}. "
            "Run the setup download step first."
        )
    # Use POSIX-style path (forward slashes) to avoid MediaPipe's Windows
    # path-joining bug where it prepends the site-packages directory to
    # absolute backslash paths. This is robust regardless of cwd.
    model_path_posix = _MODEL_PATH.replace("\\", "/")
    base_options = mp_python.BaseOptions(model_asset_path=model_path_posix)
    options = mp_vision.ObjectDetectorOptions(
        base_options=base_options,
        score_threshold=0.3,
        category_allowlist=["person"],
    )
    return mp_vision.ObjectDetector.create_from_options(options)


# Module-level singleton — initialised once, reused per call
_detector: mp_vision.ObjectDetector = _build_detector()


def detect_persons(frame: np.ndarray) -> list[tuple[float, float, float, float]]:
    """
    Detect all persons in a decoded frame.

    Args:
        frame: BGR or RGB numpy array (H, W, 3), uint8.

    Returns:
        List of normalised bounding boxes [(x1, y1, x2, y2)] where all
        values are in [0.0, 1.0], one entry per detected person.
        Returns an empty list when no persons are detected.
    """
    if frame is None or frame.size == 0:
        return []

    h, w = frame.shape[:2]

    # MediaPipe Tasks expects RGB
    if frame.shape[2] == 3:
        rgb = frame[:, :, ::-1].copy() if _is_bgr(frame) else frame.copy()
    else:
        rgb = frame.copy()

    mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
    result = _detector.detect(mp_image)

    boxes: list[tuple[float, float, float, float]] = []
    for detection in result.detections:
        # Filter to "person" category (allowlist handles this, but double-check)
        categories = detection.categories
        if not any(c.category_name == "person" for c in categories):
            continue

        bbox = detection.bounding_box
        x1 = bbox.origin_x / w
        y1 = bbox.origin_y / h
        x2 = (bbox.origin_x + bbox.width) / w
        y2 = (bbox.origin_y + bbox.height) / h

        # Clamp to [0, 1]
        x1, y1, x2, y2 = (
            max(0.0, min(1.0, x1)),
            max(0.0, min(1.0, y1)),
            max(0.0, min(1.0, x2)),
            max(0.0, min(1.0, y2)),
        )
        boxes.append((x1, y1, x2, y2))

    return boxes


def _is_bgr(frame: np.ndarray) -> bool:
    """
    Heuristic: OpenCV loads images as BGR. We assume BGR input by default
    since the CV pipeline receives frames decoded via cv2.imdecode.
    """
    return True
