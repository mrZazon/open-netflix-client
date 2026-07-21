from __future__ import annotations

import json
import logging
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

CDM_FILENAME = "libwidevinecdm.so"
MANIFEST_FILENAME = "manifest.json"
CHROME_DEB_URL = (
    "https://dl.google.com/linux/direct/"
    "google-chrome-stable_current_amd64.deb"
)
WIDEVINE_INTERNAL_DIR = "opt/google/chrome/WidevineCdm"


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
    if env_path and os.path.isdir(env_path):
        return (Path(env_path) / CDM_FILENAME).is_file()
    return find_system_cdm() is not None


def find_system_cdm() -> str | None:
    home = os.path.expanduser("~")

    candidates = [
        _user_cdm_dir(),
        Path(
            f"/opt/google/chrome/WidevineCdm"
            f"/_platform_specific/{_arch_suffix()}"
        ),
        Path("/opt/google/chrome/WidevineCdm"),
        Path("/opt/google/chrome"),
        Path("/usr/lib/chromium"),
        Path("/usr/lib/chromium-browser"),
        Path("/usr/lib64/chromium-browser"),
        Path(f"{home}/.local/lib"),
        Path(f"{home}/.local/lib/chromium"),
    ]

    if snap := os.environ.get("SNAP"):
        candidates.insert(0, Path(snap) / "extra")
        candidates.insert(1, Path(os.environ.get("SNAP_USER_DATA", "")))
        candidates.insert(2, Path(os.environ.get("SNAP_USER_COMMON", "")))

    for cdm_dir in candidates:
        if (cdm_dir / CDM_FILENAME).is_file():
            return str(cdm_dir)

    return None


def _download_chrome_deb(dest: Path, progress_cb=None) -> bool:
    log.info("Downloading Google Chrome deb...")
    try:
        req = urllib.request.Request(
            CHROME_DEB_URL,
            headers={"User-Agent": "Mozilla/5.0"},
        )
        with urllib.request.urlopen(req, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(65536)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if progress_cb and total > 0:
                        progress_cb(downloaded, total)
        log.info("Downloaded Chrome deb: %s", dest)
        return True
    except Exception as exc:
        log.warning("Failed to download Chrome deb: %s", exc)
        return False


def _extract_cdm_from_deb(deb_path: Path, dest: Path) -> bool:
    log.info("Extracting CDM from Chrome deb...")
    cdm_dir = dest.parent

    with tempfile.TemporaryDirectory() as tmp:
        cdm_pattern = "*/" + CDM_FILENAME
        manifest_pattern = "*/" + MANIFEST_FILENAME

        methods = [
            [
                "dpkg-deb", "--fsys-tarfile", str(deb_path),
            ],
            _ar_extract_data_tar(deb_path, tmp),
        ]

        for method in methods:
            if method is None:
                continue

            if isinstance(method, list) and method[0] == "_ar_done":
                tar_file = method[1]
                if tar_file is None:
                    continue
                for decompress_cmd in (
                    ["xz", "-dk", tar_file],
                    ["unxz", "-k", tar_file],
                ):
                    try:
                        log.info("Decompressing with: %s", " ".join(decompress_cmd))
                        subprocess.run(
                            decompress_cmd, check=True, timeout=60,
                            capture_output=True,
                        )
                        decompressed = Path(tar_file).with_suffix("")
                        if decompressed.is_file():
                            _tar_extract_cdm(
                                str(decompressed), cdm_dir, tmp
                            )
                            if (dest).is_file():
                                return True
                    except (subprocess.CalledProcessError, FileNotFoundError,
                            subprocess.TimeoutExpired) as exc:
                        log.info("Decompress failed: %s", exc)
                continue

            try:
                log.info("Trying dpkg-deb piped extraction...")
                result = subprocess.run(
                    method, capture_output=True, check=True, timeout=120,
                )
                tar_file = os.path.join(tmp, "data.tar")
                with open(tar_file, "wb") as f:
                    f.write(result.stdout)
                _tar_extract_cdm(tar_file, cdm_dir, tmp)
                if dest.is_file():
                    return True
            except (subprocess.CalledProcessError, FileNotFoundError,
                    subprocess.TimeoutExpired) as exc:
                log.info("Method failed: %s", exc)

        log.warning("All extraction methods failed")
        return False


def _ar_extract_data_tar(deb_path: Path, tmp: str) -> list | None:
    try:
        with open(deb_path, "rb") as f:
            magic = f.read(8)
            if magic != b"!<arch>\n":
                log.warning("Not a valid deb file")
                return None

            for _ in range(10):
                hdr = f.read(60)
                if len(hdr) < 60:
                    return None
                name = hdr[:16].decode("ascii", errors="replace").strip()
                size = int(hdr[48:58].decode("ascii").strip())
                data = f.read(size)
                pad = (size + 1) & ~1
                if pad > size:
                    f.read(pad - size)
                if name.startswith("data.tar"):
                    tar_file = os.path.join(tmp, name.rstrip("/"))
                    with open(tar_file, "wb") as f2:
                        f2.write(data)
                    log.info("Extracted %s from ar (%d bytes)", name, size)
                    return ["_ar_done", tar_file]

    except Exception as exc:
        log.warning("ar parse failed: %s", exc)
    return None


def _tar_extract_cdm(
    tar_file: str, cdm_dir: Path, extract_dir: str
) -> None:
    cdm_found = False
    manifest_found = False

    for fmt in (None, "r:xz", "r:zst", "r:gz"):
        try:
            import tarfile
            kw = {"name": tar_file}
            if fmt is not None:
                kw["mode"] = fmt
            with tarfile.open(**kw) as tar:
                for member in tar.getmembers():
                    if member.name.endswith(CDM_FILENAME):
                        tar.extract(member, path=extract_dir)
                        extracted = (
                            Path(extract_dir) / member.name.lstrip("./")
                        )
                        cdm_dir.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(
                            str(extracted), str(cdm_dir / CDM_FILENAME)
                        )
                        log.info("CDM extracted: %s", cdm_dir / CDM_FILENAME)
                        cdm_found = True
                    if (WIDEVINE_INTERNAL_DIR in member.name
                            and member.name.endswith(MANIFEST_FILENAME)):
                        tar.extract(member, path=extract_dir)
                        extracted = (
                            Path(extract_dir) / member.name.lstrip("./")
                        )
                        shutil.copy2(
                            str(extracted),
                            str(cdm_dir / MANIFEST_FILENAME),
                        )
                        log.info("Manifest extracted: %s", cdm_dir / MANIFEST_FILENAME)
                        manifest_found = True
                if cdm_found:
                    if not manifest_found:
                        _write_default_manifest(cdm_dir)
                    return
        except Exception as exc:
            log.debug("tarfile format %s failed: %s", fmt, exc)
            continue

    if not cdm_found:
        for p in Path(extract_dir).rglob(CDM_FILENAME):
            cdm_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(p), str(cdm_dir / CDM_FILENAME))
            log.info("CDM found via glob: %s", cdm_dir / CDM_FILENAME)
            cdm_found = True
            break

    if cdm_found and not manifest_found:
        for p in Path(extract_dir).rglob(MANIFEST_FILENAME):
            if WIDEVINE_INTERNAL_DIR in str(p):
                shutil.copy2(
                    str(p), str(cdm_dir / MANIFEST_FILENAME)
                )
                log.info("Manifest found via glob: %s", cdm_dir / MANIFEST_FILENAME)
                manifest_found = True
                break

    if cdm_found and not manifest_found:
        _write_default_manifest(cdm_dir)


