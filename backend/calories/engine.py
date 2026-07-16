"""
TASK-8.2 / TASK-8.3 / TASK-8.4 — Calorie Engine.

MET-based calorie accumulation with segmented tracking across exercise changes.

Design ref: §2.5. REQs: REQ-5.1, REQ-5.2, REQ-5.3, REQ-5.5.

Formula: calories = MET[exercise] × weight_kg × duration_hours

Usage::

    engine = CalorieEngine(weight_kg=72.0)
    engine.start_segment("squat", t0)
    # ... frames pass ...
    engine.close_segment(t1)
    total = engine.running_total()

    # Running estimate while segment is open:
    estimate = engine.running_estimate(current_timestamp)

    # Exercise change (atomically closes + opens):
    engine.change_exercise("push_up", t2)
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import datetime
from functools import lru_cache
from pathlib import Path
from typing import Optional

import yaml

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "met_values.yaml"


@lru_cache(maxsize=1)
def _load_met_values() -> dict[str, float]:
    """Load MET values from config/met_values.yaml (cached after first load)."""
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"MET values config not found at {_CONFIG_PATH}"
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    return {k: float(v) for k, v in data.items()}


# ---------------------------------------------------------------------------
# CalorieSegment
# ---------------------------------------------------------------------------

@dataclass
class CalorieSegment:
    """
    Represents a contiguous block of one exercise type within a session.

    Matches the ``calorie_segments`` DB schema (design.md §4.1).

    Attributes:
        exercise_type: Exercise key (e.g. "squat", "push_up").
        weight_kg:     Snapshot of user weight when the segment opened.
        start_time:    Timestamp (float, seconds) when the segment started.
        end_time:      Timestamp when closed; None while still open.
        calories:      Computed on close via MET formula; 0.0 while open.
        duration_seconds: Integer seconds; set on close.
    """
    exercise_type: str
    weight_kg: float
    start_time: float
    end_time: Optional[float] = None
    calories: float = 0.0
    duration_seconds: int = 0

    @property
    def is_open(self) -> bool:
        """True if this segment has not yet been closed."""
        return self.end_time is None


# ---------------------------------------------------------------------------
# CalorieEngine
# ---------------------------------------------------------------------------

class CalorieEngine:
    """
    Tracks calorie expenditure across a session using MET-based accumulation.

    Each exercise change creates a new ``CalorieSegment``.  The total calories
    burned is the sum of all closed segments plus a provisional running
    estimate for the currently open segment.

    Args:
        weight_kg: User body weight in kg. Must be > 0.

    Raises:
        ValueError: If ``weight_kg <= 0``.
    """

    def __init__(self, weight_kg: float) -> None:
        if weight_kg <= 0:
            raise ValueError(
                f"weight_kg must be > 0, got {weight_kg!r}"
            )
        self._weight_kg: float = weight_kg
        self._segments: list[CalorieSegment] = []

    # ------------------------------------------------------------------
    # TASK-8.2 — Segment lifecycle
    # ------------------------------------------------------------------

    def start_segment(self, exercise_type: str, timestamp: float) -> None:
        """
        Open a new calorie segment for *exercise_type*.

        Args:
            exercise_type: Exercise key matching an entry in met_values.yaml.
            timestamp:     Epoch/monotonic time when the segment begins.

        Raises:
            RuntimeError: If a segment is already open (must close first or
                          use ``change_exercise()``).
            KeyError: If *exercise_type* is not in the MET config.
        """
        if self._open_segment is not None:
            raise RuntimeError(
                "A segment is already open. Call close_segment() or "
                "change_exercise() before starting a new one."
            )
        met = _load_met_values()
        if exercise_type not in met:
            raise KeyError(
                f"Exercise '{exercise_type}' not found in met_values.yaml. "
                f"Available: {list(met.keys())}"
            )
        seg = CalorieSegment(
            exercise_type=exercise_type,
            weight_kg=self._weight_kg,
            start_time=timestamp,
        )
        self._segments.append(seg)

    def close_segment(self, timestamp: float) -> CalorieSegment:
        """
        Close the currently open segment, compute its calories, and return it.

        calories = MET[exercise] × weight_kg × duration_hours

        Args:
            timestamp: Time when the segment ends.

        Returns:
            The closed ``CalorieSegment`` with ``calories`` and
            ``duration_seconds`` populated.

        Raises:
            RuntimeError: If no segment is currently open.
        """
        seg = self._open_segment
        if seg is None:
            raise RuntimeError("No open segment to close.")

        duration_s = max(0.0, timestamp - seg.start_time)
        duration_hours = duration_s / 3600.0

        met = _load_met_values()[seg.exercise_type]
        calories = met * seg.weight_kg * duration_hours

        seg.end_time = timestamp
        seg.calories = calories
        seg.duration_seconds = int(duration_s)
        return seg

    def running_total(self) -> float:
        """
        Sum of calories from all **closed** segments.

        Does NOT include a provisional estimate for the open segment.
        Use ``running_estimate(current_timestamp)`` for the live total.
        """
        return sum(s.calories for s in self._segments if not s.is_open)

    # ------------------------------------------------------------------
    # TASK-8.3 — Running estimate (includes open segment)
    # ------------------------------------------------------------------

    def running_estimate(self, current_timestamp: float) -> float:
        """
        Live calorie total: closed segments + provisional open segment.

        Args:
            current_timestamp: Current time used to estimate the open
                               segment's elapsed duration.

        Returns:
            Total estimated calories burned so far (float).
        """
        closed_total = self.running_total()

        seg = self._open_segment
        if seg is None:
            return closed_total

        elapsed_s = max(0.0, current_timestamp - seg.start_time)
        elapsed_hours = elapsed_s / 3600.0
        met = _load_met_values()[seg.exercise_type]
        provisional = met * seg.weight_kg * elapsed_hours

        return closed_total + provisional

    # ------------------------------------------------------------------
    # TASK-8.4 — Exercise change
    # ------------------------------------------------------------------

    def change_exercise(self, new_exercise_type: str, timestamp: float) -> None:
        """
        Atomically close the current segment and open a new one.

        If no segment is currently open, simply opens a new one for
        *new_exercise_type* (handles the session-start edge case gracefully).

        Args:
            new_exercise_type: The exercise type to transition to.
            timestamp:         Time of the exercise change event.

        Raises:
            KeyError: If *new_exercise_type* is not in the MET config.
        """
        # Validate new type before making any changes (atomic guarantee).
        met = _load_met_values()
        if new_exercise_type not in met:
            raise KeyError(
                f"Exercise '{new_exercise_type}' not found in met_values.yaml."
            )

        if self._open_segment is not None:
            self.close_segment(timestamp)

        self.start_segment(new_exercise_type, timestamp)

    # ------------------------------------------------------------------
    # Public read-only accessors
    # ------------------------------------------------------------------

    @property
    def segments(self) -> list[CalorieSegment]:
        """All segments (open and closed) in chronological order."""
        return list(self._segments)

    @property
    def weight_kg(self) -> float:
        """User weight used for calorie calculations."""
        return self._weight_kg

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @property
    def _open_segment(self) -> Optional[CalorieSegment]:
        """The currently open segment, or None."""
        if self._segments and self._segments[-1].is_open:
            return self._segments[-1]
        return None
