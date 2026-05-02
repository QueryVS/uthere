from __future__ import annotations

import platform
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckResult:
    healthy: bool
    latency_ms: float
    status_code: int | None = None
    error: str | None = None


def run_check(monitor: dict[str, Any]) -> CheckResult:
    started = time.monotonic()
    try:
        if monitor["check_type"] == "ping":
            return ping(monitor["target"], float(monitor["timeout_seconds"]))
        if monitor["check_type"] == "http":
            return http(monitor["target"], float(monitor["timeout_seconds"]))
        return CheckResult(False, 0, error=f"Unknown check type: {monitor['check_type']}")
    except Exception as exc:
        latency_ms = (time.monotonic() - started) * 1000
        return CheckResult(False, latency_ms, error=f"{type(exc).__name__}: {str(exc)[:260]}")


def ping(target: str, timeout_seconds: float) -> CheckResult:
    system = platform.system().lower()
    timeout_value = str(max(1, int(timeout_seconds)))
    if system == "darwin":
        cmd = ["ping", "-c", "1", "-W", str(int(timeout_seconds * 1000)), target]
    else:
        cmd = ["ping", "-c", "1", "-W", timeout_value, target]

    started = time.monotonic()
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout_seconds + 1,
            check=False,
        )
    except FileNotFoundError:
        return CheckResult(False, 0, error="ping command not found")
    except subprocess.TimeoutExpired:
        return CheckResult(False, timeout_seconds * 1000, error="ping timed out")

    latency_ms = (time.monotonic() - started) * 1000
    if completed.returncode == 0:
        return CheckResult(True, latency_ms)

    error = completed.stderr.strip() or completed.stdout.strip() or "ping failed"
    return CheckResult(False, latency_ms, error=error.splitlines()[-1][:300])


def http(target: str, timeout_seconds: float) -> CheckResult:
    url = target if target.startswith(("http://", "https://")) else f"http://{target}"
    request = urllib.request.Request(url, method="GET", headers={"User-Agent": "uthere/0.1"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
            latency_ms = (time.monotonic() - started) * 1000
            code = response.getcode()
            return CheckResult(200 <= code < 300, latency_ms, status_code=code)
    except urllib.error.HTTPError as exc:
        latency_ms = (time.monotonic() - started) * 1000
        return CheckResult(False, latency_ms, status_code=exc.code, error=f"HTTP {exc.code}")
    except urllib.error.URLError as exc:
        latency_ms = (time.monotonic() - started) * 1000
        return CheckResult(False, latency_ms, error=str(exc.reason)[:300])
    except TimeoutError:
        return CheckResult(False, timeout_seconds * 1000, error="http timed out")
