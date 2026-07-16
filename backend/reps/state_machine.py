"""
TASK-7.2 — Per-exercise phase state machine for rep counting.

Design ref: §2.4
REQs: REQ-4.1, REQ-4.2, REQ-4.3

State machine:

    NEUTRAL  →  ECCENTRIC   when primary angle crosses eccentric_threshold
    ECCENTRIC → CONCENTRIC  when angle reaches depth_threshold (full depth)
    ECCENTRIC → NEUTRAL     if angle returns to return_threshold (partial rep — NOT counted)
    CONCENTRIC → NEUTRAL    when angle returns to return_threshold → REP COUNTED

Direction handling:
  - "decreasing" exercises (squat, push_up, lunge, shoulder_press):
        eccentric_threshold > depth_threshold
        NEUTRAL → ECCENTRIC: angle < eccentric_threshold
        ECCENTRIC → CONCENTRIC: angle < depth_threshold
        ECCENTRIC/CONCENTRIC → NEUTRAL: angle > return_threshold

  - "increasing" exercises (bicep_curl):
        depth_threshold > eccentric_threshold
        NEUTRAL → ECCENTRIC: angle > eccentric_threshold
        ECCENTRIC → CONCENTRIC: angle > depth_threshold
        ECCENTRIC/CONCENTRIC → NEUTRAL: angle < return_threshold
"""

from __future__ import annotations

import os
from enum import Enum
from pathlib import Path
from typing import Optional

import yaml


class Phase(Enum):
    NEUTRAL = "neutral"
    ECCENTRIC = "eccentric"
    CONCENTRIC = "concentric"


class RepStateMachine:
    """
    Phase-based state machine that counts full reps for a given exercise type.

    Partial reps (eccentric phase entered but depth never reached) are silently
    discarded — no rep is counted on return to NEUTRAL from ECCENTRIC.
    """

    _CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "rep_phases.yaml"

    def __init__(self, exercise_type: str) -> None:
        """
        Load phase thresholds for *exercise_type* from ``config/rep_phases.yaml``.

        Raises:
            KeyError: if exercise_type is not found in the config.
            FileNotFoundError: if the config file cannot be located.
        """
        self._exercise_type = exercise_type
        config = self._load_config(exercise_type)

        self._eccentric_threshold: float = float(config["eccentric_threshold"])
        self._depth_threshold: float = float(config["depth_threshold"])
        self._return_threshold: float = float(config["return_threshold"])

        # Direction: if eccentric_threshold > depth_threshold the angle must
        # DECREASE to go eccentric (squat, push_up, lunge, shoulder_press).
        # Otherwise (bicep_curl) the angle must INCREASE.
        self._decreasing: bool = self._eccentric_threshold > self._depth_threshold

        self._phase: Phase = Phase.NEUTRAL
        self._rep_count: int = 0

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    @property
    def rep_count(self) -> int:
        """Total completed reps since construction (or last reset)."""
        return self._rep_count

    @property
    def phase(self) -> Phase:
        """Current phase of the state machine (read-only)."""
        return self._phase

    def update(self, angle: float) -> bool:
        """
        Feed the current primary-joint angle to the state machine.

        Returns:
            ``True`` if this update completed a full rep (CONCENTRIC → NEUTRAL
            transition), ``False`` otherwise.
        """
        rep_counted = False

        if self._phase is Phase.NEUTRAL:
            if self._entered_eccentric(angle):
                self._phase = Phase.ECCENTRIC

        elif self._phase is Phase.ECCENTRIC:
            if self._reached_depth(angle):
                self._phase = Phase.CONCENTRIC
            elif self._returned_to_neutral(angle):
                # Partial rep — abandon without counting
                self._phase = Phase.NEUTRAL

        elif self._phase is Phase.CONCENTRIC:
            if self._returned_to_neutral(angle):
                # Full rep completed
                self._phase = Phase.NEUTRAL
                self._rep_count += 1
                rep_counted = True

        return rep_counted

    def reset(self) -> None:
        """Reset the state machine to NEUTRAL and clear the rep count."""
        self._phase = Phase.NEUTRAL
        self._rep_count = 0

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _entered_eccentric(self, angle: float) -> bool:
        """True when the angle has crossed the eccentric threshold from neutral."""
        if self._decreasing:
            return angle < self._eccentric_threshold
        else:
            return angle > self._eccentric_threshold

    def _reached_depth(self, angle: float) -> bool:
        """True when full depth is reached (ECCENTRIC → CONCENTRIC transition)."""
        if self._decreasing:
            return angle < self._depth_threshold
        else:
            return angle > self._depth_threshold

    def _returned_to_neutral(self, angle: float) -> bool:
        """True when the angle has returned to the neutral/start range."""
        if self._decreasing:
            return angle > self._return_threshold
        else:
            return angle < self._return_threshold

    # ------------------------------------------------------------------
    # Config loading
    # ------------------------------------------------------------------

    @classmethod
    def _load_config(cls, exercise_type: str) -> dict:
        config_path = cls._CONFIG_PATH
        if not config_path.exists():
            raise FileNotFoundError(
                f"Rep phases config not found at {config_path}"
            )
        with open(config_path, "r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh)

        if exercise_type not in data:
            raise KeyError(
                f"Exercise type '{exercise_type}' not found in {config_path}. "
                f"Available exercises: {list(data.keys())}"
            )
        return data[exercise_type]
