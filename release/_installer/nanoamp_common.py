"""Shared knowledge of where nanoamp is installed.

Both ``install.exe`` and ``uninstall.exe`` need to agree on this, and on the
side effects the installer creates outside its own directory (PATH entry,
desktop shortcut, .Renviron line). Keeping it in one module means the
uninstaller can never drift out of sync with the installer.

The install location is chosen at install time, so it is stored in
``config.ini`` next to the install root's default location. Uninstall reads it
back from there.
"""

from __future__ import annotations

import os
from pathlib import Path

PRODUCT = "nanoamp"
APP_TITLE = "nanoamp"
SHORTCUT_NAME = "nanoamp 分析工具.lnk"
CONFIG_FILE = "config.ini"


def default_install_home() -> Path:
    """Default install root: per-user, no administrator rights required."""
    local = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(local) / PRODUCT


def config_candidates() -> list[Path]:
    """config.ini locations to look in, most authoritative first."""
    out: list[Path] = [default_install_home() / CONFIG_FILE]

    # The install location may have been changed, in which case config.ini is
    # wherever the user put it. Known locations from previous runs are recorded
    # in the per-user pointer file below.
    pointer = registry_of_installs()
    if pointer and pointer not in out:
        out.insert(0, pointer)
    return out


def registry_of_installs() -> Path | None:
    """Return the install root recorded by the last install/update, if any.

    A small pointer next to the default location, so a user who chose
    D:\\nanoamp is still found by the uninstaller.
    """
    marker = default_install_home().parent / f"{PRODUCT}.path"
    try:
        if marker.is_file():
            text = marker.read_text(encoding="utf-8").strip()
            if text:
                p = Path(text)
                if p.is_dir():
                    return p / CONFIG_FILE
    except OSError:
        pass
    return None


def write_pointer(install_root: Path) -> Path:
    """Remember where nanoamp was installed (used by the uninstaller)."""
    marker = default_install_home().parent / f"{PRODUCT}.path"
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(install_root), encoding="utf-8")
    except OSError:
        pass
    return marker


def remove_pointer() -> None:
    marker = default_install_home().parent / f"{PRODUCT}.path"
    try:
        marker.unlink()
    except OSError:
        pass


def desktop_dir() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Desktop"


def shortcut_path() -> Path:
    return desktop_dir() / SHORTCUT_NAME


def renviron_path() -> Path:
    return Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / ".Renviron"


def parse_config(path: Path) -> dict[str, str]:
    """Read a key=value config.ini into a dict.

    The format is deliberately plain key=value with no spaces around "=",
    because the batch launcher parses it with ``for /f "delims=="``, which
    would otherwise read the key as "rscript " and never match.
    """
    out: dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line or line.startswith("[") or line.startswith("#"):
                continue
            key, sep, value = line.partition("=")
            if sep:
                out[key.strip().lower()] = value.strip()
    except OSError:
        pass
    return out


def looks_installed(root: Path) -> bool:
    """True if ``root`` actually contains a nanoamp installation.

    Cheap structural check. Without it, a stray config.ini (for example one
    left in the release directory) would be mistaken for an installation and
    the status report would point at the wrong place.
    """
    return (root / "R" / "lib" / PRODUCT).is_dir() or (root / "app" / "nanoamp.exe").is_file()


def _path_entries() -> list[Path]:
    """Directories on the user PATH, so a relocated install can be found."""
    import winreg

    out: list[Path] = []
    for hive, sub in (
        (winreg.HKEY_CURRENT_USER, r"Environment"),
        (winreg.HKEY_LOCAL_MACHINE,
         r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"),
    ):
        try:
            with winreg.OpenKey(hive, sub) as key:
                raw, _ = winreg.QueryValueEx(key, "Path")
        except OSError:
            continue
        for part in raw.split(";"):
            part = part.strip()
            if part:
                out.append(Path(os.path.expandvars(part)))
    return out


def scan_for_installs() -> list[Path]:
    """Find install roots by looking for our marker files.

    Used when config.ini cannot be located, which happens if a previous
    install was interrupted or the pointer file was lost. The launcher's
    directory is on the user PATH, so that is the most reliable place to look.

    Deliberately shallow and marker-based: it must never guess a wrong
    directory that the uninstaller would then delete.
    """
    roots: list[Path] = []

    def consider(bin_like: Path) -> None:
        # bin_like is either "<root>\bin" or "<root>"
        for candidate in (bin_like.parent, bin_like):
            if (candidate / "config" / "nanoamp_cli.R").is_file() or \
               (candidate / "R" / "lib" / PRODUCT).is_dir() or \
               (candidate / "app" / "nanoamp.exe").is_file():
                if candidate not in roots:
                    roots.append(candidate)
                return

    for entry in _path_entries():
        if (entry / "nanoamp.cmd").is_file():
            consider(entry)

    # Common locations people pick when relocating.
    for parent in (Path("C:/"), Path("D:/"), Path("E:/"),
                   Path(os.environ.get("USERPROFILE", ""))):
        if not parent.is_dir():
            continue
        try:
            for child in parent.iterdir():
                if child.is_dir() and child.name.lower().startswith(PRODUCT):
                    consider(child)
        except OSError:
            pass
    return roots


def find_existing_install() -> tuple[Path, dict[str, str]] | None:
    """Locate an existing installation. Returns (root, config) or None.

    Candidates are tried in order and the first that actually looks installed
    wins, so a leftover config.ini cannot shadow the real install.
    """
    fallback: tuple[Path, dict[str, str]] | None = None

    def remember(root: Path, data: dict[str, str]) -> tuple[Path, dict[str, str]] | None:
        nonlocal fallback
        if looks_installed(root):
            return root, data
        if fallback is None:
            fallback = (root, data)
        return None

    for cfg in config_candidates():
        if not cfg.is_file():
            continue
        data = parse_config(cfg)
        raw = data.get("home", "")
        root = Path(raw) if raw else cfg.parent
        if root.is_dir():
            hit = remember(root, data)
            if hit:
                return hit

    # Nothing from config.ini: look for the markers directly.
    for root in scan_for_installs():
        data: dict[str, str] = {}
        cfg = root / CONFIG_FILE
        if cfg.is_file():
            data = parse_config(cfg)
        hit = remember(root, data)
        if hit:
            return hit

    return fallback


def lib_dir(root: Path) -> Path:
    return root / "R" / "lib"


def bin_dir(root: Path) -> Path:
    return root / "bin"


def app_dir(root: Path) -> Path:
    return root / "app"


def config_dir(root: Path) -> Path:
    return root / "config"
