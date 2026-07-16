"""
Burn-Ex — ORM model registry.

Import all model modules here so that SQLAlchemy's metadata knows about
every table before `Base.metadata.create_all(engine)` is called.
"""

from backend.models.users import User  # noqa: F401
from backend.models.sessions import Session  # noqa: F401
from backend.models.sets import Set  # noqa: F401
from backend.models.form_score_samples import FormScoreSample  # noqa: F401
from backend.models.calorie_segments import CalorieSegment  # noqa: F401
from backend.models.goals import Goal  # noqa: F401
from backend.models.streaks import Streak  # noqa: F401

__all__ = [
    "User",
    "Session",
    "Set",
    "FormScoreSample",
    "CalorieSegment",
    "Goal",
    "Streak",
]
