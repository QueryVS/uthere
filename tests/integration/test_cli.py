from __future__ import annotations

import os
from types import SimpleNamespace

import uthere.cli
from uthere.cli import main


def fake_success(monitor):
    return SimpleNamespace(healthy=True, latency_ms=12.0, status_code=200 if monitor["check_type"] == "http" else None, error=None)


def test_cli_add_list_edit_remove(tmp_path, capsys):
    db = str(tmp_path / "uthere.db")
    socket_path = str(tmp_path / "uthere.sock")

    assert main(["--db", db, "--socket", socket_path, "add", "example.com", "--type", "ping", "--interval", "30"]) == 0
    assert main(["--db", db, "list"]) == 0
    output = capsys.readouterr().out
    assert "example.com" in output
    assert "ping" in output
    assert "LATENCY" in output
    assert "healthy" in output

    assert main(["--db", db, "--socket", socket_path, "edit", "1", "--interval", "45"]) == 0
    assert main(["--db", db, "remove", "1"]) == 0
    assert main(["--db", db, "list"]) == 0
    assert "No records." in capsys.readouterr().out


def test_cli_description_add_show_clear(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "uthere.db")
    monkeypatch.setattr(uthere.cli, "run_check", fake_success)

    assert main(["--db", db, "add", "example.com", "--type", "ping"]) == 0
    assert main(["--db", db, "des", "add", "1", "this description server"]) == 0
    assert main(["--db", db, "des", "show", "1"]) == 0
    assert "this description server" in capsys.readouterr().out

    assert main(["--db", db, "description", "clear", "1"]) == 0
    assert main(["--db", db, "des", "show", "1"]) == 0
    assert "No description for #1." in capsys.readouterr().out


def test_cli_description_show_all(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "uthere.db")
    monkeypatch.setattr(uthere.cli, "run_check", fake_success)

    assert main(["--db", db, "add", "one.example", "--type", "ping", "--name", "one"]) == 0
    assert main(["--db", db, "add", "two.example", "--type", "ping", "--name", "two"]) == 0
    assert main(["--db", db, "des", "add", "1", "first server"]) == 0

    assert main(["--db", db, "des", "show", "all"]) == 0
    output = capsys.readouterr().out
    assert "DESCRIPTION" in output
    assert "first server" in output
    assert "two.example" in output


def test_cli_check_all_and_multiple_ids(tmp_path, monkeypatch, capsys):
    db = str(tmp_path / "uthere.db")
    checked: list[int] = []

    def fake_run_check(monitor):
        checked.append(monitor["id"])
        return SimpleNamespace(healthy=True, latency_ms=12.0, status_code=200, error=None)

    monkeypatch.setattr(uthere.cli, "run_check", fake_run_check)

    assert main(["--db", db, "add", "one.example", "--type", "http"]) == 0
    assert main(["--db", db, "add", "two.example", "--type", "http"]) == 0

    checked.clear()
    assert main(["--db", db, "check", "all"]) == 0
    assert checked == [1, 2]

    checked.clear()
    assert main(["--db", db, "check", "1", "99"]) == 1
    captured = capsys.readouterr()
    assert checked == [1]
    assert "Record not found: #99" in captured.err


def test_cli_remove_multiple_ids(tmp_path, capsys, monkeypatch):
    db = str(tmp_path / "uthere.db")
    monkeypatch.setattr(uthere.cli, "run_check", fake_success)

    assert main(["--db", db, "add", "one.example", "--type", "ping"]) == 0
    assert main(["--db", db, "add", "two.example", "--type", "ping"]) == 0
    assert main(["--db", db, "add", "three.example", "--type", "ping"]) == 0

    assert main(["--db", db, "remove", "1", "2", "99"]) == 1
    captured = capsys.readouterr()
    assert "Records removed: #1, #2" in captured.out
    assert "Record not found: #99" in captured.err

    assert main(["--db", db, "list"]) == 0
    output = capsys.readouterr().out
    assert "three.example" in output
    assert "one.example" not in output
    assert "two.example" not in output


def test_cli_uses_env_db(tmp_path, monkeypatch, capsys):
    db = tmp_path / "env.db"
    monkeypatch.setenv("UTHERE_DB", str(db))
    monkeypatch.setattr(uthere.cli, "run_check", fake_success)

    assert main(["add", "https://example.com", "--type", "http"]) == 0
    assert main(["list"]) == 0

    assert "https://example.com" in capsys.readouterr().out
    assert db.exists()


def test_alert_test_without_channel_returns_usage_error(monkeypatch, capsys):
    for key in tuple(os.environ):
        if key.startswith("UTHERE_ALERT_"):
            monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr("uthere.alerts.ENV_FILES", ())

    assert main(["alert-test"]) == 2
    assert "No alert channel selected" in capsys.readouterr().err
