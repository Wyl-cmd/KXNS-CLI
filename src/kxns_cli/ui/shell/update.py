from __future__ import annotations

import asyncio
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import zipfile
from enum import Enum, auto
from pathlib import Path

import aiohttp

from kxns_cli.share import get_share_dir
from kxns_cli.ui.shell.console import console
from kxns_cli.utils.aiohttp import new_client_session
from kxns_cli.utils.logging import logger

GITHUB_REPO = "Wyl-cmd/kxns-cli"
GITHUB_API_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
GITHUB_RELEASES_URL = f"https://github.com/{GITHUB_REPO}/releases"

_IS_WINDOWS = sys.platform == "win32"


def _get_install_dir() -> Path:
    if _IS_WINDOWS:
        local_app_data = os.getenv("LOCALAPPDATA")
        if local_app_data:
            return Path(local_app_data) / "Programs" / "kxns-cli"
        return Path.home() / "AppData" / "Local" / "Programs" / "kxns-cli"
    return Path.home() / ".local" / "bin"


INSTALL_DIR = _get_install_dir()


class UpdateResult(Enum):
    UPDATE_AVAILABLE = auto()
    UPDATED = auto()
    UP_TO_DATE = auto()
    FAILED = auto()
    UNSUPPORTED = auto()


_UPDATE_LOCK = asyncio.Lock()


def semver_tuple(version: str) -> tuple[int, int, int]:
    v = version.strip()
    if v.startswith("v"):
        v = v[1:]
    match = re.match(r"^(\d+)\.(\d+)(?:\.(\d+))?", v)
    if not match:
        return (0, 0, 0)
    major = int(match.group(1))
    minor = int(match.group(2))
    patch = int(match.group(3) or 0)
    return (major, minor, patch)


def _detect_target() -> str | None:
    sys_name = platform.system()
    mach = platform.machine()
    if mach in ("x86_64", "amd64", "AMD64"):
        arch = "x86_64"
    elif mach in ("arm64", "aarch64"):
        arch = "aarch64"
    else:
        logger.error("Unsupported architecture: {mach}", mach=mach)
        return None
    if sys_name == "Darwin":
        os_name = "apple-darwin"
    elif sys_name == "Linux":
        os_name = "unknown-linux-gnu"
    elif sys_name == "Windows":
        os_name = "pc-windows-msvc"
    else:
        logger.error("Unsupported OS: {sys_name}", sys_name=sys_name)
        return None
    return f"{arch}-{os_name}"


async def _get_latest_release(session: aiohttp.ClientSession) -> dict | None:
    try:
        headers = {"Accept": "application/vnd.github+json"}
        async with session.get(GITHUB_API_URL, headers=headers) as resp:
            resp.raise_for_status()
            return await resp.json()
    except aiohttp.ClientError:
        logger.exception("Failed to get latest release from GitHub:")
        return None


def _find_asset_url(release: dict, target: str) -> tuple[str | None, str | None]:
    for asset in release.get("assets", []):
        name = asset.get("name", "")
        if target not in name:
            continue
        if name.endswith(".tar.gz") or name.endswith(".zip"):
            if "-onedir" in name:
                continue
            return asset.get("browser_download_url"), name
    return None, None


def _binary_name() -> str:
    return "kxns.exe" if _IS_WINDOWS else "kxns"


async def do_update(*, print: bool = True, check_only: bool = False) -> UpdateResult:
    async with _UPDATE_LOCK:
        return await _do_update(print=print, check_only=check_only)


LATEST_VERSION_FILE = get_share_dir() / "latest_version.txt"


