"""
Burn-Ex — FormScoreSample SQLAlchemy model.

Per-frame form score snapshots stored during a set.
Used to build trend lines and per-set averages.

Fields
------
id         : integer primary key
set_id     : FK → sets.id
score      : integer, CHECK(score BETWEEN 0 AND 100)
sampled_at : UTC datetime of the frame

Indexes
-------
ix_form_score_set : (set_id)
"""

from datetime import datetime, timezone

from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Index, Integer

from backend.database import Base


class FormScoreSample(Base):
    __tablename__ = "form_score_samples"

    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 100", name="ck_form_score_range"),
        Index("ix_form_score_set", "set_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    set_id = Column(Integer, ForeignKey("sets.id", ondelete="CASCADE"), nullable=False)
    score = Column(Integer, nullable=False)
    sampled_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:  # pragma: no cover
        return f"<FormScoreSample id={self.id} set_id={self.set_id} score={self.score}>"
