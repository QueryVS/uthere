from __future__ import annotations

import threading

import pytest

from uthere.wakeup import WakeServer, notify


def test_wake_server_receives_notify(tmp_path):
    socket_path = str(tmp_path / "wake.sock")
    received: list[bool] = []
    ready = threading.Event()
    errors: list[BaseException] = []

    def wait_for_wake():
        try:
            with WakeServer(socket_path) as server:
                ready.set()
                received.append(server.wait(2))
        except BaseException as exc:
            errors.append(exc)
            ready.set()

    thread = threading.Thread(target=wait_for_wake)
    thread.start()
    assert ready.wait(2)
    if errors and isinstance(errors[0], PermissionError):
        pytest.skip("Unix socket bind is blocked in this sandbox")
    if errors:
        raise errors[0]

    notify(socket_path)
    thread.join(timeout=3)

    assert received == [True]