async def _do_update(*, print: bool, check_only: bool) -> UpdateResult:
    from kxns_cli.constant import VERSION as current_version

    def _print(message: str) -> None:
        if print:
            console.print(message)

    target = _detect_target()
    if not target:
        _print("[red]Failed to detect target platform.[/red]")
        return UpdateResult.UNSUPPORTED

    async with new_client_session() as session:
        logger.info("Checking for updates on GitHub...")
        _print("Checking for updates...")

        release = await _get_latest_release(session)
        if not release:
            _print("[red]Failed to check for updates.[/red]")
            return UpdateResult.FAILED

        tag_name = release.get("tag_name", "")
        latest_version = tag_name.lstrip("v")
        if not latest_version:
            _print("[red]Failed to parse latest version.[/red]")
            return UpdateResult.FAILED

        logger.debug("Latest version: {latest_version}", latest_version=latest_version)
        LATEST_VERSION_FILE.write_text(latest_version, encoding="utf-8")

        cur_t = semver_tuple(current_version)
        lat_t = semver_tuple(latest_version)

        if cur_t >= lat_t:
            logger.debug("Already up to date: {current_version}", current_version=current_version)
            _print("[green]Already up to date.[/green]")
            return UpdateResult.UP_TO_DATE

        if check_only:
            logger.info(
                "Update available: current={current_version}, latest={latest_version}",
                current_version=current_version,
                latest_version=latest_version,
            )
            _print(f"[yellow]Update available: {latest_version}[/yellow]")
            return UpdateResult.UPDATE_AVAILABLE

        logger.info(
            "Updating from {current_version} to {latest_version}...",
            current_version=current_version,
            latest_version=latest_version,
        )
        _print(f"Updating from {current_version} to {latest_version}...")

        download_url, archive_name = _find_asset_url(release, target)
        if not download_url:
            logger.error("No matching asset found for target: {target}", target=target)
            _print(
                f"[red]No prebuilt binary found for {target}. "
                f"Please visit {GITHUB_RELEASES_URL} to download manually.[/red]"
            )
            return UpdateResult.UNSUPPORTED

        with tempfile.TemporaryDirectory(prefix="kxns-cli-") as tmpdir:
            filename = download_url.rsplit("/", 1)[-1]
            archive_path = os.path.join(tmpdir, filename)

            logger.info("Downloading from {download_url}...", download_url=download_url)
            _print("[grey50]Downloading...[/grey50]")
            try:
                async with session.get(download_url) as resp:
                    resp.raise_for_status()
                    with open(archive_path, "wb") as f:
                        async for chunk in resp.content.iter_chunked(1024 * 64):
                            if chunk:
                                f.write(chunk)
            except aiohttp.ClientError:
                logger.exception(
                    "Failed to download update from {download_url}",
                    download_url=download_url,
                )
                _print("[red]Failed to download.[/red]")
                return UpdateResult.FAILED
            except Exception:
                logger.exception("Failed to download:")
                _print("[red]Failed to download.[/red]")
                return UpdateResult.FAILED

            logger.info("Extracting archive {archive_path}...", archive_path=archive_path)
            _print("[grey50]Extracting...[/grey50]")

            bin_name = _binary_name()
            binary_path = None

            try:
                if archive_name and archive_name.endswith(".zip"):
                    with zipfile.ZipFile(archive_path, "r") as zf:
                        zf.extractall(tmpdir)
                    for root, _, files in os.walk(tmpdir):
                        if bin_name in files:
                            binary_path = os.path.join(root, bin_name)
                            break
                else:
                    import tarfile

                    with tarfile.open(archive_path, "r:gz") as tar:
                        tar.extractall(tmpdir)
                    for root, _, files in os.walk(tmpdir):
                        if bin_name in files:
                            binary_path = os.path.join(root, bin_name)
                            break

                if not binary_path:
                    logger.error("Binary '{bin_name}' not found in archive.", bin_name=bin_name)
                    _print(f"[red]Binary '{bin_name}' not found in archive.[/red]")
                    return UpdateResult.FAILED
            except Exception:
                logger.exception("Failed to extract archive:")
                _print("[red]Failed to extract archive.[/red]")
                return UpdateResult.FAILED

            INSTALL_DIR.mkdir(parents=True, exist_ok=True)
            dest_path = INSTALL_DIR / bin_name
            logger.info("Installing to {dest_path}...", dest_path=dest_path)
            _print("[grey50]Installing...[/grey50]")

            try:
                shutil.copy2(binary_path, dest_path)
                if not _IS_WINDOWS:
                    os.chmod(
                        dest_path,
                        os.stat(dest_path).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH,
                    )
            except Exception:
                logger.exception("Failed to install:")
                _print("[red]Failed to install.[/red]")
                return UpdateResult.FAILED

    _print("[green]Updated successfully![/green]")
    _print("[yellow]Restart KXNS Hunter CLI to use the new version.[/yellow]")
    return UpdateResult.UPDATED
