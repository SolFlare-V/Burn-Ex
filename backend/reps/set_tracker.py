"""
TASK-7.4 — Set tracker for rep counting.

Design ref: §2.4
REQs: REQ-4.4, REQ-4.5, REQ-4.6

Maintains current set number, per-set rep count, and list of closed sets.
Exposes count_rep(), close_set(avg_form_score) → ClosedSet, exercise_changed().
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ClosedSet:
    """Represents a completed set."""

    set_number: int
    reps: int
    avg_form_score: float


class SetTracker:
    """
    Tracks rep counts and set lifecycle.

    Set numbers start at 1. Each call to ``close_set()`` records the
    current rep count, advances the set number, and resets the counter.

    ``exercise_changed()`` force-closes only when there are reps > 0 in the
    current set; it returns ``None`` when the current set is empty, leaving
    the set number unchanged so no empty sets are persisted (REQ-4.5).
    """

    def __init__(self) -> None:
        self._set_number: int = 1
        self._current_reps: int = 0
        self._closed_sets: list[ClosedSet] = []

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def count_rep(self) -> None:
        """Increment the current set's rep count by 1."""
        self._current_reps += 1

    def close_set(self, avg_form_score: float = 0.0) -> ClosedSet:
        """
        Close the current set regardless of rep count.

        Records the set, resets ``_current_reps`` to 0, and increments
        ``_set_number``.  Returns the newly created ``ClosedSet``.

        Args:
            avg_form_score: The average form score for the set (0–100).

        Returns:
            The closed ``ClosedSet`` instance.
        """
        closed = ClosedSet(
            set_number=self._set_number,
            reps=self._current_reps,
            avg_form_score=avg_form_score,
        )
        self._closed_sets.append(closed)
        self._current_reps = 0
        self._set_number += 1
        return closed

    def exercise_changed(self) -> ClosedSet | None:
        """
        Force-close the current set if it has at least one rep.

        Called when the Session Manager detects an exercise change event
        (REQ-4.5). If the current set has no reps, nothing is closed and
        ``None`` is returned so no empty set record is persisted.

        Returns:
            The closed ``ClosedSet`` if ``current_rep_count > 0``, else ``None``.
        """
        if self._current_reps > 0:
            return self.close_set(avg_form_score=0.0)
        return None

    # ------------------------------------------------------------------
    # Read-only properties
    # ------------------------------------------------------------------

    @property
    def current_set_number(self) -> int:
        """The 1-based number of the currently open set."""
        return self._set_number

    @property
    def current_rep_count(self) -> int:
        """Reps counted in the currently open set."""
        return self._current_reps

    @property
    def closed_sets(self) -> list[ClosedSet]:
        """A copy of all closed sets in chronological order."""
        return list(self._closed_sets)
