"""
TASK-5.5 — ML classification pipeline.

classify_frame(angle_map) -> ClassificationResult

Chains: feature_extractor -> classifier -> knee-visibility gate ->
        confirmation_window -> unrecognised_timer
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from backend.ml.feature_extractor import extract_features
from backend.ml.classifier import predict, predict_proba
from backend.ml.confirmation_window import ConfirmationWindow
from backend.ml.unrecognised_timer import UnrecognisedTimer

# ---------------------------------------------------------------------------
# Knee-visibility gate
#
# Exercises that require knee landmarks to be meaningfully distinguished
# from floor-based exercises (plank, push_up). When the classifier predicts
# one of these classes but BOTH knee angles are absent from the angle_map,
# the prediction is suppressed (treated as None).
#
# Why targeted rather than universal:
#   - shoulder_press and bicep_curl legitimately don't involve knees.
#     Their triplet sets don't compute knee angles, so knees will always
#     be absent when those exercises are being performed.  A universal gate
#     would permanently block them.
#   - plank, squat, lunge, push_up all require knee evidence to be
#     distinguished from each other. Without real knee angles the model
#     relies on imputed medians (164.9 / 152.9) which fall squarely in
#     the plank training distribution, causing the plank feedback loop.
#
# The gate fires when:
#   1. The classifier predicts a class in _KNEE_REQUIRED_CLASSES, AND
#   2. Neither "left_knee" nor "right_knee" appears in the angle_map
#      (meaning MediaPipe did not produce a confident reading for either
#       knee landmark, visibility < 0.5 in confidence_filter.py).
# ---------------------------------------------------------------------------
_KNEE_REQUIRED_CLASSES: frozenset[str] = frozenset({
    "plank",
    "squat",
    "lunge",
    "push_up",
})


@dataclass
class ClassificationResult:
    """Result of classifying a single frame."""
    confirmed_type: str | None      # Confirmed exercise type, or None
    confidence: float               # Classifier confidence for the prediction
    unrecognised_warning: bool      # True once when unrecognised > 3 seconds
    class_probabilities: dict[str, float] = field(default_factory=dict)
    """Full probability distribution over exercise classes.
    Empty dict when the knee-visibility gate fires or the model is not loaded.
    Used by the calorie engine for confidence-weighted MET to reduce abrupt
    MET jumps during borderline classifications.
    """


class MLPipeline:
    """
    Stateful ML pipeline — maintains confirmation window and unrecognised timer
    across frames. Create one instance per active session.
    """

    def __init__(self) -> None:
        self._confirmation_window = ConfirmationWindow()
        self._unrecognised_timer = UnrecognisedTimer()

    def classify_frame(
        self,
        angle_map: dict[str, float],
        elapsed_seconds: float = 0.067,  # ~15fps default
    ) -> ClassificationResult:
        """
        Classify a single frame's angle map.

        Args:
            angle_map:        Dict of angle_name -> degrees from CV pipeline.
            elapsed_seconds:  Time since last frame (for unrecognised timer).

        Returns:
            ClassificationResult with confirmed_type, confidence, warning flag.
        """
        # Stage 1: Feature extraction
        features = extract_features(angle_map)

        # Stage 2: Classifier prediction
        raw_type, confidence = predict(features)

        # Stage 2a: Full probability distribution (for confidence-weighted MET)
        class_probabilities = predict_proba(features)

        # Stage 2b: Knee-visibility gate
        # If the classifier predicts a leg/floor exercise but neither knee
        # angle is present in the angle_map, suppress the prediction.
        # This prevents the plank feedback loop: once plank is confirmed the
        # plank triplet set stops computing knees, imputed median knee values
        # look like plank training data, and plank fires forever regardless
        # of what the user is actually doing.
        # shoulder_press and bicep_curl are exempt — they never use knees.
        if (
            raw_type in _KNEE_REQUIRED_CLASSES
            and "left_knee" not in (angle_map or {})
            and "right_knee" not in (angle_map or {})
        ):
            raw_type = None
            confidence = 0.0
            # Gate fires: clear probabilities so the calorie engine falls
            # through to standard single-class MET rather than using
            # a distribution dominated by spurious knee-exercise classes.
            class_probabilities = {}

        # Debug: log every 30 frames so server console shows classifier state
        # without flooding. Remove once detection is confirmed working.
        self._debug_frame_count = getattr(self, '_debug_frame_count', 0) + 1
        if self._debug_frame_count % 30 == 0:
            import logging
            _log = logging.getLogger(__name__)
            _log.info(
                "[ML] raw=%s conf=%.2f angles=%s",
                raw_type, confidence,
                {k: round(v, 1) for k, v in (angle_map or {}).items()},
            )

        # Stage 3: Confirmation window
        confirmed_type = self._confirmation_window.update(raw_type)

        # Stage 4: Unrecognised timer
        unrecognised_warning = self._unrecognised_timer.tick(
            confirmed_type, elapsed_seconds
        )

        return ClassificationResult(
            confirmed_type=confirmed_type,
            confidence=confidence,
            unrecognised_warning=unrecognised_warning,
            class_probabilities=class_probabilities,
        )

    def reset(self) -> None:
        """Reset all stateful components (e.g. on session end)."""
        self._confirmation_window.reset()
        self._unrecognised_timer.reset()


# ---------------------------------------------------------------------------
# Module-level convenience function (single shared pipeline instance)
# for use in the WebSocket handler — one pipeline per session is better
# but this satisfies the TASK-5.5 function signature requirement.
# ---------------------------------------------------------------------------
_default_pipeline = MLPipeline()


def classify_frame(angle_map: dict[str, float]) -> ClassificationResult:
    """
    Module-level classify_frame using a shared default pipeline.
    Use MLPipeline() directly for per-session isolation.
    """
    return _default_pipeline.classify_frame(angle_map)
