"""Screenshot the uninstaller while it has something to remove.

The uninstaller's window changes shape depending on what it finds, and the
interesting state is "a real install exists, here is what I will delete". That
state is hard to photograph on a clean machine, so this tool builds a complete
throwaway install in a sandbox first.

Nothing real is touched: the fake install lives in a temp folder and the
uninstaller is launched with LOCALAPPDATA / USERPROFILE / APPDATA redirected
into the sandbox, so even its PATH and .Renviron edits land there.

Usage:
    python capture_uninstaller_populated.py <outdir> [--exe release\\uninstall.exe]
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from PIL import Image, ImageGrab

sys.path.insert(0, str(Path(__file__).resolve().parent))

try:
    from pywinauto import Desktop
    from pywinauto.application import Application
except ImportError:
    print("pywinauto is required: python -m pip install pywinauto")
    raise SystemExit(2)

def build_fake_install(sandbox: Path) -> Path:
    """Create a convincing install tree, plus the pointer and path entry."""
    local = sandbox / "LocalAppData"
    local.mkdir(parents=True, exist_ok=True)
    root = sandbox / "apps" / "nanoamp"
    (root / "R" / "lib" / "nanoamp").mkdir(parents=True, exist_ok=True)
    (root / "R" / "R-runtime" / "bin").mkdir(parents=True, exist_ok=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "config").mkdir(parents=True, exist_ok=True)

    (root / "config.ini").write_text(
        "[paths]\n"
        f"home={root}\n"
        "rscript=C:\\Program Files\\R\\R-4.6.1\\bin\\Rscript.exe\n"
        "[install]\n"
        "version=0.1.0\n",
        encoding="utf-8",
    )
    (root / "bin" / "nanoamp.cmd").write_text("@echo off\r\n", encoding="ascii")
    (root / "bin" / "minimap2.exe").write_bytes(b"MZ" + b"\0" * 4094)
    (root / "app" / "nanoamp.exe").write_bytes(b"MZ" + b"\0" * 4094)
    (root / "R" / "lib" / "nanoamp" / "DESCRIPTION").write_text(
        "Package: nanoamp\nVersion: 0.1.0\n", encoding="utf-8"
    )
    (root / "R" / "R-runtime" / "bin" / "Rscript.exe").write_bytes(
        b"MZ" + b"\0" * 8190
    )

    # The pointer that normally lets the uninstaller find a moved install.
    (local / "nanoamp.path").write_text(str(root), encoding="utf-8")

    # Desktop shortcut, so the "will remove" list has more than one row.
    desktop = sandbox / "Desktop"
    desktop.mkdir(parents=True, exist_ok=True)
    (desktop / "nanoamp.lnk").write_bytes(b"\0" * 64)

    return root


def sandbox_env(sandbox: Path) -> dict[str, str]:
    env = dict(os.environ)
    local = sandbox / "LocalAppData"
    roaming = sandbox / "Roaming"
    profile = sandbox / "Profile"
    docs = profile / "Documents"
    for d in (local, roaming, profile, docs):
        d.mkdir(parents=True, exist_ok=True)
    env["LOCALAPPDATA"] = str(local)
    env["APPDATA"] = str(roaming)
    env["USERPROFILE"] = str(profile)
    env["HOMEDRIVE"], env["HOMEPATH"] = profile.drive, str(profile)[2:]
    # Make the "remove from PATH" row light up, sandboxed to HKCU\Environment.
    env["PATH"] = str(sandbox / "apps" / "nanoamp" / "bin") + os.pathsep + env["PATH"]
    return env


def find_window(title_contains: str, timeout: float = 90.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        for win in Desktop(backend="win32").windows():
            try:
                if title_contains in win.window_text():
                    return win
            except Exception:  # noqa: BLE001
                continue
        time.sleep(0.5)
    return None


def kill_all(name: str) -> None:
    subprocess.run(["taskkill", "/IM", name, "/F"], capture_output=True)


def main() -> int:
    import ctypes

    global user32
    user32 = ctypes.windll.user32

    ap = argparse.ArgumentParser()
    ap.add_argument("outdir")
    ap.add_argument("--exe", default="release/uninstall.exe")
    ns = ap.parse_args()

    outdir = Path(ns.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    exe = Path(ns.exe).resolve()
    kill_all(exe.name)

    sandbox = Path(tempfile.mkdtemp(prefix="nanoamp-unsandbox-"))
    keep = "--keep" in sys.argv
    try:
        root = build_fake_install(sandbox)
        print(f"sandbox: {sandbox}")
        print(f"fake install: {root}")

        env = sandbox_env(sandbox)
        proc = subprocess.Popen([str(exe)], env=env)
        win = find_window("nanoamp 卸载程序")
        if win is None:
            print("uninstaller window never appeared")
            return 1
        hwnd = win.handle
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        time.sleep(1.5)

        img = ImageGrab.grab()
        img.save(outdir / "uninstaller_populated.png")
        print(f"  saved uninstaller_populated.png ({img.size[0]}x{img.size[1]})")

        rect = win.rectangle()
        pad = 10
        crop = img.crop(
            (
                max(rect.left - pad, 0),
                max(rect.top - pad, 0),
                min(rect.right + pad, img.size[0]),
                min(rect.bottom + pad, img.size[1]),
            )
        )
        crop = crop.resize((crop.width * 2, crop.height * 2), Image.LANCZOS)
        crop.save(outdir / "uninstaller_populated_zoom.png")
        print(f"  saved uninstaller_populated_zoom.png ({crop.size[0]}x{crop.size[1]})")

        # Close without running it: this is a screenshot, not an uninstall.
        proc.terminate()
        kill_all(exe.name)
        time.sleep(0.5)
        return 0
    finally:
        if keep:
            print(f"kept sandbox: {sandbox}")
        else:
            shutil.rmtree(sandbox, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main())
