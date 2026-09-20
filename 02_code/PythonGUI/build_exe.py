"""Freeze the nanoamp GUI into a double-clickable nanoamp.exe.

Usage:
    python 02_code/PythonGUI\\build_exe.py

Requirements:
    pip install pyinstaller

The result lands in 02_code/PythonGUI\\dist\\nanoamp.exe. It is a one-file, windowed
build: double-clicking it opens the window with no console.

Note that the .exe only packages the *interface*. The analysis is performed by
the nanoamp R package, so R must still be installed on the target machine.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> int:
    if shutil.which("pyinstaller") is None and not _module_available("PyInstaller"):
        print("PyInstaller is not installed. Run:\n\n    pip install pyinstaller\n")
        return 2

    spec = HERE / "nanoamp.spec"
    print(f"building from {spec}")
    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(spec),
        "--noconfirm",
        "--distpath", str(HERE / "dist"),
        "--workpath", str(HERE / "build"),
    ]
    proc = subprocess.run(cmd, cwd=str(HERE))
    if proc.returncode != 0:
        print("build failed")
        return proc.returncode

    exe = HERE / "dist" / "nanoamp.exe"
    if exe.is_file():
        print(f"\nOK -> {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
        print("Double-click it to open the window.")
        return 0
    print("build finished but nanoamp.exe was not produced")
    return 1


def _module_available(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
