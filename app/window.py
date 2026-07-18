from __future__ import annotations

import logging
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt, QPoint, QTimer
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import QMainWindow, QVBoxLayout, QWidget, QApplication

from app.browser import NetflixBrowser
from app.settings import settings
from app.shortcuts import ShortcutManager
from app.tray import SystemTrayManager
from app.notifications import NotificationManager
from app.mpris import MprisManager
from app.pip import PictureInPictureWindow
from app.download import DownloadManager
from app.updater import UpdateChecker
from app.utils.config import NETFLIX_URL, APP_NAME, get_app_icon

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._browser = NetflixBrowser()
        self._shortcuts = ShortcutManager(self)
        self._tray = SystemTrayManager(self)
        self._notifications = NotificationManager(self)
        self._mpris = MprisManager(self)
        self._pip_window: PictureInPictureWindow | None = None
        self._downloads = DownloadManager(self)
        self._updater = UpdateChecker(self)
        self._always_on_top = False
        self._was_maximized_before_fullscreen = False

        self._setup_window()
        self._setup_ui()
        self._setup_connections()
        self._restore_state()
        self._setup_mpris()
        self._setup_updater()

        log.info("Window initialized")

    # -- Window setup -------------------------------------------------------

    def _setup_window(self) -> None:
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(get_app_icon())
        self.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, True)
        self.menuBar().setVisible(False)
        self.setMinimumSize(640, 480)
        self._apply_theme()

    def _apply_theme(self) -> None:
        qss_path = Path(__file__).resolve().parent / "css" / "style.qss"
        if qss_path.exists():
            self.setStyleSheet(qss_path.read_text())

    # -- UI layout ----------------------------------------------------------

    def _setup_ui(self) -> None:
        central = QWidget(self)
        central.setObjectName("centralWidget")
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._browser_view = self._browser.create_view(self)
        if self._browser_view:
            layout.addWidget(self._browser_view)

    # -- Signal connections -------------------------------------------------

    def _setup_connections(self) -> None:
        page = self._browser.current_page
        if page:
            page.playback_state_changed.connect(self._on_playback_state)
            page.metadata_changed.connect(self._on_metadata)

        self._shortcuts.open_netflix.connect(self._on_open_netflix)
        self._shortcuts.play_pause.connect(self._on_play_pause)
        self._shortcuts.mute.connect(self._on_mute)
        self._shortcuts.fullscreen.connect(self._toggle_fullscreen)
        self._shortcuts.picture_in_picture.connect(self._toggle_pip)
        self._shortcuts.always_on_top.connect(self._toggle_always_on_top)
        self._shortcuts.reload.connect(self._on_reload)
        self._shortcuts.dev_tools.connect(self._on_dev_tools)
        self._shortcuts.quit_app.connect(self._on_quit)
        self._shortcuts.volume_up.connect(self._on_volume_up)
        self._shortcuts.volume_down.connect(self._on_volume_down)
        self._shortcuts.seek_forward.connect(self._on_seek_forward)
        self._shortcuts.seek_backward.connect(self._on_seek_backward)
        self._shortcuts.next_episode.connect(self._on_next_episode)
        self._shortcuts.previous_episode.connect(self._on_previous_episode)

        self._tray.show_window.connect(self._show_from_tray)
        self._tray.quit_app.connect(self._on_quit)
        self._tray.play_pause.connect(self._on_play_pause)
        self._tray.mute.connect(self._on_mute)
        self._tray.open_downloads.connect(self._on_open_downloads)
        self._tray.open_settings.connect(self._on_open_settings)

    # -- MPRIS / Updater ----------------------------------------------------

    def _setup_mpris(self) -> None:
        p = self._mpris.provider
        p.set_callbacks(
            on_play=self._on_play,
            on_pause=self._on_pause,
            on_play_pause=self._on_play_pause,
            on_stop=self._on_stop,
            on_next=self._on_next_episode,
            on_previous=self._on_previous_episode,
            on_seek=self._on_seek,
            on_set_position=self._on_set_position,
            on_set_volume=self._on_set_volume_mpris,
        )
        self._mpris.start()

    def _setup_updater(self) -> None:
        self._updater.update_available.connect(self._on_update_available)
        QTimer.singleShot(5000, self._updater.check)

    # -- Window state -------------------------------------------------------

    def _restore_state(self) -> None:
        w = settings.get("window", "width", 1280)
        h = settings.get("window", "height", 720)
        x = settings.get("window", "x", -1)
        y = settings.get("window", "y", -1)
        maximized = settings.get("window", "maximized", False)
        self.resize(w, h)
        if x >= 0 and y >= 0:
            p = QPoint(x, y)
            on = any(s.geometry().contains(p) for s in QApplication.screens())
            if on:
                self.move(p)
        (self.showMaximized if maximized else self.show)()

    def _save_state(self) -> None:
        if self.isMaximized():
            settings.set("window", "maximized", True)
        else:
            settings.set("window", "maximized", False)
            settings.set("window", "width", self.width())
            settings.set("window", "height", self.height())
            settings.set("window", "x", self.x())
            settings.set("window", "y", self.y())

    # -- Profile switching --------------------------------------------------

    def _switch_profile(self, name: str) -> None:
        view = self._browser.switch_profile(name)
        if view:
            old = self._browser_view
            if old and old is not view:
                l = self.centralWidget().layout()
                if l:
                    l.removeWidget(old)
                    old.setParent(None)
                    l.addWidget(view)
                self._browser_view = view
            page = self._browser.current_page
            if page:
                page.playback_state_changed.connect(
                    self._on_playback_state,
                    type=Qt.ConnectionType.UniqueConnection)
                page.metadata_changed.connect(
                    self._on_metadata,
                    type=Qt.ConnectionType.UniqueConnection)

    # -- Playback callbacks -------------------------------------------------

    def _on_playback_state(self, state: str) -> None:
        is_playing = state == "playing"
        self._tray.set_playback_state(is_playing)
        self._mpris.on_playback_state_changed(state)

    def _on_metadata(self, metadata: Dict[str, Any]) -> None:
        self._mpris.on_metadata_changed(metadata)

    # -- Actions ------------------------------------------------------------

    def _on_open_netflix(self) -> None:
        self._browser.load_url(NETFLIX_URL)
        self._show_from_tray()

    # -- Media control JS helpers -------------------------------------------

    def _js(self, code: str, cb=None) -> None:
        self._browser.run_javascript(code, cb)

    def _on_play_pause(self) -> None:
        self._js("const v=document.querySelector('video');"
                 "if(v){v.paused?v.play():v.pause()}")

    def _on_play(self) -> None:
        self._js("const v=document.querySelector('video');if(v&&v.paused)v.play()")

    def _on_pause(self) -> None:
        self._js("const v=document.querySelector('video');if(v&&!v.paused)v.pause()")

    def _on_stop(self) -> None:
        self._js("const v=document.querySelector('video');if(v&&!v.paused)v.pause()")

    def _on_mute(self) -> None:
        self._js("const v=document.querySelector('video');if(v)v.muted=!v.muted")

    def _on_volume_up(self) -> None:
        self._js("const v=document.querySelector('video');"
                 "if(v)v.volume=Math.min(1,v.volume+0.1)")

    def _on_volume_down(self) -> None:
        self._js("const v=document.querySelector('video');"
                 "if(v)v.volume=Math.max(0,v.volume-0.1)")

    def _on_seek_forward(self) -> None:
        self._js("const v=document.querySelector('video');"
                 "if(v)v.currentTime=Math.min(v.duration,v.currentTime+30)")

    def _on_seek_backward(self) -> None:
        self._js("const v=document.querySelector('video');"
                 "if(v)v.currentTime=Math.max(0,v.currentTime-30)")

    def _on_seek(self, offset: float) -> None:
        self._js(f"const v=document.querySelector('video');"
                 f"if(v)v.currentTime=Math.max(0,Math.min(v.duration,"
                 f"v.currentTime+{offset}))")

    def _on_set_position(self, position: float) -> None:
        self._js(f"const v=document.querySelector('video');if(v)v.currentTime={position}")

    def _on_set_volume_mpris(self, volume: float) -> None:
        self._js(f"const v=document.querySelector('video');if(v)v.volume={volume}")

    def _on_next_episode(self) -> None:
        self._js("const b=document.querySelector('[data-uia=next-episode]');"
                 "if(b)b.click()")

    def _on_previous_episode(self) -> None:
        pass

    # -- Window mode toggles ------------------------------------------------

    def _toggle_fullscreen(self) -> None:
        if self.isFullScreen():
            self.showNormal()
            if self._was_maximized_before_fullscreen:
                self.showMaximized()
        else:
            self._was_maximized_before_fullscreen = self.isMaximized()
            self.showFullScreen()

    def _toggle_pip(self) -> None:
        if self._pip_window and self._pip_window.isVisible():
            self._pip_window.close()
            self._pip_window = None
            self._show_from_tray()
        else:
            if not self._browser_view:
                return
            self._pip_window = PictureInPictureWindow(self._browser_view)
            self._pip_window.set_content(self._browser_view)
            self._pip_window.closed.connect(self._on_pip_closed)
            self._pip_window.show()
            self.hide()

    def _on_pip_closed(self) -> None:
        self._pip_window = None
        self._show_from_tray()

    def _toggle_always_on_top(self) -> None:
        self._always_on_top = not self._always_on_top
        f = self.windowFlags()
        op = Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(f | op if self._always_on_top else f & ~op)
        self.show()

    def _show_from_tray(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    # -- Misc actions -------------------------------------------------------

    def _on_reload(self) -> None:
        self._browser.reload()

    def _on_dev_tools(self) -> None:
        self._browser.toggle_dev_tools()

    def _on_open_downloads(self) -> None:
        pass

    def _on_open_settings(self) -> None:
        from app.settings_dialog import SettingsDialog
        SettingsDialog(self).exec()

    def _on_quit(self) -> None:
        self._save_state()
        self._mpris.stop()
        QApplication.quit()

    def _on_update_available(self, version: str, url: str) -> None:
        log.info("Update available: %s", version)

    # -- Qt events ----------------------------------------------------------

    def closeEvent(self, event: QCloseEvent) -> None:
        self._save_state()
        if self._tray.is_available:
            event.ignore()
            self.hide()
        else:
            self._mpris.stop()
            event.accept()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if not self.isMaximized() and not self.isFullScreen():
            settings.set("window", "width", self.width())
            settings.set("window", "height", self.height())

    def moveEvent(self, event) -> None:
        super().moveEvent(event)
        if not self.isMaximized() and not self.isFullScreen():
            settings.set("window", "x", self.x())
            settings.set("window", "y", self.y())

    # -- Properties ---------------------------------------------------------

    @property
    def browser(self) -> NetflixBrowser:
        return self._browser

    @property
    def tray_manager(self) -> SystemTrayManager:
        return self._tray

    @property
    def notification_manager(self) -> NotificationManager:
        return self._notifications

    @property
    def download_manager(self) -> DownloadManager:
        return self._downloads
