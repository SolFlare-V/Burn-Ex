"""
Burn-Ex — SQLAlchemy database setup.

Provides:
  engine        — SQLite engine pointing to data/burnex.db (absolute path)
  SessionLocal  — sessionmaker factory for creating DB sessions
  Base          — declarative base for all ORM models
  get_db()      — FastAPI dependency that yields a session and closes it on exit
"""

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------
# __file__ is backend/database.py; project root is one level up.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DB_PATH = _PROJECT_ROOT / "data" / "burnex.db"

# Ensure the data/ directory exists (it should from TASK-1.1, but be safe).
_DB_PATH.parent.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Engine
# ---------------------------------------------------------------------------
DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},  # required for SQLite + FastAPI
)

# ---------------------------------------------------------------------------
# Session factory
# ---------------------------------------------------------------------------
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# ---------------------------------------------------------------------------
# Declarative base (all models inherit from this)
# ---------------------------------------------------------------------------
Base = declarative_base()


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------
def get_db():
    """Yield a database session, closing it when the request finishes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
