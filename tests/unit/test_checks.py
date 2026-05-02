from __future__ import annotations

from uthere.checks import run_check


def test_run_check_returns_unhealthy_for_unexpected_exception(monkeypatch):
    def broken_http(target, timeout_seconds):
        raise ValueError("bad target")

    monkeypatch.setattr("uthere.checks.http", broken_http)

    result = run_check({"check_type": "http", "target": "bad", "timeout_seconds": 1})

    assert result.healthy is False
    assert "ValueError" in result.error
