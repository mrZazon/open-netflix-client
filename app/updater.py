from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtNetwork import QNetworkAccessManager, QNetworkRequest

from app.utils.config import APP_VERSION

log = logging.getLogger(__name__)

GITHUB_API = "https://api.github.com/repos/netflix-client/netflix-client/releases/latest"


class UpdateChecker(QObject):
    update_available = Signal(str, str)
    up_to_date = Signal()
    check_failed = Signal(str)
    download_progress = Signal(int)
    download_complete = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._manager = QNetworkAccessManager(self)
        self._manager.finished.connect(self._on_check_response)
        self._latest_version: str = ""
        self._download_url: str = ""

    def check(self) -> None:
        request = QNetworkRequest(QUrl(GITHUB_API))
        request.setRawHeader(b"Accept", b"application/vnd.github.v3+json")
        request.setRawHeader(b"User-Agent", b"netflix-client")
        request.setTransferTimeout(10000)
        self._manager.get(request)

    def _on_check_response(self, reply) -> None:
        try:
            if reply.error():
                self.check_failed.emit(reply.errorString())
                return

            data = json.loads(bytes(reply.readAll()).decode())
            self._latest_version = data.get("tag_name", "").lstrip("v")

            if not self._latest_version:
                self.check_failed.emit("Could not determine latest version")
                return

            if self._is_newer(self._latest_version, APP_VERSION):
                assets = data.get("assets", [])
                for asset in assets:
                    name = asset.get("name", "")
                    if name.endswith(".AppImage"):
                        self._download_url = asset["browser_download_url"]
                        break
                self.update_available.emit(self._latest_version, self._download_url)
            else:
                self.up_to_date.emit()

        except Exception as exc:
            log.debug("Update check failed: %s", exc)
            self.check_failed.emit(str(exc))
        finally:
            reply.deleteLater()

    def _is_newer(self, latest: str, current: str) -> bool:
        try:
            latest_parts = [int(x) for x in latest.split(".")]
            current_parts = [int(x) for x in current.split(".")]
            max_len = max(len(latest_parts), len(current_parts))
            latest_parts += [0] * (max_len - len(latest_parts))
            current_parts += [0] * (max_len - len(current_parts))
            return latest_parts > current_parts
        except (ValueError, IndexError):
            return False
