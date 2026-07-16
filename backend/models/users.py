"""
Burn-Ex — User SQLAlchemy model.

Fields
------
id          : integer primary key (auto-increment)
name        : optional display name (nullable)
weight_kg   : float, CHECK(weight_kg BETWEEN 20 AND 300)
created_at  : UTC datetime, defaults to now
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, Float, Integer, String

from backend.database import Base


class User(Base):
    __tablename__ = "users"

    __table_args__ = (
        CheckConstraint("weight_kg >= 20 AND weight_kg <= 300", name="ck_users_weight_range"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(120), nullable=True)
    weight_kg = Column(Float, nullable=False)
    created_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<User id={self.id} name={self.name!r} weight_kg={self.weight_kg}>"
