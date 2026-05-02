from __future__ import annotations

import argparse
import os
import signal
import sqlite3
import sys
from typing import Any

from .alerts import AlertConfig, format_alert_message, send_alerts, should_alert
from .checks import run_check
from .db import DatabasePermissionError, connect, default_db_path
from .repository import (
    add_monitor,
    clear_description,
    delete_monitor,
    due_monitors,
    get_monitor,
    list_monitors,
    record_result,
    seconds_until_next_due,
    set_description,
    update_monitor,
)
from .wakeup import WakeServer, default_socket_path, notify


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be greater than 0")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="uthere", description="Ping/http health check CLI and service.")
    parser.add_argument("--db", default=str(default_db_path()), help="SQLite database path")
    parser.add_argument("--socket", default=default_socket_path(), help="Service wake socket path")
    sub = parser.add_subparsers(dest="command", required=True)

    add = sub.add_parser("add", help="Add a new monitor record")
    add.add_argument("target", help="IP, domain, or URL")
    add.add_argument("--type", choices=("ping", "http"), required=True, dest="check_type")
    add.add_argument("--name", help="Display name")
    add.add_argument("--interval", type=positive_int, default=60, help="Check interval in seconds")
    add.add_argument("--timeout", type=positive_float, default=5.0, help="Request timeout in seconds")
    add.set_defaults(func=cmd_add)

    list_cmd = sub.add_parser("list", help="List records and their latest status")
    list_cmd.add_argument("--all", action="store_true", help="Include disabled records")
    list_cmd.set_defaults(func=cmd_list)

    remove = sub.add_parser("remove", aliases=["rm"], help="Remove one or more records")
    remove.add_argument("ids", type=int, nargs="+", metavar="id")
    remove.set_defaults(func=cmd_remove)

    edit = sub.add_parser("edit", help="Edit a record")
    edit.add_argument("id", type=int)
    edit.add_argument("--target")
    edit.add_argument("--type", choices=("ping", "http"), dest="check_type")
    edit.add_argument("--name")
    edit.add_argument("--interval", type=positive_int)
    edit.add_argument("--timeout", type=positive_float)
    state = edit.add_mutually_exclusive_group()
    state.add_argument("--enable", action="store_true")
    state.add_argument("--disable", action="store_true")
    edit.set_defaults(func=cmd_edit)

    description = sub.add_parser("description", aliases=["des"], help="Manage record descriptions")
    description_sub = description.add_subparsers(dest="description_command", required=True)

    description_add = description_sub.add_parser("add", help="Add or replace a record description")
    description_add.add_argument("id", type=int)
    description_add.add_argument("description")
    description_add.set_defaults(func=cmd_description_add)

    description_show = description_sub.add_parser("show", help="Show one description or all descriptions")
    description_show.add_argument("id", metavar="id|all")
    description_show.set_defaults(func=cmd_description_show)

    description_clear = description_sub.add_parser("clear", aliases=["rm"], help="Clear a record description")
    description_clear.add_argument("id", type=int)
    description_clear.set_defaults(func=cmd_description_clear)

    check = sub.add_parser("check", help="Run checks immediately")
    check.add_argument("targets", nargs="*", metavar="id|all", help="Record IDs, or all")
    check.set_defaults(func=cmd_check)

    alert_test = sub.add_parser("alert-test", help="Send a test message to configured alert channels")
    alert_test.set_defaults(func=cmd_alert_test)

    serve = sub.add_parser("serve", help="Start the service loop")
    serve.add_argument("--max-sleep", type=positive_float, default=3600.0, help="Maximum sleep duration in seconds")
    serve.set_defaults(func=cmd_serve)

    return parser


