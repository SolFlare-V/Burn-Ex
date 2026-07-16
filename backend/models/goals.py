"""
Burn-Ex — Goal SQLAlchemy model.

Users can set daily or weekly calorie burn targets.

Fields
------
id               : integer primary key
user_id          : FK → users.id
type             : CHECK('daily','weekly')
target_calories  : float, target to hit
created_at       : UTC datetime
active           : boolean, whether this goal is currently active
"""

from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Float, ForeignKey, Integer, String

from backend.database import Base


class Goal(Base):
    __tablename__ = "goals"

    __table_args__ = (
        CheckConstraint("type IN ('daily', 'weekly')", name="ck_goals_type"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String(8), nullable=False)
    target_calories = Column(Float, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    active = Column(Boolean, nullable=False, default=True)

    def __repr__(self) -> str:  # pragma: no cover
        return (
            f"<Goal id={self.id} user={self.user_id} "
            f"type={self.type!r} target={self.target_calories} active={self.active}>"
        )
