from __future__ import annotations

import os
import configparser
import subprocess
from typing import NamedTuple

DESKTOP_ENV_UNKNOWN = "unknown"
DESKTOP_ENV_KDE = "kde"
DESKTOP_ENV_GNOME = "gnome"
DESKTOP_ENV_SWAY = "sway"
DESKTOP_ENV_HYPRLAND = "hyprland"
DESKTOP_ENV_WAYLAND = "wayland"


class DesktopInfo(NamedTuple):
    desktop: str
    session_type: str
    is_kde: bool
    is_gnome: bool
    is_wayland: bool


def detect_desktop() -> DesktopInfo:
    xdg_current = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
    session_type = os.environ.get("XDG_SESSION_TYPE", "x11").lower()
    is_wayland = session_type == "wayland"
    is_kde = "kde" in xdg_current
    is_gnome = "gnome" in xdg_current
    desktop = xdg_current if xdg_current else DESKTOP_ENV_UNKNOWN
    return DesktopInfo(desktop, session_type, is_kde, is_gnome, is_wayland)


def kde_color_scheme() -> str | None:
    try:
        result = subprocess.run(
            ["kreadconfig5", "--group", "General", "--key", "ColorScheme",
             "--file", "kdeglobals"],
            capture_output=True, text=True, timeout=2
        )
        return result.stdout.strip()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    globals_path = os.path.expanduser("~/.config/kdeglobals")
    if os.path.exists(globals_path):
        config = configparser.ConfigParser()
        config.read(globals_path)
        if config.has_option("General", "ColorScheme"):
            return config.get("General", "ColorScheme")
    return None


def kde_accent_color() -> str | None:
    globals_path = os.path.expanduser("~/.config/kdeglobals")
    if os.path.exists(globals_path):
        config = configparser.ConfigParser()
        config.read(globals_path)
        if config.has_option("General", "AccentColor"):
            return config.get("General", "AccentColor")
    return None


def gnome_dark_mode() -> bool | None:
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface",
             "color-scheme"],
            capture_output=True, text=True, timeout=2
        )
        return "dark" in result.stdout.strip().lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def is_dark_mode() -> bool:
    info = detect_desktop()
    if info.is_kde:
        scheme = kde_color_scheme()
        if scheme:
            return "dark" in scheme.lower()
    if info.is_gnome:
        result = gnome_dark_mode()
        if result is not None:
            return result
    try:
        result = subprocess.run(
            ["gsettings", "get", "org.gnome.desktop.interface",
             "gtk-theme"],
            capture_output=True, text=True, timeout=2
        )
        return "dark" in result.stdout.strip().lower()
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return False
