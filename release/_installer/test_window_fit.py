"""Assert that both windows fit inside themselves on every screen size.

The bug this exists for: the "开始卸载" button was packed last, so whenever the
content above it grew, the button ended up below the bottom edge of the window.
It was present, clickable in theory, and invisible in practice.

Usage:
    python release/_installer/test_window_fit.py
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import install_nanoamp as ins  # noqa: E402
import uninstall_nanoamp as un  # noqa: E402


class FakeScreen:
    """Pretend the monitor is smaller than it is, to test the shrink path."""

    def __init__(self, window, width: int, height: int):
        self.window = window
        self.width = width
        self.height = height

    def __enter__(self):
        self._real_w = self.window.winfo_screenwidth
        self._real_h = self.window.winfo_screenheight
        self.window.winfo_screenwidth = lambda: self.width
        self.window.winfo_screenheight = lambda: self.height
        return self

    def __exit__(self, *exc):
        self.window.winfo_screenwidth = self._real_w
        self.window.winfo_screenheight = self._real_h
        return False


def check(window, label: str) -> list[str]:
    """Every visible widget must sit fully inside the window, and any text that
    cannot wrap must fit. A label wider than the window is silently cut off,
    which is how a long install path hid half of itself."""
    root = window.root
    root.update()
    width, height = root.winfo_width(), root.winfo_height()
    problems: list[str] = []
    stack = list(root.pack_slaves())
    while stack:
        child = stack.pop()
        stack.extend(child.pack_slaves())
        if not child.winfo_ismapped():
            continue
        bottom = child.winfo_y() + child.winfo_height()
        right = child.winfo_x() + child.winfo_width()
        if bottom > height or right > width or child.winfo_height() <= 1:
            problems.append(
                f"{child.winfo_class()} at y={child.winfo_y()} h={child.winfo_height()} "
                f"(bottom {bottom} > window {height})"
            )
        try:
            wraplength = int(child.cget("wraplength"))
        except Exception:  # noqa: BLE001 - not a text widget
            wraplength = 0
        if wraplength <= 1 and child.winfo_reqwidth() > width - 20:
            text = ""
            try:
                text = child.cget("text")
            except Exception:  # noqa: BLE001
                pass
            problems.append(
                f"{child.winfo_class()} needs {child.winfo_reqwidth()}px but the window "
                f"is {width}px and it cannot wrap: {str(text)[:60]!r}"
            )
    return problems


def run_case(build, label: str, screen: tuple[int, int]) -> bool:
    window = build()
    with FakeScreen(window.root, *screen):
        window.fit_to_content()
        window.root.update()
        height = window.root.winfo_height()
        button_ok = (
            window.btn.winfo_ismapped()
            and window.btn.winfo_y() + window.btn.winfo_height() <= height
        )
        problems = check(window, label)
        print(f"\n=== {label} (screen {screen[0]}x{screen[1]}) ===")
        print(f"    window {window.root.winfo_width()}x{height}")
        print(f"    button visible: {button_ok}")
        for p in problems:
            print(f"    CLIPPED: {p}")
        if not button_ok:
            problems.append("the action button is not reachable")
        window.root.destroy()
    return not problems


def main() -> int:
    results: list[bool] = []
    screens = [(1920, 1080), (1366, 768), (1280, 720)]
    for width, height in screens:
        results.append(
            run_case(ins.InstallerWindow, "installer", (width, height))
        )
        results.append(
            run_case(un.UninstallWindow, "uninstaller", (width, height))
        )

    print("\n" + "=" * 60)
    if all(results):
        print(f"PASS  {len(results)}/{len(results)} window-fit cases")
        return 0
    print(f"FAIL  {sum(results)}/{len(results)} window-fit cases")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
