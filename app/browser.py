from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from PySide6.QtCore import QUrl, Signal, QTimer, QObject, Qt
from PySide6.QtWebEngineCore import (
    QWebEngineProfile,
    QWebEnginePage,
    QWebEngineSettings,
)
from PySide6.QtWebEngineWidgets import QWebEngineView

from app.utils.config import (
    NETFLIX_URL,
    USER_AGENT,
    PROFILES_DIR,
    CACHE_DIR,
)
from app.settings import settings

log = logging.getLogger(__name__)


class BrowserPage(QWebEnginePage):
    playback_state_changed = Signal(str)
    metadata_changed = Signal(dict)
    url_changed = Signal(str)

    def __init__(self, profile: QWebEngineProfile, parent: QObject | None = None) -> None:
        super().__init__(profile, parent)
        self._monitor = QTimer(self)
        self._monitor.setInterval(1500)
        self._monitor.timeout.connect(self._check_playback)
        self._monitor.start()
        self.loadFinished.connect(self._inject_hide_scrollbars)

    def _inject_hide_scrollbars(self) -> None:
        js = """
        (function() {
            const s = document.createElement('style');
            s.textContent = '::-webkit-scrollbar { display: none !important; }'
                + 'html { overflow: -moz-scrollbars-none; scrollbar-width: none; }'
                + 'body { overflow-y: auto; }';
            document.head.appendChild(s);
        })();
        """
        self.runJavaScript(js)

    def _check_playback(self) -> None:
        js = """
        (function() {
            const v = document.querySelector('video');
            if (!v) return JSON.stringify({state: 'none'});
            return JSON.stringify({
                state: v.paused ? 'paused' : 'playing',
                title: document.title,
                url: window.location.href,
                duration: v.duration || 0,
                position: v.currentTime || 0,
                muted: v.muted,
                volume: v.volume
            });
        })();
        """
        self.runJavaScript(js, self._on_playback_result)

    def _on_playback_result(self, result: Any) -> None:
        if not result:
            return
        try:
            data = json.loads(result) if isinstance(result, str) else result
        except (json.JSONDecodeError, TypeError):
            return
        state = data.get("state", "none")
        if state != "none":
            self.playback_state_changed.emit(state)
            self.metadata_changed.emit({
                "title": data.get("title", ""),
                "url": data.get("url", ""),
                "duration": data.get("duration", 0),
                "position": data.get("position", 0),
                "muted": data.get("muted", False),
                "volume": data.get("volume", 1.0),
            })

    def _on_url_changed(self, url: QUrl) -> None:
        self.url_changed.emit(url.toString())

    def javaScriptConsoleMessage(
        self, level: int, message: str, line: int, source: str
    ) -> None:
        if level != QWebEnginePage.JavaScriptConsoleMessageLevel.InfoMessageLevel:
            log.debug("JS [%s] %s:%d: %s", level, source, line, message)


