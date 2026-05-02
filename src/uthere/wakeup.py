from __future__ import annotations

import os
import selectors
import socket
from pathlib import Path

from .config import get_setting


def default_socket_path() -> str:
    return get_setting("UTHERE_SOCKET", "/tmp/uthere.sock")


def notify(socket_path: str) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
            client.settimeout(0.2)
            client.connect(socket_path)
            client.sendall(b"wake\n")
    except OSError:
        pass


class WakeServer:
    def __init__(self, socket_path: str) -> None:
        self.socket_path = socket_path
        self.selector = selectors.DefaultSelector()
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def __enter__(self) -> "WakeServer":
        path = Path(self.socket_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        self.server.bind(self.socket_path)
        self.server.listen()
        self.server.setblocking(False)
        os.chmod(self.socket_path, 0o666)
        self.selector.register(self.server, selectors.EVENT_READ)
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        self.selector.close()
        self.server.close()
        try:
            Path(self.socket_path).unlink()
        except FileNotFoundError:
            pass

    def wait(self, timeout: float | None) -> bool:
        events = self.selector.select(timeout)
        if not events:
            return False
        for key, _ in events:
            if key.fileobj is self.server:
                connection, _ = self.server.accept()
                with connection:
                    connection.recv(1024)
        return True
