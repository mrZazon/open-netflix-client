from __future__ import annotations

import argparse
import logging
import signal
import sys

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.settings import settings
from app.utils.config import ensure_dirs, LOG_FILE, APP_NAME, ORG_NAME
from app.utils.singleton import SingleInstance
from app.window import MainWindow

log = logging.getLogger(__name__)


def setup_logging(debug: bool = False) -> None:
    ensure_dirs()
    level = logging.DEBUG if debug else logging.INFO
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    handlers = [
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler(sys.stderr),
    ]
    logging.basicConfig(level=level, format=fmt, handlers=handlers)
    logging.getLogger("PySide6").setLevel(logging.WARNING)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Native Netflix client for Linux"
    )
    parser.add_argument(
        "--debug", action="store_true", help="Enable debug logging"
    )
    parser.add_argument(
        "--no-sandbox", action="store_true",
        help="Disable WebEngine sandbox (not recommended)"
    )
    parser.add_argument(
        "--profile", type=str, default="",
        help="Start with a specific profile"
    )
    parser.add_argument(
        "--version", action="store_true", help="Show version and exit"
    )
    parser.add_argument(
        "--widevine-cdm-path", type=str, default="",
        help="Path to libwidevinecdm.so for DRM playback",
    )
    return parser.parse_args()


def configure_qt() -> None:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(ORG_NAME)
    QApplication.setApplicationDisplayName("Netflix Client")
    QApplication.setDesktopFileName("netflix-client")


def _configure_widevine(cdm_path_override: str | None = None) -> None:
    import os

    if os.environ.get("QTWEBENGINE_WIDEVINE_CDM_PATH"):
        log.debug(
            "Widevine CDM path already set: %s",
            os.environ["QTWEBENGINE_WIDEVINE_CDM_PATH"],
        )
        return True

    if cdm_path_override:
        if os.path.isfile(cdm_path_override):
            os.environ["QTWEBENGINE_WIDEVINE_CDM_PATH"] = cdm_path_override
            log.info("Widevine CDM (manual): %s", cdm_path_override)
            return True
        log.warning("Widevine CDM path not found: %s", cdm_path_override)

    from app.utils.widevine import find_system_cdm

    cdm_path = find_system_cdm()
    if cdm_path:
        os.environ["QTWEBENGINE_WIDEVINE_CDM_PATH"] = cdm_path
        log.info("Widevine CDM found: %s", cdm_path)
        return True

    return False


def _configure_webengine(args: argparse.Namespace) -> None:
    import os

    is_snap = os.environ.get("SNAP") is not None
    flags: list[str] = []

    if is_snap or args.no_sandbox:
        flags.append("--no-sandbox")

    if not settings.get("performance", "hardware_acceleration", True):
        flags.append("--disable-gpu")
        flags.append("--enable-unsafe-swiftshader")

    if is_snap:
        flags.append("--disable-gpu")
        flags.append("--enable-unsafe-swiftshader")

    if flags:
        existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
        combined = f"{existing} {' '.join(flags)}".strip()
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = combined

    if is_snap or args.no_sandbox:
        os.environ["QTWEBENGINE_DISABLE_SANDBOX"] = "1"


def _clear_webengine_if_needed() -> None:
    import os
    import shutil
    from app.utils.config import CACHE_DIR, DATA_DIR

    marker = DATA_DIR / ".webengine-cleared"
    snap_rev = os.environ.get("SNAP_REVISION", "")
    marker_content = f"{snap_rev}\n"

    if marker.exists() and marker.read_text() == marker_content:
        return

    webengine_cache = CACHE_DIR / "webengine"
    if webengine_cache.exists():
        shutil.rmtree(webengine_cache, ignore_errors=True)

    for child in DATA_DIR.glob("profiles/*/Cache"):
        shutil.rmtree(child, ignore_errors=True)
    for child in DATA_DIR.glob("profiles/*/GPUCache"):
        shutil.rmtree(child, ignore_errors=True)

    marker.write_text(marker_content)


def _strip_chromium_args() -> None:
    chromium_flags = {
        "--no-sandbox", "--disable-setuid-sandbox",
        "--disable-gpu-sandbox", "--disable-gpu",
        "--disable-software-rasterizer",
        "--enable-unsafe-swiftshader",
    }
    sys.argv = [a for a in sys.argv if a not in chromium_flags]


def run(args: argparse.Namespace) -> None:
    if settings.get("general", "single_instance", True):
        SingleInstance()

    configure_qt()
    _configure_webengine(args)
    _strip_chromium_args()

    import os
    is_snap = os.environ.get("SNAP") is not None
    if is_snap:
        _clear_webengine_if_needed()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)

    if args.profile:
        settings.set("profiles", "current", args.profile)

    cdm_ready = _configure_widevine(args.widevine_cdm_path)

    window = MainWindow()

    if not cdm_ready:
        _start_widevine_install(window)

    if settings.get("general", "launch_minimized", False):
        window.hide()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    exit_code = app.exec()
    settings.flush()
    sys.exit(exit_code)


def _start_widevine_install(window: "MainWindow") -> None:
    import os
    from PySide6.QtCore import QThread, Signal as QtSignal

    class CdmInstaller(QThread):
        finished = QtSignal(str)

        def run(self) -> None:
            from app.utils.widevine import setup_widevine
            path = setup_widevine()
            self.finished.emit(path or "")

    def _on_cdm_ready(path: str) -> None:
        if path:
            os.environ["QTWEBENGINE_WIDEVINE_CDM_PATH"] = path
            log.info("Widevine CDM installed: %s", path)
            window.browser.reload()
        else:
            log.warning(
                "Widevine CDM install failed. DRM will not work."
            )

    installer = CdmInstaller(window)
    installer.finished.connect(_on_cdm_ready)
    installer.start()
    log.info("Widevine CDM installing in background...")


def main() -> None:
    args = parse_args()
    if args.version:
        from app.utils.config import APP_VERSION
        print(f"Netflix Client v{APP_VERSION}")
        sys.exit(0)

    setup_logging(args.debug)
    log.info("Starting Netflix Client")
    run(args)


if __name__ == "__main__":
    main()
