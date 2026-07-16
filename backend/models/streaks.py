"""
Burn-Ex — Streak SQLAlchemy model.

One row per user. Tracks consecutive-day workout streaks.

Fields
------
id          : integer primary key
user_id     : FK → users.id, UNIQUE (one streak record per user)
current     : current streak length in days
best        : all-time best streak
last_active : date of last completed session used in streak calculation
"""

from sqlalchemy import Column, Date, ForeignKey, Integer, UniqueConstraint

from backend.database import Base


class Streak(Base):
    __tablename__ = "streaks"

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_streaks_user"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    current = Column(Integer, nullable=False, default=0)
    best = Column(Integer, nullable=False, default=0)
    last_active = Column(Date, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Streak id={self.id} user={self.user_id} "
            f"current={self.current} best={self.best} last={self.last_active}>"
        )
