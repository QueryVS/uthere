from __future__ import annotations

import sqlite3
import os
from pathlib import Path
from typing import Any

from .config import get_setting


class DatabasePermissionError(RuntimeError):
    pass


SCHEMA = """
CREATE TABLE IF NOT EXISTS monitors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    target TEXT NOT NULL,
    check_type TEXT NOT NULL CHECK (check_type IN ('ping', 'http')),
    interval_seconds INTEGER NOT NULL DEFAULT 60,
    timeout_seconds REAL NOT NULL DEFAULT 5,
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    last_checked_at TEXT,
    last_status TEXT NOT NULL DEFAULT 'unknown',
    last_latency_ms REAL,
    last_status_code INTEGER,
    last_error TEXT
);

CREATE INDEX IF NOT EXISTS idx_monitors_due
ON monitors(enabled, last_checked_at);
"""


def default_db_path() -> Path:
    if os.geteuid() == 0:
        default = Path("/var/lib/uthere/uthere.db")
    else:
        default = Path.home() / ".local" / "state" / "uthere" / "uthere.db"
    return Path(get_setting("UTHERE_DB", str(default))).expanduser()


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    db_path = Path(path).expanduser() if path else default_db_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        conn.executescript(SCHEMA)
        migrate(conn)
    except sqlite3.OperationalError as exc:
        if "readonly" in str(exc).lower():
            raise DatabasePermissionError(f"SQLite database is read-only: {db_path}") from exc
        raise
    return conn


def row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


def migrate(conn: sqlite3.Connection) -> None:
    columns = {row["name"] for row in conn.execute("PRAGMA table_info(monitors)").fetchall()}
    if "description" not in columns:
        conn.execute("ALTER TABLE monitors ADD COLUMN description TEXT")
        conn.commit()
