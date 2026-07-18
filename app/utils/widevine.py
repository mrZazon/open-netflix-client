from __future__ import annotations

import glob
import logging
import os
import platform
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

CDM_FILENAME = "libwidevinecdm.so"
CHROME_DEB_URL = (
    "https://dl.google.com/linux/direct/"
    "google-chrome-stable_current_amd64.deb"
)
CDM_INTERNAL_PATH = "opt/google/chrome/WidevineCdm/_platform_specific"


def _user_cdm_dir() -> Path:
    from app.utils.config import DATA_DIR
    return DATA_DIR / "widevine"


def _arch_suffix() -> str:
    machine = platform.machine()
    mapping = {
        "x86_64": "linux_x64",
        "amd64": "linux_x64",
        "aarch64": "linux_arm64",
        "arm64": "linux_arm64",
    }
    return mapping.get(machine, "linux_x64")


def is_cdm_available() -> bool:
    env_path = os.environ.get("QTWEBENGINE_WIDEVINE_CDM_PATH", "")
    if env_path and os.path.isfile(env_path):
        return True
    return find_system_cdm() is not None


def find_system_cdm() -> str | None:
    home = os.path.expanduser("~")
    arch = _arch_suffix()

    candidates = [
        _user_cdm_dir() / CDM_FILENAME,
        Path(f"/opt/google/chrome/WidevineCdm/_platform_specific/{arch}")
        / CDM_FILENAME,
        Path(f"/opt/google/chrome/{CDM_FILENAME}"),
        Path(f"/usr/lib/chromium/{CDM_FILENAME}"),
        Path(f"/usr/lib/chromium-browser/{CDM_FILENAME}"),
        Path(f"/usr/lib64/chromium-browser/{CDM_FILENAME}"),
        Path(f"{home}/.local/lib/{CDM_FILENAME}"),
        Path(f"{home}/.local/lib/chromium/{CDM_FILENAME}"),
    ]

    if snap := os.environ.get("SNAP"):
        candidates.insert(
            0, Path(snap) / "extra" / CDM_FILENAME
        )
        candidates.insert(
            1, Path(os.environ.get("SNAP_USER_DATA", "")) / CDM_FILENAME
        )
        candidates.insert(
            2,
            Path(os.environ.get("SNAP_USER_COMMON", "")) / CDM_FILENAME,
        )

    for path in candidates:
        if path.is_file():
            return str(path)

    for pattern in [
        str(_user_cdm_dir() / f"{CDM_FILENAME}.*"),
        f"/usr/lib/{CDM_FILENAME}.*",
        f"/usr/lib64/{CDM_FILENAME}.*",
    ]:
        matches = sorted(
            glob.glob(pattern), key=os.path.getmtime, reverse=True
        )
        for match in matches:
            if os.path.isfile(match):
                return match

    return None


def _download_chrome_deb(dest: Path) -> bool:
    log.info("Downloading Google Chrome deb...")
    try:
        req = urllib.request.Request(
            CHROME_DEB_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=60) as resp:
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
        log.info("Downloaded Chrome deb: %s", dest)
        return True
    except Exception as exc:
        log.warning("Failed to download Chrome deb: %s", exc)
        return False


def _extract_cdm_from_deb(deb_path: Path, dest: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        log.info("Extracting CDM from Chrome deb...")
        try:
            result = subprocess.run(
                ["dpkg-deb", "--fsys-tarfile", str(deb_path)],
                capture_output=True,
                check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            log.info("dpkg-deb not available, trying manual extraction")
            return _extract_cdm_manual(deb_path, dest)

        tar_path = Path(tmp) / "data.tar"
        tar_path.write_bytes(result.stdout)

        for fmt in (None, "r:xz", "r:zst", "r:gz"):
            try:
                kw = {"name": tar_path} if fmt is None else {
                    "name": tar_path, "mode": fmt}
                with tarfile.open(**kw) as tar:
                    for member in tar.getmembers():
                        if member.name.endswith(CDM_FILENAME):
                            tar.extract(member, path=tmp)
                            extracted = Path(tmp) / member.name
                            dest.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copy2(str(extracted), str(dest))
                            log.info("CDM extracted to: %s", dest)
                            return True
            except tarfile.TarError:
                continue

        return _extract_cdm_manual(deb_path, dest)


def _extract_cdm_manual(deb_path: Path, dest: Path) -> bool:
    with tempfile.TemporaryDirectory() as tmp:
        ctrl = Path(tmp) / "control.tar"
        data = Path(tmp) / "data.tar"

        with open(deb_path, "rb") as f:
            magic = f.read(8)
            if magic != b"!<arch>\n":
                log.warning("Not a valid deb file")
                return False
            f.read(2)  # date
            f.read(6)  # owner
            f.read(6)  # group
            f.read(10)  # mode
            f.read(10)  # size
            f.read(2)  # end magic
            ctrl_header = f.read(60)
            ctrl_size = int(ctrl_header[48:58].strip())
            ctrl.write_bytes(f.read(ctrl_size))
            pad = (ctrl_size + 1) & ~1
            f.read(pad - ctrl_size if pad > ctrl_size else 0)
            f.read(2)  # data end magic
            data_header = f.read(60)
            data_size = int(data_header[48:58].strip())
            data.write_bytes(f.read(data_size))

        try:
            with tarfile.open(data) as tar:
                for member in tar.getmembers():
                    if member.name.endswith(CDM_FILENAME):
                        tar.extract(member, path=tmp)
                        extracted = Path(tmp) / member.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(extracted), str(dest))
                        log.info("CDM extracted to: %s", dest)
                        return True
        except tarfile.TarError:
            pass

        try:
            with tarfile.open(data, "r:xz") as tar:
                for member in tar.getmembers():
                    if member.name.endswith(CDM_FILENAME):
                        tar.extract(member, path=tmp)
                        extracted = Path(tmp) / member.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(extracted), str(dest))
                        log.info("CDM extracted to: %s", dest)
                        return True
        except tarfile.TarError:
            pass

        try:
            with tarfile.open(data, "r:zst") as tar:
                for member in tar.getmembers():
                    if member.name.endswith(CDM_FILENAME):
                        tar.extract(member, path=tmp)
                        extracted = Path(tmp) / member.name
                        dest.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(str(extracted), str(dest))
                        log.info("CDM extracted to: %s", dest)
                        return True
        except tarfile.TarError:
            pass

    return False


def setup_widevine() -> str | None:
    existing = find_system_cdm()
    if existing:
        cdm_dir = _user_cdm_dir()
        target = cdm_dir / CDM_FILENAME
        if existing == str(target):
            return existing
        cdm_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(existing, str(target))
        log.info("CDM copied to: %s", target)
        return str(target)

    cdm_dir = _user_cdm_dir()
    cdm_dir.mkdir(parents=True, exist_ok=True)
    target = cdm_dir / CDM_FILENAME

    log.info("Widevine CDM not found. Auto-installing from Chrome deb...")

    with tempfile.TemporaryDirectory() as tmp:
        deb_path = Path(tmp) / "google-chrome-stable.deb"
        if _download_chrome_deb(deb_path):
            if _extract_cdm_from_deb(deb_path, target):
                return str(target)

    log.error(
        "Could not install Widevine CDM.\n"
        "  Install Google Chrome manually, then copy the CDM:\n"
        "    sudo apt install google-chrome-stable\n"
        "    cp /opt/google/chrome/WidevineCdm/_platform_specific/"
        "linux_x64/libwidevinecdm.so %s/",
        cdm_dir,
    )
    return None
