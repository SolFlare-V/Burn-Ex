"""
Burn-Ex — Session SQLAlchemy model.

Fields
------
id              : UUID stored as TEXT, primary key
user_id         : FK → users.id
started_at      : UTC datetime
ended_at        : UTC datetime, nullable (null while active)
status          : CHECK('active','completed','interrupted')
total_reps      : integer, default 0
total_calories  : float, default 0.0
avg_form_score  : float, nullable
duration_seconds: integer, nullable (filled on session end)

Indexes
-------
ix_sessions_user_started  : (user_id, started_at DESC) for history queries
"""

from datetime import datetime, timezone

from sqlalchemy import (
    CheckConstraint,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
)

from backend.database import Base


class Session(Base):
    __tablename__ = "sessions"

    __table_args__ = (
        CheckConstraint(
            "status IN ('active', 'completed', 'interrupted')",
            name="ck_sessions_status",
        ),
        Index("ix_sessions_user_started", "user_id", "started_at"),
    )

    id = Column(String(36), primary_key=True)          # UUID as TEXT
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    ended_at = Column(DateTime, nullable=True)
    status = Column(String(16), nullable=False, default="active")
    total_reps = Column(Integer, nullable=False, default=0)
    total_calories = Column(Float, nullable=False, default=0.0)
    avg_form_score = Column(Float, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<Session id={self.id} status={self.status!r} reps={self.total_reps}>"
