"""
Confirmation window for exercise type classification.

Maintains a sliding deque of the last N classification results.
Returns a confirmed type when a majority of window slots hold the same
non-None class. Majority (> 50%) is used instead of unanimous consensus
so that occasional mis-classifications during correct movement don't
prevent confirmation.

Window size is 6 frames (~400ms at 15fps) — small enough to confirm
quickly when the user starts an exercise, large enough to suppress
noise from single-frame mis-classifications.
"""

from __future__ import annotations

from collections import Counter, deque

WINDOW_SIZE = 6
MAJORITY_THRESHOLD = 0.6  # 60% of window must agree (4 of 6 frames)


class ConfirmationWindow:
    """Sliding window that confirms exercise type by majority vote."""

    def __init__(
        self,
        window_size: int = WINDOW_SIZE,
        majority: float = MAJORITY_THRESHOLD,
    ) -> None:
        self._window: deque[str | None] = deque(maxlen=window_size)
        self._window_size = window_size
        self._majority = majority

    def update(self, exercise_type: str | None) -> str | None:
        """
        Add a new classification result and return confirmed type if majority.

        Args:
            exercise_type: Predicted class or None (UNKNOWN/low-confidence).

        Returns:
            The exercise type that appears in >= majority of window slots,
            or None if no type meets the threshold or the window is not full.

        Note: None inputs count toward flushing the window — a run of None
        frames will replace the previous majority within window_size frames,
        clearing stale classifications when the camera loses sight of the user.
        """
        self._window.append(exercise_type)

        # Return as soon as we have >= 3 frames and a majority, not just when full.
        # This means the first detection can fire after 3 frames (~200ms at 15fps)
        # instead of waiting for the window to fill to 6.
        if len(self._window) < 3:
            return None

        # Count non-None votes only
        counts = Counter(s for s in self._window if s is not None)
        if not counts:
            return None

        top_type, top_count = counts.most_common(1)[0]
        # Require majority relative to actual window size so far
        if top_count / len(self._window) >= self._majority:
            return top_type

        return None

    def reset(self) -> None:
        """Clear the window."""
        self._window.clear()

    @property
    def current_window(self) -> list[str | None]:
        return list(self._window)
