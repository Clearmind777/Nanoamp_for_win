"""Guard against the "安装路径含有非法字符" false positive ever coming back.

The bug: install.exe rejected *every* install location, so 开始安装 could never
run. The validator tested the whole path string for ':', but a Windows drive
anchor (`C:\\`) legitimately contains a colon, so the default path failed too.

This test pins both directions:
  * legal paths must be accepted (including the drive colon, spaces, non-ASCII)
  * genuinely illegal characters must still be caught

Usage:
    python release/_installer/test_install_path_validation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import install_nanoamp as ins  # noqa: E402

# Paths a user could reasonably type. None of these may be rejected.
LEGAL = [
    r"C:\Users\ww052\AppData\Local\nanoamp",
    r"D:\nanoamp",
    r"D:\nanoamp test",
    r"C:\Program Files\nanoamp",
    r"C:\Program Files (x86)\nanoamp",
    "C:/Users/ww052/AppData/Local/nanoamp",
    "D:/nanoamp",
    r"E:\a b c\my nanoamp",
    r"D:\nanoamp-0.1.0_v2",
    r"D:\nanoamp (backup)",
    # A non-ASCII user name is the common real-world case, not an error.
    "C:\\Users\\\u5f20\u4e09\\AppData\\Local\\nanoamp",
    # UNC shares are legitimate.
    r"\\server\share\nanoamp",
    "C:\\",
]

# Characters Windows genuinely cannot put in a file name.
ILLEGAL = [
    (r"D:\nanoamp?", "?"),
    (r"D:\nan|oamp", "|"),
    (r"D:\nanoamp*", "*"),
    (r'D:\nan"oamp', '"'),
    (r"D:\nan<oamp", "<"),
    (r"D:\nan>oamp", ">"),
    (r"D:\nan:oamp", ":"),
    (r"D:\a\b:c", ":"),
]


def main() -> int:
    failures: list[str] = []

    print("=== legal paths (must be accepted) ===")
    for p in LEGAL:
        bad = ins._illegal_path_chars(Path(p))
        ok = not bad
        print(f"  {'ok  ' if ok else 'FAIL'}  {p}")
        if not ok:
            failures.append(f"{p} wrongly rejected (matched {bad})")

    print("\n=== illegal characters (must still be caught) ===")
    for p, expect in ILLEGAL:
        bad = ins._illegal_path_chars(Path(p))
        ok = expect in bad
        print(f"  {'ok  ' if ok else 'FAIL'}  {p}  -> {bad}")
        if not ok:
            failures.append(f"{p} should have matched {expect!r}, got {bad}")

    failures.extend(check_real_handler())

    print("\n" + "=" * 62)
    if failures:
        print(f"FAIL  {len(failures)} problem(s):")
        for f in failures:
            print("   -", f)
        return 1
    print(f"PASS  {len(LEGAL)} legal + {len(ILLEGAL)} illegal path cases "
          "+ the real 开始安装 handler")
    return 0


def check_real_handler() -> list[str]:
    """Drive the actual button handler and record which dialog it raises.

    The unit check above tests the helper; this exercises what a user's click
    really runs, with messagebox intercepted so no window is needed.
    """
    import tkinter as tk

    problems: list[str] = []
    shown: list[tuple[str, str]] = []

    real = {
        "showerror": ins.messagebox.showerror,
        "showwarning": ins.messagebox.showwarning,
        "showinfo": ins.messagebox.showinfo,
        "askyesno": ins.messagebox.askyesno,
    }
    real_run_all = ins.Installer.run_all
    ins.messagebox.showerror = lambda t, m, **k: shown.append(("error", m))
    ins.messagebox.showwarning = lambda t, m, **k: shown.append(("warning", m))
    ins.messagebox.showinfo = lambda t, m, **k: shown.append(("info", m))
    ins.messagebox.askyesno = lambda t, m, **k: shown.append(("ask", m)) or False
    # Never actually install: this test is about the validation dialog only.
    ins.Installer.run_all = lambda self: True

    window = None
    try:
        # Accept a place with no existing install so the "already installed"
        # prompt cannot interfere, then let the handler stop right after
        # validation by making the target unusable in a harmless way.
        for label, path in (("default", r"C:\Users\ww052\AppData\Local\nanoamp"),
                            ("d-drive", r"D:\nanoamp")):
            shown.clear()
            window = ins.InstallerWindow()
            window.var_install_root.set(path)
            # 开始安装 validates the path and then starts Installer.run_all in a
            # daemon thread. Patch that at class level BEFORE _start, otherwise
            # the thread really begins installing: it creates the install
            # directories and rewrites the developer's Documents\.Renviron.
            window._start()
            illegal = [m for kind, m in shown if "非法字符" in m]
            print(f"  handler with {label:8} -> dialogs={[k for k, _ in shown]} "
                  f"accepted={window.worker is not None}")
            if illegal:
                problems.append(f"{path}: handler still rejects a legal path")
            if window.worker is not None:
                window.worker.join(timeout=10)
            window.root.destroy()
            window = None
    except tk.TclError as exc:
        print(f"  (skipping handler check: no display available: {exc})")
    finally:
        if window is not None:
            try:
                window.root.destroy()
            except Exception:  # noqa: BLE001
                pass
        for name, fn in real.items():
            setattr(ins.messagebox, name, fn)
        ins.Installer.run_all = real_run_all
    return problems


if __name__ == "__main__":
    raise SystemExit(main())
