from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QMenu, QSystemTrayIcon, QWidget

log = logging.getLogger(__name__)


class SystemTrayManager(QObject):
    show_window = Signal()
    quit_app = Signal()
    play_pause = Signal()
    mute = Signal()
    open_downloads = Signal()
    open_settings = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self._tray: QSystemTrayIcon | None = None
        self._menu: QMenu | None = None
        self._setup()

    def _setup(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            log.warning("System tray not available")
            return

        self._tray = QSystemTrayIcon(self._parent)
        from app.utils.config import get_app_icon
        self._tray.setIcon(get_app_icon())
        self._tray.setToolTip("Netflix Client")

        self._menu = QMenu(self._parent)
        self._menu.setObjectName("trayMenu")

        open_action = QAction("Netflix", self._menu)
        open_action.triggered.connect(self.show_window)
        self._menu.addAction(open_action)

        self._menu.addSeparator()

        self._play_action = QAction("Pause", self._menu)
        self._play_action.triggered.connect(self.play_pause)
        self._menu.addAction(self._play_action)

        self._mute_action = QAction("Mute", self._menu)
        self._mute_action.triggered.connect(self.mute)
        self._menu.addAction(self._mute_action)

        self._menu.addSeparator()

        downloads_action = QAction("Downloads", self._menu)
        downloads_action.triggered.connect(self.open_downloads)
        self._menu.addAction(downloads_action)

        settings_action = QAction("Settings", self._menu)
        settings_action.triggered.connect(self.open_settings)
        self._menu.addAction(settings_action)

        self._menu.addSeparator()

        quit_action = QAction("Quit", self._menu)
        quit_action.triggered.connect(self.quit_app)
        self._menu.addAction(quit_action)

        self._tray.setContextMenu(self._menu)

        self._tray.activated.connect(self._on_activated)
        self._tray.show()

    def _on_activated(self, reason: int) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window.emit()

    def set_playback_state(self, playing: bool) -> None:
        if self._play_action:
            self._play_action.setText("Pause" if playing else "Play")

    def set_mute_state(self, muted: bool) -> None:
        if self._mute_action:
            self._mute_action.setText("Unmute" if muted else "Mute")

    def show_notification(self, title: str, message: str) -> None:
        if self._tray and self._tray.supportsMessages():
            self._tray.showMessage(title, message, QIcon(), 5000)

    @property
    def is_available(self) -> bool:
        return self._tray is not None

    def hide(self) -> None:
        if self._tray:
            self._tray.hide()

    def show(self) -> None:
        if self._tray:
            self._tray.show()
