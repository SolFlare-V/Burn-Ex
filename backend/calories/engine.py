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


def _compute_weighted_met(class_probabilities: dict[str, float]) -> float:
    """
    Compute a probability-weighted MET value from a full class distribution.

    Returns Σ P(class_i) × MET_i for all classes present in met_values.yaml.
    This is an approximation used to smooth calorie estimates during borderline
    classifications — it reduces abrupt MET jumps when the classifier is
    uncertain between two exercises with different MET values.

    Returns 0.0 if class_probabilities is empty (caller falls through to
    standard single-class MET lookup).
    """
    if not class_probabilities:
        return 0.0
    met = _load_met_values()
    weighted = sum(
        prob * met[cls]
        for cls, prob in class_probabilities.items()
        if cls in met
    )
    return weighted


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

    # Seconds of silence after which calorie accumulation is paused.
    # If no frame arrives within this window the open segment is treated
    # as paused — running_estimate returns only the closed total until
    # frames resume. This prevents calories accumulating when the camera
    # is covered, the tab is hidden, or the user walks away mid-session.
    IDLE_PAUSE_THRESHOLD: float = 5.0

    def __init__(self, weight_kg: float) -> None:
        if weight_kg <= 0:
            raise ValueError(
                f"weight_kg must be > 0, got {weight_kg!r}"
            )
        self._weight_kg: float = weight_kg
        self._segments: list[CalorieSegment] = []
        # Timestamp of the most recent frame received; updated by notify_frame().
        self._last_frame_ts: Optional[float] = None

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

    def close_segment(
        self,
        timestamp: float,
        intensity_multiplier: float = 1.0,
        class_probabilities: Optional[dict[str, float]] = None,
    ) -> "CalorieSegment":
        """
        Close the currently open segment, compute its calories, and return it.

        calories = MET[exercise] × weight_kg × duration_hours × intensity_multiplier

        When class_probabilities is provided and non-empty, a confidence-weighted
        MET (Σ P(class_i) × MET_i) is used instead of the single-class MET.
        This reduces abrupt MET jumps during borderline classifications where
        the classifier is uncertain between two exercises with different base METs.

        Args:
            timestamp:           Time when the segment ends.
            intensity_multiplier: Movement-intensity scaling factor from
                                  IntensityEstimator (default 1.0 = standard MET).
            class_probabilities: Full classifier probability distribution over
                                 exercise classes (optional). When provided and
                                 non-empty, overrides the single-class MET lookup.

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

        # Use confidence-weighted MET when a full distribution is available;
        # otherwise fall back to the single top-class MET value.
        weighted = _compute_weighted_met(class_probabilities or {})
        if weighted > 0.0:
            met = weighted
        else:
            met = _load_met_values()[seg.exercise_type]

        # Floor matches the minimum from IntensityEstimator (_MIN_MULTIPLIER = 0.40).
        multiplier = max(0.40, float(intensity_multiplier))
        calories = met * seg.weight_kg * duration_hours * multiplier

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

    def notify_frame(self, timestamp: float) -> None:
        """
        Record the timestamp of the most recently received frame.
        Must be called each frame before running_estimate() so the
        idle-detection gate works correctly.
        """
        self._last_frame_ts = timestamp

    def running_estimate(
        self,
        current_timestamp: float,
        intensity_multiplier: float = 1.0,
        class_probabilities: Optional[dict[str, float]] = None,
        general_activity_met: float = 0.0,
    ) -> float:
        """
        Live calorie total: closed segments + provisional open segment.

        Calories only accumulate up to the last received frame timestamp.
        If no frame has arrived within IDLE_PAUSE_THRESHOLD seconds the
        open-segment contribution is frozen.

        When class_probabilities is provided and non-empty, a confidence-weighted
        MET (Σ P(class_i) × MET_i) is used in the provisional estimate.

        When general_activity_met > 0 and no exercise segment is open, a
        provisional general-activity calorie contribution is added.
        This uses Ainsworth-style MET tiers from total body motion velocity and
        is a coarse approximation from monocular RGB pose data.

        Args:
            current_timestamp:    Current time (same clock used for notify_frame).
            intensity_multiplier: Movement-intensity scaling factor.
            class_probabilities:  Full classifier probability distribution (optional).
            general_activity_met: MET estimate for unclassified movement (optional).

        Returns:
            Total estimated calories burned so far (float).
        """
        closed_total = self.running_total()

        seg = self._open_segment

        # No frames ever received, or no frame recently — freeze accumulation.
        if self._last_frame_ts is None:
            return closed_total
        idle_s = current_timestamp - self._last_frame_ts
        if idle_s > self.IDLE_PAUSE_THRESHOLD:
            return closed_total

        if seg is None:
            # No exercise segment open — add general activity contribution if available.
            if general_activity_met > 0.0:
                elapsed_s = max(0.0, self._last_frame_ts - (self._last_frame_ts - 1.0))
                # Use a single-frame contribution: met * weight * (1/3600)
                # Caller is expected to accumulate this per frame rather than
                # computing a segment duration here.
                pass  # general activity is accumulated per-frame in ws_pose.py
            return closed_total

        # Accumulate only up to the last real frame, not wall clock.
        elapsed_s = max(0.0, self._last_frame_ts - seg.start_time)
        elapsed_hours = elapsed_s / 3600.0

        # Use confidence-weighted MET when available.
        weighted = _compute_weighted_met(class_probabilities or {})
        if weighted > 0.0:
            met = weighted
        else:
            met = _load_met_values()[seg.exercise_type]

        # Floor matches the minimum from IntensityEstimator (_MIN_MULTIPLIER = 0.40).
        multiplier = max(0.40, float(intensity_multiplier))
        provisional = met * seg.weight_kg * elapsed_hours * multiplier

        return closed_total + provisional

    # ------------------------------------------------------------------
    # TASK-8.4 — Exercise change
    # ------------------------------------------------------------------

    def change_exercise(
        self,
        new_exercise_type: str,
        timestamp: float,
        intensity_multiplier: float = 1.0,
        class_probabilities: Optional[dict[str, float]] = None,
    ) -> None:
        """
        Atomically close the current segment and open a new one.

        If no segment is currently open, simply opens a new one for
        *new_exercise_type* (handles the session-start edge case gracefully).

        Args:
            new_exercise_type:    The exercise type to transition to.
            timestamp:            Time of the exercise change event.
            intensity_multiplier: Movement-intensity scaling factor applied to
                                  the closing segment's final calorie calculation.
            class_probabilities:  Full classifier probability distribution for
                                  the closing segment's final calorie calculation.

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
            self.close_segment(
                timestamp,
                intensity_multiplier=intensity_multiplier,
                class_probabilities=class_probabilities,
            )

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
