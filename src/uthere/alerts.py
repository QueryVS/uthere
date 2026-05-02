from __future__ import annotations

import json
import os
import smtplib
import ssl
import urllib.error
import urllib.request
from dataclasses import dataclass
from email.message import EmailMessage
from typing import Any


@dataclass(frozen=True)
class AlertConfig:
    channels: tuple[str, ...]
    mode: str
    mail_host: str | None
    mail_port: int
    mail_user: str | None
    mail_password: str | None
    mail_from: str | None
    mail_to: tuple[str, ...]
    mail_tls: str
    telegram_bot_token: str | None
    telegram_chat_ids: tuple[str, ...]
    whatsapp_token: str | None
    whatsapp_phone_number_id: str | None
    whatsapp_to: tuple[str, ...]
    whatsapp_api_version: str
    whatsapp_api_url: str | None

    @classmethod
    def from_env(cls) -> "AlertConfig":
        return cls(
            channels=parse_csv(os.environ.get("UTHERE_ALERT_CHANNELS", "")),
            mode=os.environ.get("UTHERE_ALERT_MODE", "on_change").strip().lower(),
            mail_host=empty_to_none(os.environ.get("UTHERE_MAIL_HOST")),
            mail_port=int(os.environ.get("UTHERE_MAIL_PORT", "587")),
            mail_user=empty_to_none(os.environ.get("UTHERE_MAIL_USER")),
            mail_password=empty_to_none(os.environ.get("UTHERE_MAIL_PASSWORD")),
            mail_from=empty_to_none(os.environ.get("UTHERE_MAIL_FROM")),
            mail_to=parse_csv(os.environ.get("UTHERE_MAIL_TO", "")),
            mail_tls=os.environ.get("UTHERE_MAIL_TLS", "starttls").strip().lower(),
            telegram_bot_token=empty_to_none(os.environ.get("UTHERE_TELEGRAM_BOT_TOKEN")),
            telegram_chat_ids=parse_csv(os.environ.get("UTHERE_TELEGRAM_CHAT_ID", "")),
            whatsapp_token=empty_to_none(os.environ.get("UTHERE_WHATSAPP_TOKEN")),
            whatsapp_phone_number_id=empty_to_none(os.environ.get("UTHERE_WHATSAPP_PHONE_NUMBER_ID")),
            whatsapp_to=parse_csv(os.environ.get("UTHERE_WHATSAPP_TO", "")),
            whatsapp_api_version=os.environ.get("UTHERE_WHATSAPP_API_VERSION", "v20.0").strip(),
            whatsapp_api_url=empty_to_none(os.environ.get("UTHERE_WHATSAPP_API_URL")),
        )

    @property
    def enabled(self) -> bool:
        return bool(self.channels)


def parse_csv(value: str) -> tuple[str, ...]:
    return tuple(item.strip() for item in value.split(",") if item.strip())


def empty_to_none(value: str | None) -> str | None:
    if value is None or not value.strip():
        return None
    return value.strip()


def should_alert(config: AlertConfig, monitor: dict[str, Any], healthy: bool) -> bool:
    if healthy or not config.enabled:
        return False
    if config.mode in {"always", "every_failure", "every-failure"}:
        return True
    return monitor.get("last_status") != "unhealthy"


def format_alert_message(monitor: dict[str, Any], result: Any) -> str:
    name = monitor.get("name") or f"#{monitor['id']}"
    parts = [
        "uthere alert: unhealthy",
        f"monitor: {name}",
        f"target: {monitor['target']}",
        f"type: {monitor['check_type']}",
        f"latency: {result.latency_ms:.0f}ms",
    ]
    if result.status_code is not None:
        parts.append(f"http_status: {result.status_code}")
    if result.error:
        parts.append(f"error: {result.error}")
    return "\n".join(parts)


def send_alerts(config: AlertConfig, message: str) -> list[str]:
    errors: list[str] = []
    for channel in config.channels:
        try:
            if channel == "mail":
                send_mail(config, message)
            elif channel == "telegram":
                send_telegram(config, message)
            elif channel == "whatsapp":
                send_whatsapp(config, message)
            else:
                errors.append(f"unknown alert channel: {channel}")
        except Exception as exc:  # Alerts must not stop health checks.
            errors.append(f"{channel}: {exc}")
    return errors


def send_mail(config: AlertConfig, message: str) -> None:
    if not config.mail_host or not config.mail_from or not config.mail_to:
        raise ValueError("mail requires UTHERE_MAIL_HOST, UTHERE_MAIL_FROM, and UTHERE_MAIL_TO")

    email = EmailMessage()
    email["Subject"] = "uthere alert: unhealthy"
    email["From"] = config.mail_from
    email["To"] = ", ".join(config.mail_to)
    email.set_content(message)

    if config.mail_tls == "ssl":
        with smtplib.SMTP_SSL(config.mail_host, config.mail_port, timeout=10, context=ssl.create_default_context()) as smtp:
            login_if_needed(smtp, config)
            smtp.send_message(email)
        return

    with smtplib.SMTP(config.mail_host, config.mail_port, timeout=10) as smtp:
        if config.mail_tls == "starttls":
            smtp.starttls(context=ssl.create_default_context())
        login_if_needed(smtp, config)
        smtp.send_message(email)


def login_if_needed(smtp: smtplib.SMTP, config: AlertConfig) -> None:
    if config.mail_user and config.mail_password:
        smtp.login(config.mail_user, config.mail_password)


def send_telegram(config: AlertConfig, message: str) -> None:
    if not config.telegram_bot_token or not config.telegram_chat_ids:
        raise ValueError("telegram requires UTHERE_TELEGRAM_BOT_TOKEN and UTHERE_TELEGRAM_CHAT_ID")

    url = f"https://api.telegram.org/bot{config.telegram_bot_token}/sendMessage"
    for chat_id in config.telegram_chat_ids:
        post_json(url, {"chat_id": chat_id, "text": message})


def send_whatsapp(config: AlertConfig, message: str) -> None:
    if not config.whatsapp_token or not config.whatsapp_to:
        raise ValueError("whatsapp requires UTHERE_WHATSAPP_TOKEN and UTHERE_WHATSAPP_TO")
    if config.whatsapp_api_url:
        url = config.whatsapp_api_url
    else:
        if not config.whatsapp_phone_number_id:
            raise ValueError("whatsapp requires UTHERE_WHATSAPP_PHONE_NUMBER_ID")
        url = f"https://graph.facebook.com/{config.whatsapp_api_version}/{config.whatsapp_phone_number_id}/messages"

    headers = {"Authorization": f"Bearer {config.whatsapp_token}"}
    for phone_number in config.whatsapp_to:
        payload = {
            "messaging_product": "whatsapp",
            "to": phone_number,
            "type": "text",
            "text": {"body": message},
        }
        post_json(url, payload, headers=headers)


def post_json(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    request_headers = {"Content-Type": "application/json", **(headers or {})}
    request = urllib.request.Request(url, data=body, headers=request_headers, method="POST")
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            response_body = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        response_body = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP {exc.code}: {response_body[:300]}") from exc

    if not response_body:
        return {}
    return json.loads(response_body)
