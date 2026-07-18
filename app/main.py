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
    return parser.parse_args()


def configure_qt() -> None:
    QApplication.setApplicationName(APP_NAME)
    QApplication.setOrganizationName(ORG_NAME)
    QApplication.setApplicationDisplayName("Netflix Client")
    QApplication.setDesktopFileName("netflix-client")


def run(args: argparse.Namespace) -> None:
    if settings.get("general", "single_instance", True):
        SingleInstance()

    configure_qt()

    app = QApplication(sys.argv)
    app.setAttribute(Qt.ApplicationAttribute.AA_UseHighDpiPixmaps, True)
    app.setAttribute(Qt.ApplicationAttribute.AA_DontCreateNativeWidgetSiblings, True)

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
