"""
Per-person session state for the automatic person identification feature.

Each person detected this session gets a PersonSessionState that mirrors
the per-session state in _SessionState (ws_pose.py) but is keyed to a
person_id rather than a session_id.

The calorie engine itself is NOT duplicated here — identity only determines
which person's bucket receives the frame's calorie contribution.  The actual
CalorieEngine and IntensityEstimator instances live in PersonSessionState
and are swapped in/out when the active person changes.

Data model
----------
PersonSessionState holds:
  - person_id:             UUID assigned by PersonRegistry
  - display_name:          "Person 1", "Person 2", etc. (assigned at creation)
  - first_seen_at:         wall-clock timestamp of first detection
  - last_seen_at:          wall-clock timestamp of most recent detection
  - calorie_engine:        CalorieEngine instance (independent per person)
  - intensity_estimator:   IntensityEstimator instance (independent per person)
  - rep_counter:           RepCounter instance (independent per person)
  - form_tracker:          SetFormTracker instance (independent per person)
  - ml_pipeline:           MLPipeline instance (independent per person)
  - completed_sets:        list of CompletedSet records
  - active_set_exercise:   exercise type of the currently open set, or None
  - active_set_start_reps: rep count at the start of the current set
  - segment_open:          whether a calorie segment is currently open
  - last_confirmed_type:   last confirmed exercise (for ws_pose change logic)
  - intensity_multiplier:  last intensity multiplier value

CompletedSet holds:
  - person_id
  - set_number
  - exercise
  - reps
  - calories
  - avg_form_score
  - timestamp
  - partial: True if the set was finalized due to a person-swap mid-rep
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Optional

from backend.calories.engine import CalorieEngine
from backend.calories.intensity import IntensityEstimator
from backend.ml.pipeline import MLPipeline
from backend.reps.counter import RepCounter
from backend.scoring.set_form_tracker import SetFormTracker


# ---------------------------------------------------------------------------
# CompletedSet — immutable record of a finalized set
# ---------------------------------------------------------------------------

@dataclass
class CompletedSet:
    person_id: str
    set_number: int
    exercise: str
    reps: int
    calories: float
    avg_form_score: float
    timestamp: float          # epoch seconds
    partial: bool = False     # True if finalized mid-rep due to person swap


# ---------------------------------------------------------------------------
# PersonSessionState — all mutable state for one detected person
# ---------------------------------------------------------------------------

class PersonSessionState:
    """
    Mirrors _SessionState from ws_pose.py but is keyed to a person_id.
    One instance per detected person, held by PersonSessionManager.
    """

    def __init__(
        self,
        person_id: str,
        display_name: str,
        weight_kg: float,
        height_cm: float = 0.0,
    ) -> None:
        self.person_id = person_id
        self.display_name = display_name
        self.weight_kg = weight_kg
        self.height_cm = height_cm

        self.first_seen_at: float = time.time()
        self.last_seen_at: float = self.first_seen_at

        # Independent pipeline components per person
        height_m = (height_cm / 100.0) if height_cm > 0 else 0.0
        self.ml_pipeline = MLPipeline()
        self.rep_counter = RepCounter()
        self.form_tracker = SetFormTracker()
        self.calorie_engine = CalorieEngine(weight_kg=weight_kg)
        self.intensity_estimator = IntensityEstimator(fps=15.0, height_m=height_m)

        # Exercise-change tracking (mirrors ws_pose._SessionState)
        self.last_confirmed_type: Optional[str] = None
        self.segment_open: bool = False
        self.intensity_multiplier: float = 1.0

        # Per-person set history
        self.completed_sets: list[CompletedSet] = []
        self._set_number_counter: int = 0

    # ------------------------------------------------------------------
    # Set management
    # ------------------------------------------------------------------

    def finalize_current_set(self, partial: bool = False) -> Optional[CompletedSet]:
        """
        Finalize the currently active set and append it to completed_sets.

        Called when:
          - A set naturally completes (rep counter detects end-of-set).
          - A person swap occurs mid-rep (partial=True).
          - The exercise type changes.

        Returns the CompletedSet record, or None if no set was active.
        """
        rep_state = self.rep_counter.get_state() if hasattr(self.rep_counter, "get_state") else None
        current_reps = getattr(rep_state, "rep_count", 0) if rep_state else 0
        current_exercise = self.last_confirmed_type

        if current_exercise is None or current_reps == 0:
            return None

        self._set_number_counter += 1
        avg_form = self.form_tracker.average_score() if hasattr(self.form_tracker, "average_score") else 0.0

        # Close calorie segment to get final calories for this set
        calories_for_set = 0.0
        if self.segment_open:
            try:
                seg = self.calorie_engine.close_segment(
                    time.time(),
                    intensity_multiplier=self.intensity_multiplier,
                )
                calories_for_set = seg.calories
                self.segment_open = False
            except RuntimeError:
                calories_for_set = self.calorie_engine.running_total()

        completed = CompletedSet(
            person_id=self.person_id,
            set_number=self._set_number_counter,
            exercise=current_exercise,
            reps=current_reps,
            calories=round(calories_for_set, 4),
            avg_form_score=round(avg_form, 1),
            timestamp=time.time(),
            partial=partial,
        )
        self.completed_sets.append(completed)
        return completed

    def total_calories(self) -> float:
        """Running calorie total for this person (closed segments only)."""
        return self.calorie_engine.running_total()

    def total_reps(self) -> int:
        """Total reps across all completed sets."""
        return sum(s.reps for s in self.completed_sets)

    def to_summary_dict(self) -> dict:
        """Serialisable summary for the History/Sessions API endpoint."""
        return {
            "person_id": self.person_id,
            "display_name": self.display_name,
            "first_seen_at": self.first_seen_at,
            "last_seen_at": self.last_seen_at,
            "total_calories": round(self.total_calories(), 3),
            "total_reps": self.total_reps(),
            "sets": [
                {
                    "set_number": s.set_number,
                    "exercise": s.exercise,
                    "reps": s.reps,
                    "calories": s.calories,
                    "avg_form_score": s.avg_form_score,
                    "timestamp": s.timestamp,
                    "partial": s.partial,
                }
                for s in self.completed_sets
            ],
        }
