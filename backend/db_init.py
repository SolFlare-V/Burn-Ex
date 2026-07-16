"""
Burn-Ex — Database initialisation script.

Run this once (or after wiping data/burnex.db) to create all 7 tables:
    users, sessions, sets, form_score_samples,
    calorie_segments, goals, streaks

Usage
-----
    python backend/db_init.py

The script is safe to re-run; SQLAlchemy uses CREATE TABLE IF NOT EXISTS
semantics via `checkfirst=True` (the default for create_all).
"""

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path so `backend.*` imports work whether
# this script is run as `python backend/db_init.py` from the project root
# or as `python db_init.py` from inside the backend/ directory.
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # backend/
_ROOT = _HERE.parent                              # project root
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from backend.database import Base, engine        # noqa: E402
import backend.models  # noqa: F401, E402 — side-effect: registers all models with Base.metadata


def init_db() -> None:
    print(f"Creating tables in: {engine.url}")
    Base.metadata.create_all(bind=engine)

    # Report created tables
    from sqlalchemy import inspect
    inspector = inspect(engine)
    tables = inspector.get_table_names()
    print(f"Tables present ({len(tables)}): {', '.join(sorted(tables))}")
    expected = {
        "users", "sessions", "sets", "form_score_samples",
        "calorie_segments", "goals", "streaks",
    }
    missing = expected - set(tables)
    if missing:
        print(f"WARNING — missing tables: {missing}", file=sys.stderr)
        sys.exit(1)
    print("✓ All 7 tables created successfully.")


if __name__ == "__main__":
    init_db()
