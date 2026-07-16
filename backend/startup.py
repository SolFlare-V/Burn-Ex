"""
TASK-12.3 -- Startup model-loading validation.

Registered as a FastAPI lifespan startup handler.
Loads MediaPipe Pose and the exercise classifier at startup.
If either fails, logs a fatal error and exits with code 1.

Design ref: sec 7.1. REQs: REQ-10.3.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

_CLASSIFIER_PATH = Path(__file__).resolve().parent.parent / "models" / "exercise_classifier.pkl"


def validate_models() -> None:
    """
    Load MediaPipe Pose and the Random Forest classifier.
    Exits the process with sys.exit(1) if either cannot be loaded.
    """
    # --- MediaPipe Pose ---
    try:
        import mediapipe as mp
        pose = mp.solutions.pose.Pose(
            static_image_mode=True,
            model_complexity=1,
            enable_segmentation=False,
        )
        pose.close()
        logger.info("Startup check: MediaPipe Pose loaded OK.")
    except Exception as exc:
        logger.critical("FATAL: MediaPipe Pose failed to load: %s", exc)
        sys.exit(1)

    # --- Exercise classifier ---
    try:
        import joblib
        if not _CLASSIFIER_PATH.exists():
            raise FileNotFoundError(
                f"Classifier not found at {_CLASSIFIER_PATH}"
            )
        clf = joblib.load(_CLASSIFIER_PATH)
        logger.info(
            "Startup check: classifier loaded OK (%s).",
            type(clf).__name__,
        )
    except Exception as exc:
        logger.critical("FATAL: Exercise classifier failed to load: %s", exc)
        sys.exit(1)

    logger.info("Startup model validation complete.")
