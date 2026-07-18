from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from app.utils.config import CONFIG_DIR

SETTINGS_FILE = CONFIG_DIR / "settings.json"

DEFAULT_SETTINGS: Dict[str, Any] = {
    "general": {
        "launch_minimized": False,
        "start_page": "https://www.netflix.com",
        "single_instance": True,
        "auto_reconnect": True,
        "offline_mode": False,
    },
    "appearance": {
        "dark_mode": "system",
        "accent_color": None,
        "rounded_corners": True,
        "compact_mode": False,
        "show_tray_icon": True,
        "font_size": "normal",
    },
    "downloads": {
        "directory": "",
        "max_parallel": 3,
        "bandwidth_limit": 0,
        "notify_completion": True,
    },
    "profiles": {
        "current": "Default",
        "list": ["Default"],
    },
    "performance": {
        "hardware_acceleration": True,
        "memory_cache_size": 256,
        "disk_cache_size": 512,
        "lazy_loading": True,
    },
    "privacy": {
        "use_keyring": True,
        "clear_cache_on_exit": False,
        "do_not_track": True,
        "save_cookies": True,
    },
    "shortcuts": {
        "open_netflix": "Ctrl+Shift+N",
        "play_pause": "Ctrl+Shift+P",
        "mute": "Ctrl+Shift+M",
        "fullscreen": "Ctrl+Shift+F",
        "picture_in_picture": "Ctrl+Shift+I",
        "always_on_top": "Ctrl+Shift+T",
        "reload": "Ctrl+Shift+R",
        "dev_tools": "Ctrl+Shift+D",
    },
    "window": {
        "width": 1280,
        "height": 720,
        "x": -1,
        "y": -1,
        "maximized": False,
        "fullscreen": False,
    },
}


class Settings:
    def __init__(self) -> None:
        self._data: Dict[str, Any] = {}
        self._dirty = False
        self._load()

    def _load(self) -> None:
        try:
            if SETTINGS_FILE.exists():
                raw = SETTINGS_FILE.read_text()
                self._data = json.loads(raw)
        except (json.JSONDecodeError, OSError):
            self._data = {}
        self._merge_defaults()

    def _merge_defaults(self) -> None:
        for section, values in DEFAULT_SETTINGS.items():
            if section not in self._data:
                self._data[section] = {}
            for key, default in values.items():
                if key not in self._data[section]:
                    self._data[section][key] = default

    def _save(self) -> None:
        if not self._dirty:
            return
        try:
            SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
            SETTINGS_FILE.write_text(
                json.dumps(self._data, indent=2, ensure_ascii=False)
            )
            self._dirty = False
        except OSError:
            pass

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self._data.get(section, {}).get(key, default)

    def set(self, section: str, key: str, value: Any) -> None:
        if section not in self._data:
            self._data[section] = {}
        if self._data[section].get(key) != value:
            self._data[section][key] = value
            self._dirty = True
            self._save()

    def get_section(self, section: str) -> Dict[str, Any]:
        return dict(self._data.get(section, {}))

    def set_section(self, section: str, values: Dict[str, Any]) -> None:
        self._data[section] = values
        self._dirty = True
        self._save()

    def reset(self) -> None:
        self._data = {}
        self._merge_defaults()
        self._dirty = True
        self._save()

    def export_to(self, path: str | Path) -> None:
        dest = Path(path)
        shutil.copy2(SETTINGS_FILE, dest)

    def import_from(self, path: str | Path) -> bool:
        src = Path(path)
        if not src.exists():
            return False
        try:
            raw = src.read_text()
            imported = json.loads(raw)
            self._data.update(imported)
            self._merge_defaults()
            self._dirty = True
            self._save()
            return True
        except (json.JSONDecodeError, OSError):
            return False

    def get_all(self) -> Dict[str, Any]:
        return dict(self._data)

    @property
    def is_dark_mode(self) -> bool:
        from app.utils.platform import is_dark_mode
        setting = self.get("appearance", "dark_mode", "system")
        if setting == "dark":
            return True
        if setting == "light":
            return False
        return is_dark_mode()

    def flush(self) -> None:
        self._save()


settings = Settings()
