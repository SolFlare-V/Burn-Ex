"""
TASK-9.5 — Streak update logic.

Called on session completion to update the user's consecutive-day workout
streak stored in the ``streaks`` table.

Rules (Design ref §4.1, REQs: REQ-7.5, REQ-7.6):
  - date(now) - date(last_active) == 0 days  → same day, no change to current
  - date(now) - date(last_active) == 1 day   → increment current
  - date(now) - date(last_active)  > 1 day   → reset current to 1
  - If current > best, update best.
  - If no streak row exists yet, create one (current=1, best=1).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timezone
from typing import Optional

from backend.database import SessionLocal
from backend.models.streaks import Streak

logger = logging.getLogger(__name__)


def update_streak(user_id: int, completed_at: Optional[datetime] = None) -> Streak:
    """
    Update the streak record for *user_id* after a session is completed.

    Args:
        user_id:       ID of the user who completed the session.
        completed_at:  Datetime the session ended (defaults to now UTC).

    Returns:
        The updated (or newly created) Streak ORM row.
    """
    if completed_at is None:
        completed_at = datetime.now(timezone.utc)

    today: date = completed_at.date()

    db = SessionLocal()
    try:
        row = db.query(Streak).filter(Streak.user_id == user_id).first()

        if row is None:
            # First session ever for this user — create streak row
            row = Streak(
                user_id=user_id,
                current=1,
                best=1,
                last_active=today,
            )
            db.add(row)
            logger.info("Created streak for user %d: current=1 best=1", user_id)
        else:
            last: Optional[date] = row.last_active

            if last is None:
                delta = None
            else:
                delta = (today - last).days

            if delta is None or delta > 1:
                # Gap > 1 day (or no prior activity): reset
                row.current = 1
                logger.info(
                    "Streak reset for user %d (gap=%s days): current=1",
                    user_id, delta,
                )
            elif delta == 1:
                # Consecutive day: increment
                row.current += 1
                logger.info(
                    "Streak incremented for user %d: current=%d",
                    user_id, row.current,
                )
            else:
                # delta == 0: same day, no change
                logger.debug(
                    "Streak unchanged for user %d (same day): current=%d",
                    user_id, row.current,
                )

            # Update best if current exceeds it
            if row.current > row.best:
                row.best = row.current

            # Always update last_active to today
            row.last_active = today

        db.commit()
        db.refresh(row)
        result = row
    finally:
        db.close()

    return result
