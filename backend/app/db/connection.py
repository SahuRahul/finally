"""SQLite connection helper and lazy initialization."""

from __future__ import annotations

import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_USER_ID = "default"
DEFAULT_CASH = 10000.0
DEFAULT_WATCHLIST = [
    "AAPL", "GOOGL", "MSFT", "AMZN", "TSLA",
    "NVDA", "META", "JPM", "V", "NFLX",
]

# backend/app/db/connection.py -> project root is three parents up from app/db
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_SCHEMA_PATH = Path(__file__).resolve().parents[2] / "db" / "schema.sql"


def _db_path() -> Path:
    """Resolve the SQLite file path, honoring FINALLY_DB_PATH override."""
    override = os.environ.get("FINALLY_DB_PATH", "").strip()
    if override:
        return Path(override)
    return _PROJECT_ROOT / "db" / "finally.db"


def now_iso() -> str:
    """Current UTC time as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    """Generate a new UUID primary key."""
    return str(uuid.uuid4())


def get_connection() -> sqlite3.Connection:
    """Open a connection to the database, initializing it on first use.

    Returns a connection with Row factory so rows behave like dicts.
    """
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _initialize(conn)
    return conn


def init_db() -> None:
    """Explicitly initialize and seed the database. Safe to call repeatedly.

    Provided for use in the FastAPI lifespan startup; init also happens
    automatically on the first get_connection() call.
    """
    get_connection().close()


def _initialize(conn: sqlite3.Connection) -> None:
    """Create tables and seed default data if not already present."""
    conn.executescript(_SCHEMA_PATH.read_text())
    _seed(conn)
    conn.commit()


def _seed(conn: sqlite3.Connection) -> None:
    """Insert default user profile and watchlist if the profile is missing."""
    exists = conn.execute(
        "SELECT 1 FROM users_profile WHERE id = ?", (DEFAULT_USER_ID,)
    ).fetchone()
    if exists:
        return

    conn.execute(
        "INSERT INTO users_profile (id, cash_balance, created_at) VALUES (?, ?, ?)",
        (DEFAULT_USER_ID, DEFAULT_CASH, now_iso()),
    )
    for ticker in DEFAULT_WATCHLIST:
        conn.execute(
            "INSERT INTO watchlist (id, user_id, ticker, added_at) VALUES (?, ?, ?, ?)",
            (new_id(), DEFAULT_USER_ID, ticker, now_iso()),
        )
