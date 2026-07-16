"""
TASK-5.4 — Unrecognised exercise timer.

Tracks consecutive seconds with no confirmed exercise type.
Emits a warning once when unrecognised duration exceeds 3 seconds.
Resets when a confirmed type is received.
"""

from __future__ import annotations

UNRECOGNISED_WARNING_THRESHOLD = 3.0  # seconds


class UnrecognisedTimer:
    """
    Tracks how long the exercise type has been unrecognised.
    Emits True once per unrecognised episode when threshold is exceeded.
    """

    def __init__(self, threshold: float = UNRECOGNISED_WARNING_THRESHOLD) -> None:
        self._threshold = threshold
        self._accumulated: float = 0.0
        self._warning_emitted: bool = False

    def tick(
        self,
        confirmed_type: str | None,
        elapsed_seconds: float,
    ) -> bool:
        """
        Update timer state for one frame tick.

        Args:
            confirmed_type:  Confirmed exercise type or None (unrecognised).
            elapsed_seconds: Time elapsed since the last tick (seconds).

        Returns:
            True exactly once when accumulated unrecognised time first exceeds
            the threshold. Returns False otherwise.
        """
        if confirmed_type is not None:
            # Reset on any confirmed type
            self._accumulated = 0.0
            self._warning_emitted = False
            return False

        # No confirmed type — accumulate time
        self._accumulated += elapsed_seconds

        if self._accumulated > self._threshold and not self._warning_emitted:
            self._warning_emitted = True
            return True

        return False

    def reset(self) -> None:
        """Manually reset the timer."""
        self._accumulated = 0.0
        self._warning_emitted = False

    @property
    def accumulated_seconds(self) -> float:
        return self._accumulated
