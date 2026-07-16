"""
TASK-6.2 — Cue generator for form corrections.

Loads form_thresholds.yaml, identifies violated thresholds,
sorts by severity_weight descending, returns top 2 cue strings.
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


def generate_cues(
    angle_map: dict[str, float],
    exercise_type: str,
) -> list[str]:
    """
    Generate up to 2 form-correction cues for the current frame.

    Evaluates both regular ``thresholds`` (min/max angle checks) and, for
    plank, ``plank_checks`` (alignment checks using multiple involved_angles).

    Args:
        angle_map:     Dict of angle_name -> degrees.
        exercise_type: Exercise key (e.g. "squat", "plank").

    Returns:
        List of up to 2 cue strings, sorted by severity (highest first).
        Returns an empty list when no violations exist or exercise unknown.
    """
    config = _load_thresholds()
    exercise_cfg = config.get(exercise_type)
    if not exercise_cfg:
        return []

    violations: list[tuple[int, str]] = []  # (severity_weight, cue_string)

    # --- Regular threshold checks (min/max per angle) ---
    thresholds = exercise_cfg.get("thresholds", {})
    for angle_name, threshold in thresholds.items():
        value = angle_map.get(angle_name)
        if value is None:
            continue

        min_val = threshold.get("min")
        max_val = threshold.get("max")
        severity = int(threshold.get("severity_weight", 1))

        if min_val is not None and value < min_val:
            cue = threshold.get("cue_low", f"{angle_name} too low")
            violations.append((severity, cue))
        elif max_val is not None and value > max_val:
            cue = threshold.get("cue_high", f"{angle_name} too high")
            violations.append((severity, cue))

    # --- Plank-specific static alignment checks ---
    # Each plank_check uses involved_angles to determine whether any of the
    # named angles are outside the thresholds defined in the main thresholds
    # block. If any involved angle is violated, the check's cue is emitted
    # (with its own severity_weight) instead of the per-angle cue.
    plank_checks = exercise_cfg.get("plank_checks", {})
    for _check_name, check in plank_checks.items():
        involved = check.get("involved_angles", [])
        severity = int(check.get("severity_weight", 1))
        cue = check.get("cue", "Maintain alignment")

        # The check fires when ANY of the involved angles violates its threshold.
        check_violated = False
        for angle_name in involved:
            value = angle_map.get(angle_name)
            if value is None:
                continue
            threshold = thresholds.get(angle_name, {})
            min_val = threshold.get("min")
            max_val = threshold.get("max")
            if (min_val is not None and value < min_val) or \
               (max_val is not None and value > max_val):
                check_violated = True
                break

        if check_violated:
            violations.append((severity, cue))

    # --- Sort by severity descending, deduplicate, return top 2 ---
    violations.sort(key=lambda x: x[0], reverse=True)
    seen: set[str] = set()
    result: list[str] = []
    for _, cue in violations:
        if cue not in seen:
            seen.add(cue)
            result.append(cue)
        if len(result) >= 2:
            break

    return result
