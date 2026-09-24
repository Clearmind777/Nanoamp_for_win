"""Freeze install.exe and uninstall.exe into the release directory.

Usage:
    python release/_installer/build_exe.py            # both
    python release/_installer/build_exe.py install    # only install.exe
    python release/_installer/build_exe.py uninstall  # only uninstall.exe

Requires PyInstaller (pip install pyinstaller).

Build strategy: **onedir**.
The executables land in ``release/`` beside the payload (``_offline/``,
``01_R-package/``, ``03_GUI/``), which is ~250 MB of R installers and package
archives. Bundling that inside the executable would produce a ~250 MB
self-extracting binary that unpacks on every launch. Keeping the payload
external means each .exe stays around 10 MB and starts instantly.

The payload location is documented for the user in release/README.md: the
release folder as a whole is the deliverable, and install.exe must not be
moved away from it.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parent

# name -> (entry script, spec file, one-line description)
TARGETS = {
    "install": ("install_nanoamp.py", "install.spec", "one-click installer"),
    "uninstall": ("uninstall_nanoamp.py", "uninstall.spec", "uninstaller"),
}


def main() -> int:
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")] or list(TARGETS)
    unknown = [w for w in wanted if w not in TARGETS]
    if unknown:
        print(f"unknown target(s): {', '.join(unknown)}\navailable: {', '.join(TARGETS)}")
        return 2

    if not _has_pyinstaller():
        print("PyInstaller is not installed. Run:\n\n    pip install pyinstaller\n")
        return 2

    failed: list[str] = []
    for name in wanted:
        if not _build(name):
            failed.append(name)

    print("\n=== payload check (must sit next to the executables) ===")
    _verify_payload_visible()

    if failed:
        print(f"\nFAILED: {', '.join(failed)}")
        return 1
    return 0


def _build(name: str) -> bool:
    entry, spec, desc = TARGETS[name]
    print(f"\n=== building {name}.exe ({desc}) ===")
    if not (HERE / entry).is_file():
        print(f"missing entry script: {entry}")
        return False

    cmd = [
        sys.executable, "-m", "PyInstaller",
        str(HERE / spec),
        "--noconfirm",
        "--distpath", str(RELEASE),
        "--workpath", str(HERE / "build"),
    ]
    proc = subprocess.run(cmd, cwd=str(HERE))
    if proc.returncode != 0:
        print(f"{name}: build failed")
        return False

    exe = RELEASE / f"{name}.exe"
    if not exe.is_file():
        print(f"{name}: build finished but {name}.exe was not produced")
        return False
    print(f"OK -> {exe}  ({exe.stat().st_size / 1024 / 1024:.1f} MB)")
    return True


def _verify_payload_visible() -> None:
    ok = True
    for name in ("_offline", "01_R-package", "02_CLI", "03_GUI", "deps"):
        p = RELEASE / name
        if p.exists():
            print(f"  OK      {name}")
        elif name == "_offline":
            print("  note    _offline not present "
                  "(optional: release/_build/build_assets.py packages deps/ so install.exe can download)")
        else:
            print(f"  MISSING {name}")
            ok = False
    r_installers = list((RELEASE / "_offline" / "r").glob("R-*-win.exe"))
    pkgs = list((RELEASE / "_offline" / "r-packages").rglob("*.zip"))
    manifest = list((RELEASE / "deps").glob("pinned-R*.tsv"))
    print(f"  R installer : {r_installers[0].name if r_installers else 'not present (online install)'}")
    print(f"  R packages  : {len(pkgs)}" if pkgs else "  R packages  : 0 (online install uses deps/pinned-R*.tsv)")
    print(f"  pinned set  : {manifest[0].name if manifest else 'MISSING'}")
    aligner = RELEASE / "_offline" / "minimap2.exe"
    print(f"  minimap2    : {aligner.relative_to(RELEASE).as_posix() if aligner.is_file() else 'MISSING'}"
          "  -> packaged as bin/minimap2.exe in the setup asset")
    # The installer needs *a* way to get dependencies and an aligner: the
    # offline bundle, the pinned manifest, or both.
    if not r_installers and not manifest:
        print("\nWARNING: neither an offline bundle nor deps/pinned-R*.tsv is present;")
        print("         install.exe will refuse to run on a machine without R.")
        ok = False
    if not aligner.is_file():
        print("\nWARNING: no _offline/minimap2.exe to package as bin/minimap2.exe;")
        print("         the aligner step would fail.")
        ok = False
    _ = ok


def _has_pyinstaller() -> bool:
    try:
        __import__("PyInstaller")
    except ImportError:
        return False
    return True


if __name__ == "__main__":
    raise SystemExit(main())
