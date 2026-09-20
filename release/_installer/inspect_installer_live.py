"""Drive the nanoamp installer window and verify its live state rows.

Tk paints its widgets itself, so nothing in the window exposes text through the
Win32 API. This tool therefore takes the opposite approach: it finds the real
entry widget by geometry, types into it, and reads the result from the
screenshot it takes. That is exactly what a user would do.

Usage:
    python inspect_installer_live.py <outdir>

It answers two questions:

  1. does the "该磁盘剩余 X GB" row render at all?
  2. does it change when the install location changes, and does it warn on an
     unreachable drive?
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import sys
import time
from pathlib import Path

from PIL import Image, ImageGrab

try:
    from pywinauto import Desktop
    from pywinauto.application import Application
    from pywinauto.keyboard import send_keys
except ImportError:
    print("pywinauto is required: python -m pip install pywinauto")
    raise SystemExit(2)

user32 = ctypes.windll.user32
SW_RESTORE = 9
VK_CONTROL, VK_A = 0x11, 0x41


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


def widgets_by_geometry(win) -> list:
    return [(c.rectangle(), c) for c in win.descendants()]


def find_entry(win):
    """The path entry is the widest one-line box in the top third."""
    best = None
    for rect, child in widgets_by_geometry(win):
        w, h = rect.width(), rect.height()
        if rect.top < win.rectangle().top + 400 and w > 350 and 18 <= h <= 40:
            if best is None or w > best[0].width():
                best = (rect, child)
    return best


def focus_and_type(child, text: str) -> None:
    """Replace the entry contents the way a user would.

    Global keystrokes only reach the window that currently owns focus, which is
    unreliable when a browser or terminal is in the way. Clicking the control
    first and then typing straight at it is what actually works here.
    """
    user32.SetForegroundWindow(win_handle)
    child.click_input()
    time.sleep(0.4)
    child.type_keys("^a{DEL}", pause=0.05)
    child.type_keys(text, pause=0.03, with_spaces=True)
    time.sleep(1.2)


def kill_all(name: str) -> int:
    """Kill every process with this image name.

    PyInstaller's one-file bootloader unpacks itself and runs the GUI in a
    *child* process, so killing the pid we started leaves the real window (and
    its lock on the exe) behind. That would make the next rebuild fail with
    "access denied", so sweep by image name instead.
    """
    proc = subprocess.run(
        ["taskkill", "/IM", name, "/F"], capture_output=True, text=True
    )
    killed = proc.stdout.count("SUCCESS") + proc.stdout.count("成功")
    return killed


def shoot(path: Path) -> None:
    """Grab the whole screen, plus a legible crop of the install-location box.

    The window moves between runs, so the crop is derived from the frame and
    the entry geometry rather than hard-coded screen coordinates.
    """
    img = ImageGrab.grab()
    img.save(path)
    print(f"  saved {path.name} ({img.size[0]}x{img.size[1]})")

    if shoot.entry_rect is not None:
        left = max(shoot.entry_rect.left - 20, 0)
        top = max(shoot.entry_rect.top - 70, 0)
        right = min(shoot.entry_rect.right + 220, img.size[0])
        bottom = min(shoot.entry_rect.bottom + 70, img.size[1])
        crop = img.crop((left, top, right, bottom))
        scale = 2
        crop = crop.resize((crop.width * scale, crop.height * scale), Image.LANCZOS)
        crop.save(path.with_name(path.stem + "_zoom.png"))
        print(f"  saved {path.stem}_zoom.png ({crop.size[0]}x{crop.size[1]})")


shoot.entry_rect = None


def main() -> int:
    if len(sys.argv) < 2:
        print(__doc__)
        return 2
    outdir = Path(sys.argv[1])
    outdir.mkdir(parents=True, exist_ok=True)
    exe = Path("release/install.exe").resolve()
    kill_all("install.exe")  # never let an old copy hold the file we rebuild

    global win_handle
    app = Application(backend="win32").start(
        subprocess.list2cmdline([str(exe)]), timeout=60
    )
    win = find_window("nanoamp 安装程序")
    if win is None:
        print("installer window never appeared")
        return 1
    win_handle = win.handle
    user32.ShowWindow(win_handle, SW_RESTORE)
    user32.SetForegroundWindow(win_handle)
    time.sleep(1.5)

    print("[1] default state")
    entry = find_entry(win)
    if entry is None:
        print("  could not locate the path entry")
        kill_all("install.exe")
        return 1
    rect, child = entry
    shoot.entry_rect = rect
    print(f"  entry at {rect}")
    shoot(outdir / "installer_default.png")

    print("[2] point it at D:\\nanoamp (a different drive)")
    focus_and_type(child, "D:\\nanoamp")
    shoot(outdir / "installer_d_drive.png")

    print("[3] point it at Q:\\nope (drive does not exist)")
    focus_and_type(child, "Q:\\nope")
    shoot(outdir / "installer_bad_drive.png")

    kill_all("install.exe")
    time.sleep(0.5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
