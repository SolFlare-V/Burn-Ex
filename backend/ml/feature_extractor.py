"""
TASK-5.1 — Feature extractor for exercise classifier.

Converts an angle_map dict into a fixed-length (10,) numpy array.
Missing angles are filled with per-feature medians computed from training data.
Returns None only if the angle_map is completely empty (no angles at all).
"""

from __future__ import annotations

import os

import joblib
import numpy as np

# Must match FEATURE_ANGLES in data/collect_landmarks.py and train_classifier.py
FEATURE_NAMES: list[str] = [
    "left_knee",
    "right_knee",
    "left_hip",
    "right_hip",
    "left_elbow",
    "right_elbow",
    "left_shoulder",
    "right_shoulder",
    "trunk",
    "left_ankle",
]

# ---------------------------------------------------------------------------
# Load per-feature medians from training data for imputation at inference time.
# Falls back to sensible anatomical defaults if model/data not available.
# ---------------------------------------------------------------------------
_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_RAW_DIR = os.path.join(_PROJECT_ROOT, "data", "raw")

# Anatomical neutral-position defaults (degrees) as last-resort fallback
_ANATOMICAL_DEFAULTS: dict[str, float] = {
    "left_knee": 170.0,
    "right_knee": 170.0,
    "left_hip": 170.0,
    "right_hip": 170.0,
    "left_elbow": 165.0,
    "right_elbow": 165.0,
    "left_shoulder": 15.0,   # arm hanging at side — was 60° which biased toward shoulder_press
    "right_shoulder": 15.0,  # arm hanging at side — was 60°
    "trunk": 170.0,
    "left_ankle": 90.0,
}


def _compute_training_medians() -> dict[str, float]:
    """Compute per-feature medians from all collected CSVs."""
    import csv, glob
    data: dict[str, list[float]] = {name: [] for name in FEATURE_NAMES}
    csv_files = glob.glob(os.path.join(_RAW_DIR, "*.csv"))
    for path in csv_files:
        try:
            with open(path, newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    for name in FEATURE_NAMES:
                        val = row.get(name, "")
                        if val:
                            try:
                                data[name].append(float(val))
                            except ValueError:
                                pass
        except Exception:
            pass
    medians: dict[str, float] = {}
    for name in FEATURE_NAMES:
        if data[name]:
            medians[name] = float(np.median(data[name]))
        else:
            medians[name] = _ANATOMICAL_DEFAULTS[name]
    return medians


try:
    _FEATURE_MEDIANS = _compute_training_medians()
    # Override shoulder medians with anatomical neutral (arm at side).
    # The cross-exercise median (~49°) is polluted by shoulder_press data
    # (~118°) and causes the classifier to misidentify bicep_curl as
    # shoulder_press when shoulders aren't visible in frame.
    _FEATURE_MEDIANS["left_shoulder"] = 15.0
    _FEATURE_MEDIANS["right_shoulder"] = 15.0
    # Override trunk median — 76° is a forward-lean posture (squat/plank).
    # Neutral upright trunk = ~170°.
    _FEATURE_MEDIANS["trunk"] = 170.0
    # Override knee medians — the global median (164.9 / 152.9) is dominated
    # by the large squat class (3394 rows of bent-knee data). When these
    # values are imputed for upper-body exercises (bicep_curl, shoulder_press)
    # whose triplet sets never compute knees, the classifier sees a vector
    # that looks like the top of a squat and predicts squat.
    # Neutral upright standing knee = ~175° (nearly fully extended).
    _FEATURE_MEDIANS["left_knee"] = 175.0
    _FEATURE_MEDIANS["right_knee"] = 175.0
    # Similarly, left_ankle median is squat-influenced (148°). Neutral = ~90°.
    _FEATURE_MEDIANS["left_ankle"] = 90.0
except Exception:
    _FEATURE_MEDIANS = dict(_ANATOMICAL_DEFAULTS)


def extract_features(angle_map: dict[str, float]) -> np.ndarray | None:
    """
    Convert an angle_map to a fixed-length feature vector.

    Missing angles are imputed with training-data medians (same strategy used
    during training). Returns None only if angle_map is None or empty.

    Args:
        angle_map: Dict mapping angle name -> degrees, as returned by
                   calculate_angle_map().

    Returns:
        numpy array of shape (10,) with float32 values, or None if
        angle_map is None or empty.
    """
    if not angle_map:
        return None

    features: list[float] = []
    for name in FEATURE_NAMES:
        if name in angle_map:
            features.append(float(angle_map[name]))
        else:
            # Impute with training median
            features.append(_FEATURE_MEDIANS.get(name, _ANATOMICAL_DEFAULTS[name]))

    return np.array(features, dtype=np.float32)
