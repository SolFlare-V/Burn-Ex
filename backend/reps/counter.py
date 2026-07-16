"""
TASK-7.6 — Rep counter assembly module.

Design ref: §2.4
REQs: REQ-4.1–REQ-4.7

Assembles PlankTimer, PauseTimer, SetTracker, and RepStateMachine into a
single update_rep_state() call that drives all rep-counting logic.

Routes plank exercise to PlankTimer (hold-duration tracking, REQ-4.7).
All other exercises use the RepStateMachine phase state machine (REQ-4.1–REQ-4.3),
PauseTimer (auto set-closing on inactivity, REQ-4.4), and SetTracker (set
management, REQ-4.5, REQ-4.6).

Returns RepState(rep_count, set_number, sets_closed, hold_seconds).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import yaml

from backend.reps.pause_timer import PauseTimer
from backend.reps.plank_timer import PlankTimer
from backend.reps.set_tracker import ClosedSet, SetTracker
from backend.reps.state_machine import RepStateMachine


# ---------------------------------------------------------------------------
# Public data class returned by update_rep_state
# ---------------------------------------------------------------------------


@dataclass
class RepState:
    """Snapshot of current rep-counting state returned after each frame update.

    Attributes:
        rep_count:    Reps counted in the current (open) set.
        set_number:   1-based number of the currently open set.
        sets_closed:  All closed sets recorded so far this session.
        hold_seconds: Elapsed plank hold seconds (0 for non-plank exercises).
    """

    rep_count: int = 0
    set_number: int = 1
    sets_closed: list[ClosedSet] = field(default_factory=list)
    hold_seconds: int = 0


# ---------------------------------------------------------------------------
# Config path — mirrors RepStateMachine._CONFIG_PATH
# ---------------------------------------------------------------------------

_CONFIG_PATH = Path(__file__).resolve().parent.parent.parent / "config" / "rep_phases.yaml"


def _load_primary_angle(exercise_type: str) -> str:
    """Return the primary_angle key for *exercise_type* from rep_phases.yaml.

    Raises:
        FileNotFoundError: if the config file is missing.
        KeyError: if exercise_type is not present.
    """
    if not _CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"Rep phases config not found at {_CONFIG_PATH}"
        )
    with open(_CONFIG_PATH, "r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if exercise_type not in data:
        raise KeyError(
            f"Exercise type '{exercise_type}' not found in rep_phases.yaml. "
            f"Available: {list(data.keys())}"
        )
    return data[exercise_type]["primary_angle"]


# ---------------------------------------------------------------------------
# RepCounter
# ---------------------------------------------------------------------------


class RepCounter:
    """Drives rep counting for all supported exercise types.

    Maintains internal state across frames:
      - SetTracker     — tracks set number, rep count, closed sets.
      - PlankTimer     — wall-clock hold timer for plank.
      - PauseTimer     — detects inactivity → auto-close set (REQ-4.4).
      - RepStateMachine — phase state machine for non-plank reps (REQ-4.1–4.3).

    Call ``update_rep_state(angle_map, confirmed_type, elapsed_seconds)`` once
    per processed frame to advance state and receive the current RepState.
    """

    _PLANK = "plank"

    def __init__(self) -> None:
        self._set_tracker = SetTracker()
        self._plank_timer = PlankTimer()
        self._pause_timer = PauseTimer()
        self._state_machine: Optional[RepStateMachine] = None
        self._last_confirmed_type: Optional[str] = None

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def update_rep_state(
        self,
        angle_map: dict[str, float],
        confirmed_type: Optional[str],
        elapsed_seconds: float,
    ) -> RepState:
        """Update rep-counting state for one processed frame.

        Args:
            angle_map:       Joint angle map keyed by angle name (e.g.
                             ``{"left_knee": 85.0, ...}``).
            confirmed_type:  The currently confirmed exercise type string, or
                             ``None`` if no exercise is confirmed this frame.
            elapsed_seconds: Wall-clock seconds elapsed since the previous
                             frame (used by PauseTimer).

        Returns:
            Current :class:`RepState` snapshot.
        """
        # ------------------------------------------------------------------
        # 1. No confirmed exercise — return unchanged state immediately.
        # ------------------------------------------------------------------
        if confirmed_type is None:
            return self._current_state()

        # ------------------------------------------------------------------
        # 2. Exercise type changed since last confirmed frame.
        # ------------------------------------------------------------------
        if confirmed_type != self._last_confirmed_type:
            self._handle_exercise_change(confirmed_type)

        # ------------------------------------------------------------------
        # 3. Plank path — accumulate hold time; skip state machine.
        # ------------------------------------------------------------------
        if confirmed_type == self._PLANK:
            # PlankTimer is already running (started in _handle_exercise_change
            # when entering plank, or was already running).
            return self._current_state()

        # ------------------------------------------------------------------
        # 4. Non-plank path — drive state machine + pause timer.
        # ------------------------------------------------------------------
        primary_angle = _load_primary_angle(confirmed_type)
        angle = angle_map.get(primary_angle, 0.0)

        # State machine update — may count a rep.
        if self._state_machine is not None:
            rep_counted = self._state_machine.update(angle)
            if rep_counted:
                self._set_tracker.count_rep()

        # Pause timer update — may auto-close the set.
        close_set = self._pause_timer.tick(angle, elapsed_seconds)
        if close_set:
            self._set_tracker.close_set(0.0)
            self._pause_timer.reset()

        return self._current_state()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _handle_exercise_change(self, new_type: str) -> None:
        """Handle a transition to a new confirmed exercise type.

        Closes current set if reps > 0 (via SetTracker.exercise_changed,
        REQ-4.5).  Stops/starts PlankTimer as appropriate (REQ-4.7).
        Creates a fresh RepStateMachine for the new exercise if not plank.
        Resets PauseTimer.
        """
        old_type = self._last_confirmed_type

        # Close set on exercise change (REQ-4.5) — only when reps exist.
        self._set_tracker.exercise_changed()

        # Plank timer lifecycle.
        if old_type == self._PLANK:
            self._plank_timer.stop()

        if new_type == self._PLANK:
            self._plank_timer.start()
        else:
            # New non-plank exercise: create a fresh state machine.
            self._state_machine = RepStateMachine(new_type)

        # Reset pause timer for the new exercise.
        self._pause_timer.reset()

        # Persist new type.
        self._last_confirmed_type = new_type

    def _current_state(self) -> RepState:
        """Assemble and return a RepState snapshot from current tracker state."""
        return RepState(
            rep_count=self._set_tracker.current_rep_count,
            set_number=self._set_tracker.current_set_number,
            sets_closed=self._set_tracker.closed_sets,
            hold_seconds=self._plank_timer.elapsed(),
        )
