from __future__ import annotations

import logging
from typing import Callable, Dict, Optional

from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QKeySequence, QShortcut, QAction
from PySide6.QtWidgets import QWidget

from app.settings import settings

log = logging.getLogger(__name__)


class ShortcutManager(QObject):
    open_netflix = Signal()
    play_pause = Signal()
    mute = Signal()
    fullscreen = Signal()
    picture_in_picture = Signal()
    always_on_top = Signal()
    reload = Signal()
    dev_tools = Signal()
    quit_app = Signal()
    volume_up = Signal()
    volume_down = Signal()
    seek_forward = Signal()
    seek_backward = Signal()
    next_episode = Signal()
    previous_episode = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._parent = parent
        self._shortcuts: Dict[str, QShortcut] = {}
        self._actions: Dict[str, QAction] = {}
        self._setup()

    def _setup(self) -> None:
        if not self._parent:
            return
        bindings = {
            "open_netflix": (settings.get("shortcuts", "open_netflix", "Ctrl+Shift+N"),
                             self.open_netflix),
            "play_pause": (settings.get("shortcuts", "play_pause", "Ctrl+Shift+P"),
                           self.play_pause),
            "mute": (settings.get("shortcuts", "mute", "Ctrl+Shift+M"),
                     self.mute),
            "fullscreen": (settings.get("shortcuts", "fullscreen", "Ctrl+Shift+F"),
                           self.fullscreen),
            "picture_in_picture": (
                settings.get("shortcuts", "picture_in_picture", "Ctrl+Shift+I"),
                self.picture_in_picture),
            "always_on_top": (settings.get("shortcuts", "always_on_top", "Ctrl+Shift+T"),
                              self.always_on_top),
            "reload": (settings.get("shortcuts", "reload", "Ctrl+Shift+R"),
                       self.reload),
            "dev_tools": (settings.get("shortcuts", "dev_tools", "Ctrl+Shift+D"),
                          self.dev_tools),
        }
        for name, (keyseq, signal) in bindings.items():
            self._add_shortcut(name, keyseq, signal)

        media_keys = {
            "volume_up": ("Ctrl+Up", self.volume_up),
            "volume_down": ("Ctrl+Down", self.volume_down),
            "seek_forward": ("Ctrl+Right", self.seek_forward),
            "seek_backward": ("Ctrl+Left", self.seek_backward),
            "next_episode": ("Ctrl+Shift+Right", self.next_episode),
            "previous_episode": ("Ctrl+Shift+Left", self.previous_episode),
        }
        for name, (keyseq, signal) in media_keys.items():
            self._add_shortcut(name, keyseq, signal)

        quit_shortcut = QShortcut(QKeySequence("Ctrl+Q"), self._parent)
        quit_shortcut.activated.connect(self.quit_app)

        escape_shortcut = QShortcut(QKeySequence("Escape"), self._parent)
        escape_shortcut.activated.connect(self._on_escape)

    def _add_shortcut(self, name: str, keyseq: str, signal: Signal) -> None:
        if not self._parent or not keyseq:
            return
        try:
            shortcut = QShortcut(QKeySequence(keyseq), self._parent)
            shortcut.activated.connect(signal)
            self._shortcuts[name] = shortcut
        except Exception as exc:
            log.warning("Failed to register shortcut '%s': %s", name, exc)

    def _on_escape(self) -> None:
        if self._parent:
            from app.window import MainWindow
            win = self._parent.window() if self._parent else None
            if isinstance(win, MainWindow):
                if win.isFullScreen():
                    win.exit_fullscreen()

    def update_shortcut(self, name: str, keyseq: str) -> None:
        if name in self._shortcuts:
            try:
                self._shortcuts[name].setKey(QKeySequence(keyseq))
            except Exception as exc:
                log.warning("Failed to update shortcut '%s': %s", name, exc)

    def reload_settings(self) -> None:
        for name, shortcut in self._shortcuts.items():
            key = f"shortcuts.{name}"
            parts = name.split(".")
            if len(parts) == 1:
                keyseq = settings.get("shortcuts", name, "")
            else:
                keyseq = settings.get(parts[0], parts[1], "")
            if keyseq:
                try:
                    shortcut.setKey(QKeySequence(keyseq))
                except Exception as exc:
                    log.warning("Failed to reload shortcut '%s': %s", name, exc)
