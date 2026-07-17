"""
Burn-Ex — User SQLAlchemy model.

Fields
------
id           : integer primary key (auto-increment)
name         : optional display name (nullable)
weight_kg    : float, CHECK(weight_kg BETWEEN 20 AND 300)
height_cm    : optional float, CHECK(height_cm BETWEEN 50 AND 300), nullable
fitness_goal : optional string — one of: 'lose_weight', 'build_muscle',
               'get_toned', 'stay_fit', 'improve_endurance'
created_at   : UTC datetime, defaults to now
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Integer, String

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("weight_kg >= 20 AND weight_kg <= 300", name="ck_users_weight_range"),
        CheckConstraint(
            "height_cm IS NULL OR (height_cm >= 50 AND height_cm <= 300)",
            name="ck_users_height_range",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=True)
    weight_kg = Column(Float, nullable=False)
    height_cm = Column(Float, nullable=True)
    fitness_goal = Column(String(32), nullable=True)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} name={self.name!r} weight_kg={self.weight_kg}>"
