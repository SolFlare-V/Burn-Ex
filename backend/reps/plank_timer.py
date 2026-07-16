"""
TASK-7.5 — Plank hold timer.

Design ref: §2.4
REQs: REQ-4.7

Tracks elapsed hold time for plank exercises.
Start timing when exercise confirmed as plank; stop on exercise change,
session pause, or end.

Exposes:
  start()           — begin timing (idempotent if already running)
  stop() → int      — stop timing, return total elapsed seconds (floor)
  elapsed() → int   — current elapsed seconds (even while running)
  is_running: bool  — True if the timer is currently active
  reset()           — stop and reset to zero
"""

from __future__ import annotations

import time


class PlankTimer:
    """Tracks the duration of a plank hold in whole seconds.

    Uses ``time.monotonic()`` for a clock that is immune to wall-clock
    adjustments and never goes backwards.

    Key behaviours
    --------------
    - ``start()`` is idempotent — calling it a second time while already
      running does **not** reset the accumulated time.
    - ``stop()`` returns the total elapsed seconds as an ``int`` (floor
      division).  Repeated calls after stopping return the same frozen value.
    - ``elapsed()`` returns the current elapsed seconds (updating in real
      time while running, frozen after ``stop()``).
    - After ``stop()``, ``elapsed()`` still returns the final stopped value.
    - ``reset()`` stops the timer if running and clears all state to zero.
    """

    def __init__(self) -> None:
        self._start_time: float | None = None  # monotonic timestamp when started
        self._stopped_elapsed: int | None = None  # frozen value after stop()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self) -> None:
        """Begin timing.

        Idempotent — if the timer is already running this call is a no-op,
        preserving the current accumulated time.
        """
        if self._start_time is not None:
            # Already running; ignore duplicate start.
            return
        if self._stopped_elapsed is not None:
            # Timer was stopped previously; continue from the frozen value
            # by back-dating the start time so elapsed() remains consistent.
            self._start_time = time.monotonic() - float(self._stopped_elapsed)
            self._stopped_elapsed = None
        else:
            self._start_time = time.monotonic()

    def stop(self) -> int:
        """Stop timing and return elapsed hold duration in whole seconds.

        Returns
        -------
        int
            Total elapsed seconds (floor).  Returns 0 if never started.
            Idempotent — repeated calls after stopping return the same value.
        """
        if self._stopped_elapsed is not None:
            # Already stopped; return the frozen value.
            return self._stopped_elapsed

        if self._start_time is None:
            # Never started.
            return 0

        elapsed = int(time.monotonic() - self._start_time)
        self._stopped_elapsed = elapsed
        self._start_time = None
        return elapsed

    def elapsed(self) -> int:
        """Return current elapsed seconds as ``int``.

        Returns 0 if the timer has never been started.
        Returns the frozen value if the timer has been stopped.
        Returns live elapsed seconds if the timer is currently running.
        """
        if self._stopped_elapsed is not None:
            return self._stopped_elapsed

        if self._start_time is None:
            return 0

        return int(time.monotonic() - self._start_time)

    @property
    def is_running(self) -> bool:
        """``True`` if the timer is currently running (started but not stopped)."""
        return self._start_time is not None

    def reset(self) -> None:
        """Stop the timer (if running) and reset all state to zero.

        After calling ``reset()``:
        - ``elapsed()`` returns 0
        - ``is_running`` is False
        - ``stop()`` returns 0
        """
        self._start_time = None
        self._stopped_elapsed = None
