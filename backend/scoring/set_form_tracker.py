"""
TASK-6.4 — Per-set form score tracker.

Maintains a running mean of per-frame form scores for the current set.
Resets on new set start.

Design ref: §2.3, §4.3. REQs: REQ-3.5.
"""

from __future__ import annotations


class SetFormTracker:
    """Track the running average form score for the current set.

    Usage::

        tracker = SetFormTracker()
        tracker.add_sample(100)
        tracker.add_sample(80)
        tracker.add_sample(60)
        tracker.average()   # → 80.0
        tracker.reset()
        tracker.average()   # → 100.0  (no samples → perfect score default)
    """

    def __init__(self) -> None:
        self._total: int = 0
        self._count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def add_sample(self, score: int) -> None:
        """Add a per-frame form score sample to the running total.

        Args:
            score: Integer score in [0, 100] for a single video frame.
        """
        self._total += score
        self._count += 1

    def average(self) -> float:
        """Return the running mean of all samples added since last reset.

        Returns:
            The mean score as a float. Returns 100.0 when no samples have
            been added yet (the set has not started, so form is assumed
            perfect until evidence says otherwise).
        """
        if self._count == 0:
            return 100.0
        return self._total / self._count

    def reset(self) -> None:
        """Clear all accumulated samples.

        Called when a new set begins (exercise change, auto-close on
        pause, or manual session restart).
        """
        self._total = 0
        self._count = 0

    @property
    def sample_count(self) -> int:
        """Number of form score samples added since the last reset."""
        return self._count
