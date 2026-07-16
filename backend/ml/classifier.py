"""
TASK-5.2 — Exercise classifier wrapper.

Loads models/exercise_classifier.pkl at module initialisation using joblib.
Exposes predict(feature_vector) -> (exercise_type | None, confidence).
"""

from __future__ import annotations

import os

import joblib
import numpy as np

# ---------------------------------------------------------------------------
# Resolve model path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "exercise_classifier.pkl")

CONFIDENCE_THRESHOLD = 0.6


def _load_model():
    if not os.path.exists(_MODEL_PATH):
        raise FileNotFoundError(
            f"exercise_classifier.pkl not found at {_MODEL_PATH}. "
            "Run data/train_classifier.py first (TASK-4.3)."
        )
    return joblib.load(_MODEL_PATH)


# Module-level singleton
try:
    _clf = _load_model()
    _MODEL_LOADED = True
except FileNotFoundError:
    _clf = None
    _MODEL_LOADED = False


def predict(
    feature_vector: np.ndarray | None,
) -> tuple[str | None, float]:
    """
    Predict the exercise type from a feature vector.

    Args:
        feature_vector: numpy array of shape (10,) from feature_extractor,
                        or None.

    Returns:
        (exercise_type, confidence) where:
          - (None, 0.0)      if feature_vector is None
          - (None, max_prob) if max_prob < CONFIDENCE_THRESHOLD (UNKNOWN)
          - (class, prob)    if confident prediction
    """
    if feature_vector is None:
        return (None, 0.0)

    if not _MODEL_LOADED or _clf is None:
        return (None, 0.0)

    vec = feature_vector.reshape(1, -1)
    proba = _clf.predict_proba(vec)[0]
    max_idx = int(np.argmax(proba))
    max_prob = float(proba[max_idx])
    class_name: str = _clf.classes_[max_idx]

    if max_prob < CONFIDENCE_THRESHOLD:
        return (None, max_prob)

    return (class_name, max_prob)


def is_model_loaded() -> bool:
    """Return True if the classifier model was loaded successfully."""
    return _MODEL_LOADED
