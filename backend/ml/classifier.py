"""
TASK-5.2 — Exercise classifier wrapper.

Loads models/exercise_classifier.pkl at module initialisation using joblib.
Exposes predict(feature_vector) -> (exercise_type | None, confidence).
"""

from __future__ import annotations

import logging
import os

import joblib
import numpy as np

# ---------------------------------------------------------------------------
# Feature vector diagnostic logging.
# Enable with:  BURN_EX_LOG_FEATURES=1  in the environment before starting
# the backend server.  Logs every prediction to the standard logger so the
# output appears in the server console / terminal window.
# ---------------------------------------------------------------------------
_FEATURE_LOG_ENABLED = os.environ.get("BURN_EX_LOG_FEATURES", "0") == "1"
_feature_logger = logging.getLogger("burn_ex.classifier")

# ---------------------------------------------------------------------------
# Resolve model path
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_MODEL_PATH = os.path.join(_PROJECT_ROOT, "models", "exercise_classifier.pkl")

CONFIDENCE_THRESHOLD = 0.35  # Low enough for partial-body frames where probability
# is spread across similar-looking exercises (e.g. bicep_curl vs shoulder_press).
# At 6 classes random baseline = 0.17; 0.35 is still well above noise.


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


_FEATURE_NAMES = [
    "left_knee", "right_knee", "left_hip", "right_hip",
    "left_elbow", "right_elbow", "left_shoulder", "right_shoulder",
    "trunk", "left_ankle",
]


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

    # ------------------------------------------------------------------
    # Diagnostic feature-vector logging (BURN_EX_LOG_FEATURES=1)
    # Prints the raw angles and per-class probabilities for every frame
    # so you can confirm what values the model is actually receiving.
    # ------------------------------------------------------------------
    if _FEATURE_LOG_ENABLED:
        angles_str = "  ".join(
            f"{name}={vec[0, i]:.1f}" for i, name in enumerate(_FEATURE_NAMES)
        )
        probs_str = "  ".join(
            f"{cls}={proba[j]:.3f}" for j, cls in enumerate(_clf.classes_)
        )
        verdict = class_name if max_prob >= CONFIDENCE_THRESHOLD else "BELOW_THRESHOLD"
        _feature_logger.info(
            "[FEATURE] %s | [PROBA] %s | [VERDICT] %s (%.3f)",
            angles_str, probs_str, verdict, max_prob,
        )

    if max_prob < CONFIDENCE_THRESHOLD:
        return (None, max_prob)

    return (class_name, max_prob)


def is_model_loaded() -> bool:
    """Return True if the classifier model was loaded successfully."""
    return _MODEL_LOADED
