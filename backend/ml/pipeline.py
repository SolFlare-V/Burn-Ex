"""
TASK-5.5 — ML classification pipeline.

classify_frame(angle_map) -> ClassificationResult

Chains: feature_extractor -> classifier -> confirmation_window -> unrecognised_timer
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from backend.ml.feature_extractor import extract_features
from backend.ml.classifier import predict
from backend.ml.confirmation_window import ConfirmationWindow
from backend.ml.unrecognised_timer import UnrecognisedTimer


@dataclass
class ClassificationResult:
    """Result of classifying a single frame."""
    confirmed_type: str | None      # Confirmed exercise type, or None
    confidence: float               # Classifier confidence for the prediction
    unrecognised_warning: bool      # True once when unrecognised > 3 seconds


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