def cmd_add(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        monitor_id = add_monitor(
            conn,
            target=args.target,
            check_type=args.check_type,
            name=args.name,
            interval_seconds=args.interval,
            timeout_seconds=args.timeout,
        )
        monitor = get_monitor(conn, monitor_id)
        if monitor is not None:
            safe_run_and_record(conn, [monitor], verbose=True, alerts=AlertConfig.from_env(), db_path=args.db)
    notify(args.socket)
    print(f"Record added: #{monitor_id}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        rows = list_monitors(conn, include_disabled=args.all)
    print_table(rows)
    return 0


def cmd_remove(args: argparse.Namespace) -> int:
    missing: list[int] = []
    removed: list[int] = []
    with connect(args.db) as conn:
        for monitor_id in args.ids:
            deleted = delete_monitor(conn, monitor_id)
            if deleted:
                removed.append(monitor_id)
            else:
                missing.append(monitor_id)
    if removed:
        notify(args.socket)
        print("Records removed: " + ", ".join(f"#{monitor_id}" for monitor_id in removed))
    for monitor_id in missing:
        print(f"Record not found: #{monitor_id}", file=sys.stderr)
    return 1 if missing else 0


def cmd_edit(args: argparse.Namespace) -> int:
    fields: dict[str, Any] = {}
    for arg_name, db_name in (
        ("target", "target"),
        ("check_type", "check_type"),
        ("name", "name"),
        ("interval", "interval_seconds"),
        ("timeout", "timeout_seconds"),
    ):
        value = getattr(args, arg_name)
        if value is not None:
            fields[db_name] = value
    if args.enable:
        fields["enabled"] = 1
    if args.disable:
        fields["enabled"] = 0
    if not fields:
        print("No fields were provided to edit.", file=sys.stderr)
        return 2
    with connect(args.db) as conn:
        updated = update_monitor(conn, args.id, fields)
    if not updated:
        print(f"Record not found: #{args.id}", file=sys.stderr)
        return 1
    notify(args.socket)
    print(f"Record updated: #{args.id}")
    return 0


def cmd_description_add(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        updated = set_description(conn, args.id, args.description)
    if not updated:
        print(f"Record not found: #{args.id}", file=sys.stderr)
        return 1
    notify(args.socket)
    print(f"Description updated: #{args.id}")
    return 0


def cmd_description_show(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        if args.id == "all":
            monitors = list_monitors(conn, include_disabled=True)
            print_descriptions(monitors)
            return 0
        try:
            monitor_id = int(args.id)
        except ValueError:
            print("Description target must be a record ID or all.", file=sys.stderr)
            return 2
        monitor = get_monitor(conn, monitor_id)
    if monitor is None:
        print(f"Record not found: #{monitor_id}", file=sys.stderr)
        return 1
    description = monitor.get("description") or ""
    if not description:
        print(f"No description for #{monitor_id}.")
        return 0
    print(description)
    return 0


def cmd_description_clear(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        updated = clear_description(conn, args.id)
    if not updated:
        print(f"Record not found: #{args.id}", file=sys.stderr)
        return 1
    notify(args.socket)
    print(f"Description cleared: #{args.id}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    with connect(args.db) as conn:
        if args.targets and args.targets != ["all"]:
            monitors = []
            missing_or_invalid = False
            for target in args.targets:
                try:
                    monitor_id = int(target)
                except ValueError:
                    print(f"Check target must be a record ID or all: {target}", file=sys.stderr)
                    missing_or_invalid = True
                    continue
                monitor = get_monitor(conn, monitor_id)
                if monitor is None:
                    print(f"Record not found: #{monitor_id}", file=sys.stderr)
                    missing_or_invalid = True
                    continue
                monitors.append(monitor)
        else:
            monitors = list_monitors(conn, include_disabled=False)
        if not monitors:
            print("No enabled records to check.")
            return 1 if args.targets else 0
        failures = safe_run_and_record(conn, monitors, verbose=True, alerts=AlertConfig.from_env(), db_path=args.db)
    return 1 if failures or (args.targets and args.targets != ["all"] and missing_or_invalid) else 0


def cmd_alert_test(args: argparse.Namespace) -> int:
    config = AlertConfig.from_env()
    if not config.enabled:
        print("No alert channel selected. Use UTHERE_ALERT_CHANNELS=mail,telegram,whatsapp.", file=sys.stderr)
        return 2
    errors = send_alerts(config, "uthere test alert")
    if errors:
        for error in errors:
            print(f"Alert error: {error}", file=sys.stderr)
        return 1
    print("Test alert sent.")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    stop = False

    def handle_stop(signum: int, frame: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGTERM, handle_stop)
    signal.signal(signal.SIGINT, handle_stop)

    alerts = AlertConfig.from_env()
    alert_channels = ",".join(alerts.channels) if alerts.enabled else "disabled"
    print(f"uthere service started. Database: {args.db} Socket: {args.socket} Alerts: {alert_channels}")
    with connect(args.db) as conn:
        with WakeServer(args.socket) as wake_server:
            while not stop:
                monitors = due_monitors(conn)
                if monitors:
                    safe_run_and_record(conn, monitors, verbose=True, alerts=alerts, db_path=args.db)
                    continue

                wait_seconds = seconds_until_next_due(conn)
                if wait_seconds is None:
                    wait_seconds = args.max_sleep
                wait_seconds = min(wait_seconds, args.max_sleep)
                wake_server.wait(wait_seconds)
    print("uthere service stopped.")
    return 0


def safe_run_and_record(
    conn: Any,
    monitors: list[dict[str, Any]],
    *,
    verbose: bool,
    alerts: AlertConfig | None,
    db_path: str,
) -> int:
    try:
        return run_and_record(conn, monitors, verbose=verbose, alerts=alerts)
    except sqlite3.OperationalError as exc:
        if "readonly" in str(exc).lower():
            print(
                f"SQLite database is read-only: {db_path}. "
                "Check file ownership/permissions and make sure the CLI and service use the same database.",
                file=sys.stderr,
            )
            return 1
        raise


def run_and_record(conn: Any, monitors: list[dict[str, Any]], *, verbose: bool, alerts: AlertConfig | None = None) -> int:
    failures = 0
    for monitor in monitors:
        result = run_check(monitor)
        should_send_alert = should_alert(alerts, monitor, result.healthy) if alerts else False
        record_result(
            conn,
            monitor["id"],
            healthy=result.healthy,
            latency_ms=result.latency_ms,
            status_code=result.status_code,
            error=result.error,
        )
        if not result.healthy:
            failures += 1
            if should_send_alert and alerts:
                message = format_alert_message(monitor, result)
                for error in send_alerts(alerts, message):
                    print(f"Alert error: {error}", file=sys.stderr, flush=True)
        if verbose:
            status = "healthy" if result.healthy else "unhealthy"
            code = f" HTTP {result.status_code}" if result.status_code is not None else ""
            err = f" - {result.error}" if result.error else ""
            print(f"#{monitor['id']} {monitor['target']} [{monitor['check_type']}] {status}{code} {result.latency_ms:.0f}ms{err}", flush=True)
    return failures


def print_table(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No records.")
        return
    headers = ["ID", "NAME", "TARGET", "TYPE", "INT", "EN", "LAST CHECK", "STATUS", "LATENCY", "CODE", "ERROR"]
    data = [
        [
            str(row["id"]),
            row["name"] or "-",
            row["target"],
            row["check_type"],
            f"{row['interval_seconds']}s",
            "yes" if row["enabled"] else "no",
            row["last_checked_at"] or "-",
            row["last_status"],
            f"{row['last_latency_ms']:.0f}ms" if row["last_latency_ms"] is not None else "-",
            str(row["last_status_code"]) if row["last_status_code"] is not None else "-",
            shorten(row["last_error"] or "-", 40),
        ]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for row in data:
        widths = [max(width, len(value)) for width, value in zip(widths, row, strict=True)]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths, strict=True)))
    print("  ".join("-" * width for width in widths))
    for row in data:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)))


def print_descriptions(rows: list[dict[str, Any]]) -> None:
    if not rows:
        print("No records.")
        return
    headers = ["ID", "NAME", "TARGET", "DESCRIPTION"]
    data = [
        [
            str(row["id"]),
            row["name"] or "-",
            row["target"],
            shorten(row["description"] or "-", 80),
        ]
        for row in rows
    ]
    widths = [len(header) for header in headers]
    for row in data:
        widths = [max(width, len(value)) for width, value in zip(widths, row, strict=True)]
    print("  ".join(header.ljust(width) for header, width in zip(headers, widths, strict=True)))
    print("  ".join("-" * width for width in widths))
    for row in data:
        print("  ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)))


def shorten(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3] + "..."


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except DatabasePermissionError as exc:
        print(
            f"{exc}. Check file ownership/permissions and make sure the CLI and service use the same database.",
            file=sys.stderr,
        )
        return 1
