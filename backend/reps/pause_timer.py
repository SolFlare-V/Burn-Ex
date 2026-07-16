"""
TASK-7.3 — Pause timer for auto set-closing on inactivity.

Design ref: §2.4
REQs: REQ-4.4

Tracks time since last angle movement above a threshold.
Returns True ONCE when stationary duration exceeds 8 seconds.
Resets automatically when movement is detected.
"""

from __future__ import annotations


class PauseTimer:
    """
    Tracks inactivity (no angle movement above MOVEMENT_THRESHOLD) and signals
    when the user has been stationary for at least PAUSE_THRESHOLD seconds.

    One-shot semantics: once True is returned for a pause event, subsequent
    ticks return False until reset() is called explicitly or movement is
    detected (which also calls reset internally).

    Usage::

        timer = PauseTimer()
        for angle, dt in frame_stream:
            should_close = timer.tick(angle, dt)
            if should_close:
                set_tracker.close_set(...)
    """

    MOVEMENT_THRESHOLD: float = 2.0  # degrees — at or below this is treated as stationary
    PAUSE_THRESHOLD: float = 8.0     # seconds — must *exceed* this to fire the one-shot

    def __init__(self) -> None:
        self._last_angle: float | None = None
        self._stationary_seconds: float = 0.0
        self._fired: bool = False

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def tick(self, angle: float, elapsed_seconds: float) -> bool:
        """
        Update the timer with the current primary-joint angle and the time
        elapsed since the previous tick.

        Args:
            angle: Current joint angle in degrees.
            elapsed_seconds: Wall-clock seconds elapsed since the last tick.

        Returns:
            True exactly once when the cumulative stationary duration first
            crosses PAUSE_THRESHOLD.  Returns False on every other call,
            including calls after the threshold was already signalled (until
            reset() is invoked).
        """
        # First call — record starting angle and begin accumulation.
        if self._last_angle is None:
            self._last_angle = angle
            self._stationary_seconds += elapsed_seconds
            return False

        movement = abs(angle - self._last_angle)

        if movement > self.MOVEMENT_THRESHOLD:
            # Movement detected — reset everything and start fresh.
            self.reset()
            self._last_angle = angle
            return False

        # Stationary tick — update the tracked angle and accumulate time.
        self._last_angle = angle
        self._stationary_seconds += elapsed_seconds

        # One-shot: if already fired, keep returning False until reset().
        if self._fired:
            return False

        if self._stationary_seconds > self.PAUSE_THRESHOLD:
            self._fired = True
            return True

        return False

    def reset(self) -> None:
        """
        Clear accumulated stationary time, last angle, and the fired flag.
        Call this after acting on a True return value, or when a new set starts.
        """
        self._stationary_seconds = 0.0
        self._fired = False
        self._last_angle = None

    # ------------------------------------------------------------------
    # Read-only property
    # ------------------------------------------------------------------

    @property
    def stationary_seconds(self) -> float:
        """Total accumulated stationary duration in seconds."""
        return self._stationary_seconds
