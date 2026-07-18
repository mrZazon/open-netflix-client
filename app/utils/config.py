from __future__ import annotations

import os
from pathlib import Path
from typing import TYPE_CHECKING

from platformdirs import PlatformDirs

if TYPE_CHECKING:
    from PySide6.QtGui import QIcon

_snap_data = os.environ.get("SNAP_USER_DATA", "")
_snap_common = os.environ.get("SNAP_USER_COMMON", "")
_is_snap = bool(os.environ.get("SNAP"))

if _is_snap and _snap_common:
    DIRS = None
    CONFIG_DIR = Path(_snap_common) / "config"
    DATA_DIR = Path(_snap_common) / "data"
    CACHE_DIR = Path(_snap_common) / "cache"
    LOG_DIR = Path(_snap_common) / "log"
else:
    DIRS = PlatformDirs("netflix-client", "netflix-client")
    CONFIG_DIR = Path(DIRS.user_config_dir)
    DATA_DIR = Path(DIRS.user_data_dir)
    CACHE_DIR = Path(DIRS.user_cache_dir)
    LOG_DIR = Path(DIRS.user_log_dir)

PROFILES_DIR = DATA_DIR / "profiles"
DOWNLOADS_DIR = Path.home() / "Videos" / "Netflix"
COOKIES_DIR = DATA_DIR / "cookies"
CACHE_ICONS_DIR = CACHE_DIR / "icons"
LOG_FILE = LOG_DIR / "netflix-client.log"

NETFLIX_URL = "https://www.netflix.com"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

APP_NAME = "Netflix Client"
ORG_NAME = "netflix-client"
APP_VERSION = "1.0.6"


def ensure_dirs() -> None:
    for d in (CONFIG_DIR, DATA_DIR, CACHE_DIR, LOG_DIR, PROFILES_DIR,
              DOWNLOADS_DIR, COOKIES_DIR, CACHE_ICONS_DIR):
        d.mkdir(parents=True, exist_ok=True)


def asset_path(name: str) -> Path:
    return Path(__file__).resolve().parent.parent / "assets" / name


def get_app_icon() -> QIcon:
    from PySide6.QtGui import QIcon
    theme_icon = QIcon.fromTheme("netflix-client")
    if not theme_icon.isNull():
        return theme_icon
    png_path = str(asset_path("icon.png"))
    return QIcon(png_path)
