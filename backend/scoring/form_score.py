"""
TASK-6.3 — Per-frame form score calculator.

Loads config/form_thresholds.yaml (shared with cue_generator.py),
checks each threshold in the exercise config, and computes:

    frame_score = max(0, 100 - sum(penalty for each violation))

Design ref: §2.3. REQs: REQ-3.4, REQ-3.5.
"""

from __future__ import annotations

import os
from functools import lru_cache

import yaml

_HERE = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(os.path.dirname(_HERE))
_THRESHOLDS_PATH = os.path.join(_PROJECT_ROOT, "config", "form_thresholds.yaml")


@lru_cache(maxsize=1)
def _load_thresholds() -> dict:
    with open(_THRESHOLDS_PATH, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def compute_frame_score(
    angle_map: dict[str, float],
    exercise_type: str,
) -> int:
    """
    Compute a form score for a single video frame.

    For each threshold defined under the exercise type in
    ``config/form_thresholds.yaml``, check whether the corresponding angle in
    *angle_map* violates the ``min`` or ``max`` bound.  When a violation is
    detected the threshold's ``penalty`` value is accumulated.  The final
    score is floored at 0.

    Args:
        angle_map:     Dict mapping angle_name -> degrees (float).
        exercise_type: Exercise key as it appears in form_thresholds.yaml
                       (e.g. "squat", "push_up", "plank").

    Returns:
        Integer score in [0, 100].  100 = perfect form, lower = more violations.
    """
    config = _load_thresholds()
    exercise_cfg = config.get(exercise_type)
    if not exercise_cfg:
        return 100  # unknown exercise — no deduction

    thresholds = exercise_cfg.get("thresholds", {})
    total_penalty = 0

    for angle_name, threshold in thresholds.items():
        value = angle_map.get(angle_name)
        if value is None:
            continue  # angle not available for this frame — skip

        min_val = threshold.get("min")
        max_val = threshold.get("max")
        penalty = int(threshold.get("penalty", 0))

        if (min_val is not None and value < min_val) or \
           (max_val is not None and value > max_val):
            total_penalty += penalty

    return max(0, 100 - total_penalty)


# ---------------------------------------------------------------------------
# Backwards-compatibility alias (used by earlier scaffolding)
# ---------------------------------------------------------------------------
calculate_frame_score = compute_frame_score
