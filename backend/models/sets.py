"""
Burn-Ex — Set SQLAlchemy model.

A "set" is one bout of continuous exercise within a session (e.g. 10 squats).
For plank, reps = 0 and hold_seconds is populated instead.

Fields
------
id            : integer primary key
session_id    : FK → sessions.id
set_number    : ordinal within the session (1-based)
exercise      : exercise type string (e.g. "squat")
reps          : integer count, default 0
hold_seconds  : integer (plank hold duration), nullable
avg_form_score: float, nullable
closed_at     : UTC datetime when set was closed, nullable

Indexes
-------
ix_sets_session_set : (session_id, set_number)
"""

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)

from backend.database import Base


class Set(Base):
    __tablename__ = "sets"

    __table_args__ = (
        Index("ix_sets_session_set", "session_id", "set_number"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    set_number = Column(Integer, nullable=False)
    exercise = Column(String(64), nullable=False)
    reps = Column(Integer, nullable=False, default=0)
    hold_seconds = Column(Integer, nullable=True)       # plank only
    avg_form_score = Column(Float, nullable=True)
    closed_at = Column(DateTime, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Set id={self.id} session={self.session_id} "
            f"set#{self.set_number} {self.exercise} reps={self.reps}>"
        )
