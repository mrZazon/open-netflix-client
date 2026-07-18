from __future__ import annotations

import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set
from enum import Enum, auto

from PySide6.QtCore import QObject, Signal, QTimer

from app.settings import settings
from app.utils.config import DOWNLOADS_DIR

log = logging.getLogger(__name__)


class DownloadStatus(Enum):
    QUEUED = auto()
    DOWNLOADING = auto()
    PAUSED = auto()
    COMPLETED = auto()
    CANCELLED = auto()
    FAILED = auto()


class DownloadItem(QObject):
    progress_changed = Signal(int)
    status_changed = Signal(object)
    speed_changed = Signal(float)

    def __init__(
        self,
        title: str,
        url: str,
        path: Path | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.title = title
        self.url = url
        self.path = path or DOWNLOADS_DIR / f"{title}.mp4"
        self.status = DownloadStatus.QUEUED
        self.progress: int = 0
        self.total_bytes: int = 0
        self.downloaded_bytes: int = 0
        self.speed: float = 0.0
        self.error: str | None = None
        self.created_at = datetime.now()
        self._bytes_at_last_check: int = 0

    def update_progress(self, downloaded: int, total: int) -> None:
        self.downloaded_bytes = downloaded
        self.total_bytes = total
        if total > 0:
            new_progress = int((downloaded / total) * 100)
            if new_progress != self.progress:
                self.progress = new_progress
                self.progress_changed.emit(new_progress)

    def set_speed(self, speed: float) -> None:
        self.speed = speed
        self.speed_changed.emit(speed)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "title": self.title,
            "url": self.url,
            "path": str(self.path),
            "status": self.status.name,
            "progress": self.progress,
            "total_bytes": self.total_bytes,
            "downloaded_bytes": self.downloaded_bytes,
            "error": self.error,
            "created_at": self.created_at.isoformat(),
        }


class DownloadManager(QObject):
    download_added = Signal(object)
    download_removed = Signal(object)
    download_completed = Signal(object)
    download_failed = Signal(object, str)
    all_completed = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._downloads: Dict[str, DownloadItem] = {}
        self._active: Set[str] = set()

    def add_download(
        self, title: str, url: str, path: Path | None = None
    ) -> DownloadItem:
        item = DownloadItem(title, url, path, self)
        self._downloads[url] = item
        self._active.add(url)
        self.download_added.emit(item)
        log.info("Download queued: %s", title)
        return item

    def pause(self, url: str) -> bool:
        if url not in self._downloads:
            return False
        item = self._downloads[url]
        if item.status == DownloadStatus.DOWNLOADING:
            item.status = DownloadStatus.PAUSED
            item.status_changed.emit(item.status)
            self._active.discard(url)
            return True
        return False

    def resume(self, url: str) -> bool:
        if url not in self._downloads:
            return False
        item = self._downloads[url]
        if item.status == DownloadStatus.PAUSED:
            item.status = DownloadStatus.DOWNLOADING
            item.status_changed.emit(item.status)
            self._active.add(url)
            return True
        return False

    def cancel(self, url: str) -> bool:
        if url not in self._downloads:
            return False
        item = self._downloads[url]
        item.status = DownloadStatus.CANCELLED
        item.status_changed.emit(item.status)
        self._active.discard(url)
        self._cleanup_file(item)
        return True

    def retry(self, url: str) -> bool:
        if url not in self._downloads:
            return False
        item = self._downloads[url]
        if item.status == DownloadStatus.FAILED:
            item.status = DownloadStatus.QUEUED
            item.progress = 0
            item.error = None
            item.status_changed.emit(item.status)
            self._active.add(url)
            return True
        return False

    def remove(self, url: str) -> bool:
        if url not in self._downloads:
            return False
        item = self._downloads[url]
        self._active.discard(url)
        del self._downloads[url]
        self.download_removed.emit(item)
        return True

    def mark_completed(self, url: str) -> None:
        if url not in self._downloads:
            return
        item = self._downloads[url]
        item.status = DownloadStatus.COMPLETED
        item.progress = 100
        item.status_changed.emit(item.status)
        self._active.discard(url)
        self.download_completed.emit(item)
        if not self._active:
            self.all_completed.emit()

    def mark_failed(self, url: str, error: str) -> None:
        if url not in self._downloads:
            return
        item = self._downloads[url]
        item.status = DownloadStatus.FAILED
        item.error = error
        item.status_changed.emit(item.status)
        self._active.discard(url)
        self.download_failed.emit(item, error)

    def get_downloads(self) -> List[DownloadItem]:
        return list(self._downloads.values())

    def get_active(self) -> List[DownloadItem]:
        return [d for d in self._downloads.values()
                if d.status == DownloadStatus.DOWNLOADING]

    @property
    def has_active(self) -> bool:
        return len(self._active) > 0

    def _cleanup_file(self, item: DownloadItem) -> None:
        try:
            if item.path.exists():
                item.path.unlink()
        except OSError:
            pass

    def get_download_dir(self) -> Path:
        custom = settings.get("downloads", "directory", "")
        if custom:
            return Path(custom)
        return DOWNLOADS_DIR
