from __future__ import annotations

import logging
from typing import Optional

from PySide6.QtCore import Qt, Signal

from PySide6.QtWidgets import (
    QMainWindow, QVBoxLayout, QWidget, QPushButton, QHBoxLayout,
    QLabel, QFrame,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from app.utils.config import get_app_icon

log = logging.getLogger(__name__)


class PictureInPictureWindow(QMainWindow):
    closed = Signal()

    def __init__(self, browser_view: QWebEngineView | None = None) -> None:
        super().__init__()
        self._browser_view = browser_view
        self._original_parent: QWidget | None = None
        self._setup_ui()

    def _setup_ui(self) -> None:
        self.setWindowTitle("Netflix PiP")
        self.setWindowFlags(
            Qt.WindowType.Window |
            Qt.WindowType.FramelessWindowHint |
            Qt.WindowType.WindowStaysOnTopHint |
            Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, False)
        self.setMinimumSize(320, 180)
        self.resize(640, 360)

        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        title_bar = QFrame(central)
        title_bar.setFixedHeight(32)
        title_bar.setObjectName("pipTitleBar")
        title_bar.setStyleSheet(
            "QFrame#pipTitleBar {"
            "  background-color: #1c1c1c;"
            "  border: none;"
            "}"
        )
        title_layout = QHBoxLayout(title_bar)
        title_layout.setContentsMargins(8, 0, 8, 0)
        title_layout.setSpacing(4)

        icon_label = QLabel(title_bar)
        icon = get_app_icon()
        icon_label.setPixmap(icon.pixmap(16, 16))
        title_layout.addWidget(icon_label)

        title_text = QLabel("Netflix", title_bar)
        title_text.setStyleSheet("color: #e5e5e5; font-size: 12px;")
        title_layout.addWidget(title_text, 1)

        close_btn = QPushButton("×", title_bar)
        close_btn.setFixedSize(24, 24)
        close_btn.setStyleSheet(
            "QPushButton {"
            "  background: transparent;"
            "  color: #999;"
            "  border: none;"
            "  font-size: 16px;"
            "}"
            "QPushButton:hover {"
            "  color: #fff;"
            "  background: #e50914;"
            "  border-radius: 12px;"
            "}"
        )
        close_btn.clicked.connect(self._close_pip)
        title_layout.addWidget(close_btn)

        layout.addWidget(title_bar)

        self._content = QWidget(central)
        self._content.setStyleSheet("background-color: #000;")
        content_layout = QVBoxLayout(self._content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._content, 1)

    def set_content(self, view: QWebEngineView) -> None:
        if self._content.layout():
            if self._browser_view:
                self._browser_view.setParent(None)
            self._browser_view = view
            self._content.layout().addWidget(view)

    def _close_pip(self) -> None:
        self.closed.emit()
        self.close()

    def showEvent(self, event) -> None:
        super().showEvent(event)
        self.raise_()
        self.activateWindow()

    def _restore_view(self) -> None:
        if self._browser_view and self._original_parent:
            self._browser_view.setParent(self._original_parent)
            if self._original_parent.layout():
                self._original_parent.layout().addWidget(self._browser_view)
            self._browser_view.show()
