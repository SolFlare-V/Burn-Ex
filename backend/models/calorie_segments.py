"""
Burn-Ex — CalorieSegment SQLAlchemy model.

Each segment represents a continuous block of one exercise type within a session.
Calories are computed from the MET equation and stored on segment close.

Fields
------
id               : integer primary key
session_id       : FK → sessions.id
exercise         : exercise type string
weight_kg        : user weight at time of segment (float)
started_at       : UTC datetime segment started
ended_at         : UTC datetime segment ended (null while open)
calories         : float, computed on close (null while open)
duration_seconds : integer, computed on close (null while open)

Indexes
-------
ix_calorie_segments_session : (session_id)
"""

from sqlalchemy import Column, DateTime, Float, ForeignKey, Index, Integer, String

from backend.database import Base


class CalorieSegment(Base):
    __tablename__ = "calorie_segments"

    __table_args__ = (
        Index("ix_calorie_segments_session", "session_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(36), ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    exercise = Column(String(64), nullable=False)
    weight_kg = Column(Float, nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    calories = Column(Float, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<CalorieSegment id={self.id} session={self.session_id} "
            f"{self.exercise} cal={self.calories}>"
        )
