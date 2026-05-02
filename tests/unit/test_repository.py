from __future__ import annotations

from datetime import UTC, datetime, timedelta

from uthere.db import connect
from uthere.repository import (
    add_monitor,
    due_monitors,
    get_monitor,
    record_result,
    seconds_until_next_due,
    update_monitor,
    set_description,
)


def test_add_and_due_monitor(tmp_path):
    conn = connect(tmp_path / "uthere.db")

    monitor_id = add_monitor(
        conn,
        target="example.com",
        check_type="ping",
        name="example",
        interval_seconds=60,
        timeout_seconds=2,
    )

    monitor = get_monitor(conn, monitor_id)
    assert monitor is not None
    assert monitor["target"] == "example.com"
    assert monitor["description"] is None
    assert due_monitors(conn)[0]["id"] == monitor_id
    assert seconds_until_next_due(conn) == 0


def test_set_description(tmp_path):
    conn = connect(tmp_path / "uthere.db")
    monitor_id = add_monitor(
        conn,
        target="example.com",
        check_type="ping",
        name="example",
        interval_seconds=60,
        timeout_seconds=2,
    )

    assert set_description(conn, monitor_id, "edge server") is True
    assert get_monitor(conn, monitor_id)["description"] == "edge server"


def test_seconds_until_next_due_uses_last_checked_at(tmp_path):
    conn = connect(tmp_path / "uthere.db")
    monitor_id = add_monitor(
        conn,
        target="https://example.com",
        check_type="http",
        name=None,
        interval_seconds=60,
        timeout_seconds=2,
    )
    record_result(conn, monitor_id, healthy=True, latency_ms=10, status_code=200, error=None)

    wait = seconds_until_next_due(conn)

    assert wait is not None
    assert 0 < wait <= 60
    assert due_monitors(conn) == []


def test_update_to_old_last_check_becomes_due(tmp_path):
    conn = connect(tmp_path / "uthere.db")
    monitor_id = add_monitor(
        conn,
        target="https://example.com",
        check_type="http",
        name=None,
        interval_seconds=60,
        timeout_seconds=2,
    )
    old_time = datetime.now(UTC) - timedelta(seconds=120)
    update_monitor(conn, monitor_id, {"last_checked_at": old_time.replace(microsecond=0).isoformat()})

    assert due_monitors(conn)[0]["id"] == monitor_id
