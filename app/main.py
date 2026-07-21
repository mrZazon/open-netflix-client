from __future__ import annotations

import argparse
import logging
import os
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


def _find_cdm_so(cdm_path_override: str | None = None) -> str | None:
    from pathlib import Path

    if cdm_path_override:
        p = Path(cdm_path_override)
        if p.is_file():
            return str(p)
        if p.is_dir() and (p / "libwidevinecdm.so").is_file():
            return str(p / "libwidevinecdm")

    from app.utils.widevine import find_system_cdm

    cdm_dir = find_system_cdm()
    if cdm_dir:
        so = Path(cdm_dir) / "libwidevinecdm.so"
        if so.is_file():
            return str(so)
    return None


def _set_widevine_flag(cdm_so_path: str) -> None:
    flag = f"--widevine-path={cdm_so_path}"
    existing = os.environ.get("QTWEBENGINE_CHROMIUM_FLAGS", "")
    if flag not in existing:
        combined = f"{existing} {flag}".strip()
        os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = combined
    log.info("Widevine flag set: %s", flag)


def _configure_widevine(cdm_path_override: str | None = None) -> bool:
    cdm_so = _find_cdm_so(cdm_path_override)
    if cdm_so:
        _set_widevine_flag(cdm_so)
        return True
    return False


def _ensure_widevine(cdm_path_override: str | None = None) -> None:
    if _configure_widevine(cdm_path_override):
        return

    from PySide6.QtWidgets import (
        QDialog, QVBoxLayout, QLabel, QProgressBar,
    )
    from PySide6.QtGui import QFont
    from PySide6.QtCore import Qt, QThread, Signal as QtSignal

    dialog = QDialog()
    dialog.setWindowTitle("Netflix Client")
    dialog.setFixedSize(420, 180)
    dialog.setWindowFlags(
        Qt.WindowType.Dialog | Qt.WindowType.CustomizeWindowHint
        | Qt.WindowType.WindowTitleHint
    )
    dialog.setStyleSheet("""
        QDialog { background: #141414; }
        QLabel { color: #999; font-size: 12px; }
    """)

    layout = QVBoxLayout(dialog)
    layout.setContentsMargins(24, 24, 24, 24)
    layout.setSpacing(12)

    title = QLabel("Netflix Client")
    title.setStyleSheet(
        "color: #e50914; font-size: 18px; font-weight: bold;"
    )
    title.setFont(QFont("sans-serif", 18, QFont.Weight.Bold))
    layout.addWidget(title)

    status = QLabel("Preparing DRM component...")
    status.setFont(QFont("sans-serif", 11))
    layout.addWidget(status)

    progress = QProgressBar()
    progress.setRange(0, 100)
    progress.setValue(0)
    progress.setTextVisible(True)
    progress.setStyleSheet("""
        QProgressBar {
            background: #333; border: none; border-radius: 4px;
            height: 20px; color: #fff; font-size: 11px;
        }
        QProgressBar::chunk {
            background: #e50914; border-radius: 4px;
        }
    """)
    layout.addWidget(progress)

    detail = QLabel("Downloading Google Chrome (~100 MB)...")
    detail.setStyleSheet("color: #666; font-size: 10px;")
    detail.setFont(QFont("sans-serif", 10))
    layout.addWidget(detail)

    dialog.show()
    QApplication.processEvents()

    class CdmWorker(QThread):
        progress = QtSignal(int, int)
        status = QtSignal(str, str)
        done = QtSignal(str)

        def run(self) -> None:
            def on_progress(downloaded: int, total: int) -> None:
                pct = int(downloaded * 80 / total)
                self.progress.emit(pct, 100)
                mb = downloaded / (1024 * 1024)
                tb = total / (1024 * 1024)
                self.status.emit(
                    "Downloading Google Chrome...",
                    f"{mb:.1f} / {tb:.1f} MB",
                )

            self.status.emit("Downloading Google Chrome...", "")
            from app.utils.widevine import setup_widevine
            path = setup_widevine(progress_cb=on_progress)
            self.progress.emit(90, 100)
            self.status.emit("Extracting DRM component...", "")
            self.done.emit(path or "")

    worker = CdmWorker()
    worker.progress.connect(lambda v, m: progress.setValue(v))

    def _on_status(s: str, d: str) -> None:
        status.setText(s)
        if d:
            detail.setText(d)

    worker.status.connect(_on_status)

    result = [""]
    worker.done.connect(lambda p: result.__setitem__(0, p))
    worker.start()

    while worker.isRunning():
        QApplication.processEvents()
        worker.wait(50)

    progress.setValue(100)
    status.setText("Done!")
    detail.setText("")
    QApplication.processEvents()

    import time
    time.sleep(0.3)
    dialog.close()

    cdm_dir = result[0]
    if cdm_dir:
        cdm_so = os.path.join(cdm_dir, "libwidevinecdm.so")
        if os.path.isfile(cdm_so):
            _set_widevine_flag(cdm_so)
            log.info("Widevine CDM installed: %s", cdm_so)
        else:
            log.warning("CDM dir set but .so not found: %s", cdm_dir)
    else:
        log.warning("Widevine CDM install failed. DRM will not work.")


def _configure_webengine(args: argparse.Namespace) -> None:
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

    is_snap = os.environ.get("SNAP") is not None
    if is_snap:
        _clear_webengine_if_needed()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app.setAttribute(
        Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True
    )

    _ensure_widevine(args.widevine_cdm_path)

    if args.profile:
        settings.set("profiles", "current", args.profile)

    window = MainWindow()

    if settings.get("general", "launch_minimized", False):
        window.hide()

    signal.signal(signal.SIGINT, signal.SIG_DFL)

    exit_code = app.exec()
    settings.flush()
    sys.exit(exit_code)


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
