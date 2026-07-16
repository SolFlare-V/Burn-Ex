"""
TASK-6.6 — Scoring engine: score_frame(processed_frame, confirmed_type) → ScoringResult

Routes each frame to the appropriate scoring path:
  - occluded frame  → early-exit with warning "Move into frame"
  - confirmed_type is None → early-exit with empty result (no exercise yet)
  - confirmed_type == "plank" → plank_scorer
  - any other exercise → cue_generator + form_score

Design ref: §2.3. REQs: REQ-3.1–REQ-3.7.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend.scoring.cue_generator import generate_cues
from backend.scoring.form_score import compute_frame_score
from backend.scoring.plank_scorer import score_plank


@dataclass
class ScoringResult:
    """Output of a single scored frame."""
    cues: list[str] = field(default_factory=list)
    score: int = 0
    warning: str | None = None


def score_frame(processed_frame, confirmed_type: str | None) -> ScoringResult:
    """
    Score a single processed video frame.

    Args:
        processed_frame: A ``ProcessedFrame`` instance produced by the CV
                         pipeline.  Must expose ``.occluded: bool`` and
                         ``.angle_map: dict[str, float]``.
        confirmed_type:  The currently confirmed exercise type (e.g.
                         ``"squat"``, ``"plank"``), or ``None`` when the
                         exercise has not yet been confirmed.

    Returns:
        A :class:`ScoringResult` with cues, a 0–100 form score, and an
        optional warning string.

    Behaviour:
        1. **Occlusion guard** — if ``processed_frame.occluded`` is ``True``
           the engine immediately returns
           ``ScoringResult(cues=[], score=0, warning="Move into frame")``
           and skips all angle evaluation (REQ-3.6).
        2. **No confirmed type** — if ``confirmed_type`` is ``None`` the
           engine returns ``ScoringResult(cues=[], score=0, warning=None)``.
        3. **Plank path** — delegates to :func:`score_plank` which handles
           static-hold quality scoring (REQ-3.7).
        4. **Regular path** — runs :func:`generate_cues` and
           :func:`compute_frame_score` for all other confirmed exercise types.
    """
    # ── Occlusion guard (REQ-3.6, REQ-1.4) ──────────────────────────────────
    if processed_frame.occluded:
        return ScoringResult(cues=[], score=0, warning="Move into frame")

    # ── No confirmed exercise type yet ──────────────────────────────────────
    if confirmed_type is None:
        return ScoringResult(cues=[], score=0, warning=None)

    angle_map: dict[str, float] = processed_frame.angle_map

    # ── Plank path (REQ-3.7) ────────────────────────────────────────────────
    if confirmed_type == "plank":
        cues, score = score_plank(angle_map)
        return ScoringResult(cues=cues, score=score, warning=None)

    # ── Regular exercise path ────────────────────────────────────────────────
    cues: list[str] = generate_cues(angle_map, confirmed_type)
    score: int = compute_frame_score(angle_map, confirmed_type)
    return ScoringResult(cues=cues, score=score, warning=None)
