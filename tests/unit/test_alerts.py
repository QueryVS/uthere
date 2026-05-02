from __future__ import annotations

from types import SimpleNamespace

import pytest

from uthere.alerts import AlertConfig, format_alert_message, parse_csv, should_alert


def config(*, channels=("telegram",), mode="on_change"):
    return AlertConfig(
        channels=channels,
        mode=mode,
        mail_host=None,
        mail_port=587,
        mail_user=None,
        mail_password=None,
        mail_from=None,
        mail_to=(),
        mail_tls="starttls",
        telegram_bot_token=None,
        telegram_chat_ids=(),
        whatsapp_token=None,
        whatsapp_phone_number_id=None,
        whatsapp_to=(),
        whatsapp_api_version="v20.0",
        whatsapp_api_url=None,
    )


def test_parse_csv_strips_empty_items():
    assert parse_csv("mail, telegram,,whatsapp ") == ("mail", "telegram", "whatsapp")


@pytest.mark.parametrize(
    ("last_status", "expected"),
    [
        ("unknown", True),
        ("healthy", True),
        ("unhealthy", False),
    ],
)
def test_should_alert_on_change(last_status, expected):
    monitor = {"last_status": last_status}

    assert should_alert(config(), monitor, healthy=False) is expected


def test_should_alert_always_repeats_failures():
    assert should_alert(config(mode="always"), {"last_status": "unhealthy"}, healthy=False) is True


def test_format_alert_message_contains_monitor_context():
    monitor = {"id": 7, "name": "api", "target": "https://api.example", "check_type": "http"}
    result = SimpleNamespace(latency_ms=42.4, status_code=503, error="HTTP 503")

    message = format_alert_message(monitor, result)

    assert "monitor: api" in message
    assert "target: https://api.example" in message
    assert "http_status: 503" in message