class NetflixBrowser(QObject):
    profile_switched = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._profiles: Dict[str, QWebEngineProfile] = {}
        self._views: Dict[str, QWebEngineView] = {}
        self._pages: Dict[str, BrowserPage] = {}
        self._current_profile: str = ""
        self._current_view: QWebEngineView | None = None
        self._profile_names: list[str] = []

        self._load_profiles()

    def _load_profiles(self) -> None:
        names = settings.get("profiles", "list", ["Default"])
        current = settings.get("profiles", "current", "Default")
        self._profile_names = names
        if current not in names:
            current = names[0] if names else "Default"
        self._current_profile = current
        for name in names:
            self._get_or_create_profile(name)

    def _get_or_create_profile(self, name: str) -> QWebEngineProfile:
        if name not in self._profiles:
            profile_path = PROFILES_DIR / name
            profile = QWebEngineProfile(name, self)
            profile.setPersistentStoragePath(str(profile_path))
            profile.setPersistentCookiesPolicy(
                QWebEngineProfile.ForcePersistentCookies
            )
            profile.setHttpUserAgent(USER_AGENT)
            profile.setHttpCacheType(QWebEngineProfile.DiskHttpCache)
            settings_ = profile.settings()
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.LocalStorageEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.JavascriptEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.PluginsEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.AutoLoadImages, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.FullScreenSupportEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.ScreenCaptureEnabled, False
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.WebGLEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.ScrollAnimatorEnabled, True
            )
            settings_.setAttribute(
                QWebEngineSettings.WebAttribute.FocusOnNavigationEnabled, True
            )

            hw_accel = settings.get("performance", "hardware_acceleration", True)
            if not hw_accel:
                settings_.setAttribute(
                    QWebEngineSettings.WebAttribute.WebGLEnabled, False
                )
                settings_.setAttribute(
                    QWebEngineSettings.WebAttribute.Accelerated2dCanvasEnabled, False
                )

            if not settings.get("privacy", "save_cookies", True):
                profile.setPersistentCookiesPolicy(
                    QWebEngineProfile.NoPersistentCookies
                )

            self._profiles[name] = profile

        return self._profiles[name]

    def create_view(self, parent: QObject | None = None) -> QWebEngineView:
        profile = self._get_or_create_profile(self._current_profile)
        if self._current_profile in self._views:
            return self._views[self._current_profile]

        view = QWebEngineView(parent)
        page = BrowserPage(profile, view)
        page.url_changed.connect(self._on_url_changed)
        page.playback_state_changed.connect(self._on_playback_state_changed)
        page.metadata_changed.connect(self._on_metadata_changed)

        view.setPage(page)
        view.load(QUrl(NETFLIX_URL))
        view.setAttribute(Qt.WidgetAttribute.WA_AcceptTouchEvents, True)

        self._views[self._current_profile] = view
        self._pages[self._current_profile] = page
        self._current_view = view
        return view

    def switch_profile(self, name: str) -> QWebEngineView | None:
        if name not in self._profile_names:
            return None
        if name == self._current_profile:
            return self._current_view

        self._get_or_create_profile(name)
        self._current_profile = name
        settings.set("profiles", "current", name)

        if name in self._views:
            view = self._views[name]
        else:
            view = None

        self._current_view = view
        self.profile_switched.emit(name)
        return view

    def add_profile(self, name: str) -> None:
        if name in self._profile_names:
            return
        self._profile_names.append(name)
        self._get_or_create_profile(name)
        settings.set("profiles", "list", self._profile_names)

    def remove_profile(self, name: str) -> None:
        if name == "Default" or name not in self._profile_names:
            return
        self._profile_names.remove(name)
        if name in self._profiles:
            del self._profiles[name]
        if name in self._views:
            self._views[name].deleteLater()
            del self._views[name]
        if name in self._pages:
            del self._pages[name]
        if self._current_profile == name:
            self._current_profile = self._profile_names[0]
            settings.set("profiles", "current", self._current_profile)
        settings.set("profiles", "list", self._profile_names)

    @property
    def current_view(self) -> QWebEngineView | None:
        return self._current_view

    @property
    def current_page(self) -> BrowserPage | None:
        return self._pages.get(self._current_profile)

    @property
    def profile_names(self) -> list[str]:
        return list(self._profile_names)

    @property
    def current_profile_name(self) -> str:
        return self._current_profile

    def reload(self) -> None:
        if self._current_view:
            self._current_view.reload()

    def load_url(self, url: str) -> None:
        if self._current_view:
            self._current_view.load(QUrl(url))

    def toggle_dev_tools(self) -> None:
        if self._current_view:
            page = self._current_view.page()
            if page:
                page.setDevToolsPage(None)

    def clear_cache(self) -> None:
        for profile in self._profiles.values():
            profile.clearHttpCache()
        cache_path = CACHE_DIR / "webengine"
        if cache_path.exists():
            import shutil
            shutil.rmtree(cache_path)

    def run_javascript(self, js: str, callback: Callable | None = None) -> None:
        if self._current_view and self._current_view.page():
            self._current_view.page().runJavaScript(js, callback)

    def _on_url_changed(self, url: str) -> None:
        log.debug("URL changed: %s", url)

    def _on_playback_state_changed(self, state: str) -> None:
        log.debug("Playback state: %s", state)

    def _on_metadata_changed(self, metadata: dict) -> None:
        pass
