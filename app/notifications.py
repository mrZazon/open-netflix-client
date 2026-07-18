from __future__ import annotations

import logging
import subprocess
from typing import Optional

from PySide6.QtCore import QObject

log = logging.getLogger(__name__)


class NotificationManager(QObject):
    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)

    def _send_notify_send(
        self, title: str, body: str, urgency: str = "normal"
    ) -> None:
        try:
            subprocess.run(
                ["notify-send", "-a", "Netflix Client", "-u", urgency,
                 title, body],
                capture_output=True, timeout=3
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

    def new_episode(self, show: str, episode: str) -> None:
        self._send_notify_send(
            f"New Episode: {show}",
            f"{episode} is now available",
        )

    def download_complete(self, title: str) -> None:
        self._send_notify_send(
            "Download Complete",
            f"{title} has been downloaded",
        )

    def playback_paused(self, title: str = "") -> None:
        text = f'"{title}" paused' if title else "Playback paused"
        self._send_notify_send("Netflix", text)

    def playback_resumed(self, title: str = "") -> None:
        text = f'"{title}" resumed' if title else "Playback resumed"
        self._send_notify_send("Netflix", text)

    def session_expired(self) -> None:
        self._send_notify_send(
            "Session Expired",
            "Please sign in again to continue watching",
            urgency="critical",
        )

    def connection_lost(self) -> None:
        self._send_notify_send(
            "Connection Lost",
            "Attempting to reconnect...",
            urgency="critical",
        )

    def connection_restored(self) -> None:
        self._send_notify_send(
            "Connection Restored",
            "You are back online",
        )

    def download_progress(self, title: str, percent: int) -> None:
        if percent in (25, 50, 75, 100):
            self._send_notify_send(
                f"Downloading: {title}",
                f"{percent}% complete",
            )

    def update_available(self, version: str) -> None:
        self._send_notify_send(
            "Update Available",
            f"Netflix Client {version} is ready to install",
        )

    def generic(self, title: str, body: str) -> None:
        self._send_notify_send(title, body)
