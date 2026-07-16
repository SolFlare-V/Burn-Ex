"""
TASK-6.5 — Plank scoring path.

Accepts an angle_map, delegates to the shared cue_generator and form_score
modules (which load plank thresholds from config/form_thresholds.yaml), and
returns (cues, score) using the same penalty framework as every other exercise.

The plank-specific checks (hip-shoulder-ankle alignment, core proxy angles)
are fully handled by the threshold entries defined under the "plank" key in
form_thresholds.yaml — no duplicated logic is needed here.

Design ref: §2.3.  REQs: REQ-3.7.
"""

from __future__ import annotations

from backend.scoring.cue_generator import generate_cues
from backend.scoring.form_score import compute_frame_score

_EXERCISE = "plank"


def score_plank(angle_map: dict[str, float]) -> tuple[list[str], int]:
    """
    Score a single plank frame.

    Args:
        angle_map: Dict mapping angle name → degrees (float).
                   Expected keys (from form_thresholds.yaml):
                   ``left_hip``, ``right_hip``, ``trunk``, ``left_shoulder``.

    Returns:
        A ``(cues, score)`` tuple where *cues* is a list of up to 2
        corrective cue strings (empty when form is perfect) and *score*
        is an integer in [0, 100] (100 = no violations).
    """
    cues: list[str] = generate_cues(angle_map, _EXERCISE)
    score: int = compute_frame_score(angle_map, _EXERCISE)
    return cues, score
