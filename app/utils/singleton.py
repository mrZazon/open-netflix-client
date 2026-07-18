from __future__ import annotations

import os
import sys
import socket
import json
import atexit

SINGLETON_PORT = 48321


class SingleInstance:
    _instance: SingleInstance | None = None
    _socket: socket.socket | None = None

    def __init__(self) -> None:
        self._ensure()

    def _ensure(self) -> None:
        try:
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self._socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._socket.bind(("127.0.0.1", SINGLETON_PORT))
            self._socket.listen(1)
            atexit.register(self._cleanup)
        except OSError:
            self._notify_running()
            sys.exit(0)

    def _notify_running(self) -> None:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.connect(("127.0.0.1", SINGLETON_PORT))
            sock.send(json.dumps({"action": "raise"}).encode())
            sock.close()
        except OSError:
            pass

    def _cleanup(self) -> None:
        if self._socket:
            try:
                self._socket.close()
            except OSError:
                pass
