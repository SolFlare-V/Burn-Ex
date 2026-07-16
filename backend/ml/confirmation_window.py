"""
TASK-5.3 — Confirmation window for exercise type classification.

Maintains a sliding deque of the last 10 classification results.
Returns a confirmed type only when all 10 slots hold the same non-None class.
"""

from __future__ import annotations

from collections import deque

WINDOW_SIZE = 10


class ConfirmationWindow:
    """Sliding window that confirms exercise type only on unanimous consensus."""

    def __init__(self, window_size: int = WINDOW_SIZE) -> None:
        self._window: deque[str | None] = deque(maxlen=window_size)
        self._window_size = window_size

    def update(self, exercise_type: str | None) -> str | None:
        """
        Add a new classification result and return confirmed type if consensus.

        Args:
            exercise_type: Predicted class or None (UNKNOWN).

        Returns:
            The confirmed exercise type string if all window slots contain the
            same non-None class, otherwise None.
        """
        self._window.append(exercise_type)

        if len(self._window) < self._window_size:
            return None

        # All slots must be the same non-None value
        first = self._window[0]
        if first is None:
            return None

        if all(slot == first for slot in self._window):
            return first

        return None

    def reset(self) -> None:
        """Clear the window."""
        self._window.clear()

    @property
    def current_window(self) -> list[str | None]:
        return list(self._window)
