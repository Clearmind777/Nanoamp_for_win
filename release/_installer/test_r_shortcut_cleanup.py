"""Test the safety net that removes shortcuts the bundled R installer adds.

Reported bug: after install.exe installed the bundled R, an "R 4.6.1" shortcut
also appeared on the desktop. The user asked for a nanoamp shortcut, not R's.

The primary defence is passing /MERGETASKS="!desktopicon,!quicklaunchicon" to
R's Inno Setup installer. This test covers the safety net behind it, which
deletes only the shortcuts that (a) appeared during the R installation and
(b) look like R's -- so a pre-existing R, or any other shortcut the user has,
is never touched.

Everything runs against a sandboxed USERPROFILE/APPDATA, so the real desktop is
never read or written.

Usage:
    python release/_installer/test_r_shortcut_cleanup.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import install_nanoamp as ins  # noqa: E402
import nanoamp_common as common  # noqa: E402


class Sandbox:
    """Redirect the desktop and Start menu into a temp directory."""

    def __init__(self, root: Path):
        self.root = root
        self.profile = root / "Profile"
        self.appdata = root / "AppData"
        (self.profile / "Desktop").mkdir(parents=True, exist_ok=True)
        (self.appdata / "Microsoft/Windows/Start Menu/Programs").mkdir(
            parents=True, exist_ok=True
        )
        self._saved: dict[str, str | None] = {}

    def __enter__(self):
        for key, value in (("USERPROFILE", str(self.profile)), ("APPDATA", str(self.appdata))):
            self._saved[key] = os.environ.get(key)
            os.environ[key] = value
        return self

    def __exit__(self, *exc):
        for key, value in self._saved.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        return False

    def desktop(self, name: str) -> Path:
        p = self.profile / "Desktop" / name
        p.write_bytes(b"lnk")
        return p

    def startmenu(self, name: str) -> Path:
        p = self.appdata / "Microsoft/Windows/Start Menu/Programs" / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"lnk")
        return p


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="nanoamp-lnk-"))
    try:
        with Sandbox(tmp) as box:
            # Shortcuts that already existed before the R install.
            preexisting_r = box.desktop("R 4.5.0.lnk")      # user's own R
            preexisting_other = box.desktop("Excel.lnk")
            preexisting_sm = box.startmenu("R/R 4.5.0.lnk")

            before = ins._shortcut_snapshot()
            print(f"  before: {len(before)} shortcut(s)")

            # What R's installer would drop.
            new_r_desktop = box.desktop("R 4.6.1.lnk")
            new_r_sm = box.startmenu("R/R 4.6.1.lnk")
            new_rgui = box.desktop("R x64 4.6.1.lnk")
            # Something harmless and unrelated, created in the same window.
            new_other = box.desktop("SomeOtherApp.lnk")

            messages: list[str] = []
            ins._hide_bundled_r_shortcuts(before, messages.append)
            for m in messages:
                print("   ", m)

            checks = [
                ("kept   user's own R (desktop)", preexisting_r.exists(), True),
                ("kept   unrelated (desktop)", preexisting_other.exists(), True),
                ("kept   user's own R (start menu)", preexisting_sm.exists(), True),
                ("kept   unrelated created later", new_other.exists(), True),
                ("removed new R (desktop)", new_r_desktop.exists(), False),
                ("removed new R (start menu)", new_r_sm.exists(), False),
                ("removed new R x64 (desktop)", new_rgui.exists(), False),
            ]
            for label, actual, expected in checks:
                ok = actual == expected
                print(f"  {'ok  ' if ok else 'FAIL'}  {label}")
                if not ok:
                    failures.append(label)

            # Idempotence: running again must not delete anything else.
            again: list[str] = []
            ins._hide_bundled_r_shortcuts(ins._shortcut_snapshot(), again.append)
            if again:
                failures.append(f"second run removed more: {again}")
            print(f"  {'ok  ' if not again else 'FAIL'}  second run is a no-op")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 62)
    if failures:
        print(f"FAIL  {len(failures)} problem(s):")
        for f in failures:
            print("   -", f)
        return 1
    print("PASS  R shortcut cleanup (keeps user's, removes R's, idempotent)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
