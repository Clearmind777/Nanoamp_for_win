"""Launch a windowed executable, wait for its window, and screenshot it.

Unlike a plain full-desktop grab, this waits for the target window to actually
exist, restores it to the foreground, and then captures the whole screen so the
window is guaranteed to be visible.

Usage:
    python capture_window.py <exe> <output.png> [--args ...] [--title-contains TEXT]
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import subprocess
import sys
import time
from pathlib import Path

from PIL import ImageGrab

user32 = ctypes.windll.user32
SW_RESTORE = 9
SW_SHOW = 5


def _win_titles() -> list[tuple[int, int, str, str]]:
    """(hwnd, pid, exe_name, title) for every visible top-level window."""
    results: list[tuple[int, int, str, str]] = []

    @ctypes.WINFUNCTYPE(wt.BOOL, wt.HWND, wt.LPARAM)
    def cb(hwnd, _lparam):
        if not user32.IsWindowVisible(hwnd):
            return True
        wpid = wt.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(wpid))
        length = user32.GetWindowTextLengthW(hwnd)
        buf = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buf, length + 1)
        results.append((hwnd, int(wpid.value), _exe_name(int(wpid.value)), buf.value))
        return True

    user32.EnumWindows(cb, 0)
    return results


def _exe_name(pid: int) -> str:
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    h = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not h:
        return ""
    try:
        size = wt.DWORD(260)
        buf = ctypes.create_unicode_buffer(260)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(size)):
            return Path(buf.value).name.lower()
    finally:
        kernel32.CloseHandle(h)
    return ""


def find_window(pid: int, title_contains: str | None, timeout: float = 60.0):
    """Wait for the target window.

    Matching is by window title, then by owning executable name, and only last
    by pid: a PyInstaller one-file bootloader runs the real GUI in a *child*
    process, so the pid we launched is not the one that owns the window.
    """
    deadline = time.time() + timeout
    seen: list[str] = []
    wanted_exe = ""
    while time.time() < deadline:
        windows = _win_titles()
        if not wanted_exe:
            for _hwnd, wpid, exe, _title in windows:
                if wpid == pid and exe:
                    wanted_exe = exe
                    break
        for hwnd, wpid, exe, title in windows:
            if title and title not in seen:
                seen.append(title)
            if not title:
                continue
            if title_contains and title_contains in title:
                return hwnd, title, seen
            if not title_contains and wpid == pid:
                return hwnd, title, seen
            if not title_contains and wanted_exe and exe == wanted_exe:
                return hwnd, title, seen
        time.sleep(0.5)
    return None, None, seen


def main() -> int:
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    exe = Path(sys.argv[1]).resolve()
    out = Path(sys.argv[2]).resolve()
    rest = sys.argv[3:]

    title_contains = None
    args: list[str] = []
    i = 0
    while i < len(rest):
        if rest[i] == "--title-contains" and i + 1 < len(rest):
            title_contains = rest[i + 1]
            i += 2
        elif rest[i] == "--args":
            args.extend(rest[i + 1:])
            break
        else:
            args.append(rest[i])
            i += 1

    print(f"launching {exe.name} {args}")
    proc = subprocess.Popen([str(exe), *args])
    hwnd, title, seen = find_window(proc.pid, title_contains)
    if not hwnd:
        print(f"no window appeared for pid {proc.pid}; titles seen: {seen}")
        proc.terminate()
        return 1
    print(f"window found: hwnd={hwnd} title={title!r}")

    user32.ShowWindow(hwnd, SW_RESTORE)
    user32.ShowWindow(hwnd, SW_SHOW)
    user32.SetForegroundWindow(hwnd)
    user32.BringWindowToTop(hwnd)
    time.sleep(2.0)

    img = ImageGrab.grab()
    img.save(out)
    print(f"saved {out}  {img.size[0]}x{img.size[1]}")

    proc.terminate()
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
