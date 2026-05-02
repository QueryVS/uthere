from __future__ import annotations

import sqlite3
from datetime import UTC, datetime, timedelta
from typing import Any

from .db import row_to_dict


def now_iso() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def add_monitor(
    conn: sqlite3.Connection,
    *,
    target: str,
    check_type: str,
    name: str | None,
    interval_seconds: int,
    timeout_seconds: float,
) -> int:
    now = now_iso()
    cur = conn.execute(
        """
        INSERT INTO monitors (
            name, target, check_type, interval_seconds, timeout_seconds,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (name, target, check_type, interval_seconds, timeout_seconds, now, now),
    )
    conn.commit()
    return int(cur.lastrowid)


def get_monitor(conn: sqlite3.Connection, monitor_id: int) -> dict[str, Any] | None:
    return row_to_dict(conn.execute("SELECT * FROM monitors WHERE id = ?", (monitor_id,)).fetchone())


def list_monitors(conn: sqlite3.Connection, *, include_disabled: bool = False) -> list[dict[str, Any]]:
    sql = "SELECT * FROM monitors"
    params: tuple[Any, ...] = ()
    if not include_disabled:
        sql += " WHERE enabled = 1"
    sql += " ORDER BY id"
    return [dict(row) for row in conn.execute(sql, params).fetchall()]


def delete_monitor(conn: sqlite3.Connection, monitor_id: int) -> bool:
    cur = conn.execute("DELETE FROM monitors WHERE id = ?", (monitor_id,))
    conn.commit()
    return cur.rowcount > 0


def update_monitor(conn: sqlite3.Connection, monitor_id: int, fields: dict[str, Any]) -> bool:
    if not fields:
        return False
    fields["updated_at"] = now_iso()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    params = tuple(fields.values()) + (monitor_id,)
    cur = conn.execute(f"UPDATE monitors SET {assignments} WHERE id = ?", params)
    conn.commit()
    return cur.rowcount > 0


def set_description(conn: sqlite3.Connection, monitor_id: int, description: str) -> bool:
    return update_monitor(conn, monitor_id, {"description": description})


def clear_description(conn: sqlite3.Connection, monitor_id: int) -> bool:
    return update_monitor(conn, monitor_id, {"description": None})


def due_monitors(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    rows = conn.execute(
        """
        SELECT *
        FROM monitors
        WHERE enabled = 1
          AND (
            last_checked_at IS NULL
            OR unixepoch(?) - unixepoch(last_checked_at) >= interval_seconds
          )
        ORDER BY COALESCE(last_checked_at, ''), id
        """,
        (now_iso(),),
    ).fetchall()
    return [dict(row) for row in rows]


def seconds_until_next_due(conn: sqlite3.Connection) -> float | None:
    rows = conn.execute(
        """
        SELECT last_checked_at, interval_seconds
        FROM monitors
        WHERE enabled = 1
        """
    ).fetchall()
    if not rows:
        return None

    now = datetime.now(UTC)
    waits: list[float] = []
    for row in rows:
        if row["last_checked_at"] is None:
            return 0
        last_checked_at = datetime.fromisoformat(row["last_checked_at"])
        next_due_at = last_checked_at + timedelta(seconds=int(row["interval_seconds"]))
        waits.append((next_due_at - now).total_seconds())
    return max(0, min(waits))


def record_result(
    conn: sqlite3.Connection,
    monitor_id: int,
    *,
    healthy: bool,
    latency_ms: float,
    status_code: int | None,
    error: str | None,
) -> None:
    status = "healthy" if healthy else "unhealthy"
    conn.execute(
        """
        UPDATE monitors
        SET last_checked_at = ?,
            last_status = ?,
            last_latency_ms = ?,
            last_status_code = ?,
            last_error = ?,
            updated_at = ?
        WHERE id = ?
        """,
        (now_iso(), status, round(latency_ms, 2), status_code, error, now_iso(), monitor_id),
    )
    conn.commit()