def _write_default_manifest(cdm_dir: Path) -> None:
    manifest = {
        "manifest_version": 2,
        "version": "0.0.0.0",
        "x-cdm-codecs": "vp8,vp09,avc1,av01",
        "x-cdm-module-versions": "4",
        "x-cdm-interface-versions": "10",
        "x-cdm-host-versions": "10",
        "x-cdm-path": ".",
    }
    path = cdm_dir / MANIFEST_FILENAME
    path.write_text(json.dumps(manifest))
    log.info("Default manifest written to: %s", path)


def setup_widevine(progress_cb=None) -> str | None:
    existing = find_system_cdm()
    if existing:
        cdm_dir = _user_cdm_dir()
        target = cdm_dir / CDM_FILENAME
        if existing == str(cdm_dir):
            if not (cdm_dir / MANIFEST_FILENAME).is_file():
                _write_default_manifest(cdm_dir)
            return existing
        cdm_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(str(Path(existing) / CDM_FILENAME), str(target))
        manifest_src = Path(existing) / MANIFEST_FILENAME
        manifest_dst = cdm_dir / MANIFEST_FILENAME
        if manifest_src.is_file():
            shutil.copy2(str(manifest_src), str(manifest_dst))
        elif not manifest_dst.is_file():
            _write_default_manifest(cdm_dir)
        log.info("CDM copied to: %s", cdm_dir)
        return str(cdm_dir)

    cdm_dir = _user_cdm_dir()
    cdm_dir.mkdir(parents=True, exist_ok=True)
    target = cdm_dir / CDM_FILENAME

    log.info("Widevine CDM not found. Auto-installing from Chrome deb...")

    with tempfile.TemporaryDirectory() as tmp:
        deb_path = Path(tmp) / "google-chrome-stable.deb"
        if _download_chrome_deb(deb_path, progress_cb):
            if _extract_cdm_from_deb(deb_path, target):
                return str(cdm_dir)

    log.error(
        "Could not install Widevine CDM.\n"
        "  Install Google Chrome manually, then copy the CDM:\n"
        "    sudo apt install google-chrome-stable\n"
        "    cp /opt/google/chrome/WidevineCdm/_platform_specific/"
        "linux_x64/libwidevinecdm.so %s/",
        cdm_dir,
    )
    return None
