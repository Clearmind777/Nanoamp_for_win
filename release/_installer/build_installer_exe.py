"""Freeze the nanoamp installer into release/install.exe.

Usage:
    python release/_installer/build_installer_exe.py

Requires PyInstaller (pip install pyinstaller).

Build strategy: **onedir**.

install.exe is placed beside the payload (``_offline/``, ``01_R-package/``,
``03_GUI/``), which is ~250 MB of R installers and package archives. Bundling
that inside the executable would produce a ~250 MB self-extracting binary that
must unpack on every launch. Keeping the payload external means the .exe stays
around 10 MB and starts instantly; the payload simply ships next to it.

This is documented for the user in release/README.md: the release folder as a
whole is the deliverable, and install.exe must not be moved away from it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parent


def main() -> int:
    if not _has_pyinstaller():
        print("PyInstaller is not installed. Run:\n\n    pip install pyinstaller\n")
        return 2

    spec = HERE / "install.spec"
    print(f"building {spec}")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--noconfirm",
        "--distpath", str(RELEASE),        # install.exe lands in release/
        "--workpath", str(HERE / "build"),
    ]
    proc = subprocess.run(cmd, cwd=str(HERE))
    if proc.returncode != 0:
        print("build failed")
        return proc.returncode

    exe = RELEASE / "install.exe"
    if not exe.is_file():
        print("build finished but install.exe was not produced")
        return 1

    size = exe.stat().st_size
    print(f"\nOK -> {exe}  ({size / 1024 / 1024:.1f} MB)")
    _verify_payload_visible()
    return 0


def _verify_payload_visible() -> None:
    """The payload must remain discoverable next to the exe."""
    print("\npayload check (must exist next to install.exe):")
    for name in ("_offline", "01_R-package", "03_GUI", "02_CLI"):
        p = RELEASE / name
        print(f"  {'OK ' if p.exists() else 'MISSING'} {name}")
    r_installers = list((RELEASE / "_offline" / "r").glob("R-*-win.exe"))
    pkgs = list((RELEASE / "_offline" / "r-packages").rglob("*.zip"))
    print(f"  R installer : {r_installers[0].name if r_installers else 'MISSING'}")
    print(f"  R packages  : {len(pkgs)}")
    if not r_installers or not pkgs:
        print("\nWARNING: release tree is incomplete; the installer will refuse to run.")


def _has_pyinstaller() -> bool:
    try:
        __import__("PyInstaller")
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
