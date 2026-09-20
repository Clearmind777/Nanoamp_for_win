"""Prove the GUI can find an R that only exists inside the nanoamp install.

This is the reported bug: install.exe successfully unpacked its own R under
<install_root>\\R\\R-runtime\\, but the GUI could not find Rscript.exe, so
环境自检 and 开始分析 both failed.

Cause: r_runner._candidate_rscipts() only looked in well-known R locations
(Program Files\\R, %LOCALAPPDATA%\\Programs\\R, PATH, ...) and never consulted
config.ini -- which is exactly where install.exe records where it put R.

The test builds a throwaway install root containing a fake Rscript.exe that
exists nowhere else, points the environment at it, and asserts find_rscript()
resolves it.

Usage:
    python 02_code/PythonGUI/tests/test_bundled_r_lookup.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import nanoamp_gui.r_runner as rr  # noqa: E402


def build_fake_install(root: Path) -> Path:
    """An install tree whose R lives only in the bundled runtime."""
    rscript = root / "R" / "R-runtime" / "bin" / "Rscript.exe"
    rscript.parent.mkdir(parents=True, exist_ok=True)
    rscript.write_bytes(b"fake")           # content is irrelevant
    (root / "R" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    # config.ini exactly as install.exe writes it
    (root / "config.ini").write_text(
        "[nanoamp]\n"
        f"home={root}\n"
        f"rscript={rscript}\n"
        f"rlib={root / 'R' / 'lib'}\n"
        "installed_at=2026-09-21 02:00:00\n",
        encoding="utf-8",
    )
    return rscript


def main() -> int:
    failures: list[str] = []

    # --- case 1: a default-location install, found via config.ini ----------
    tmp = Path(tempfile.mkdtemp(prefix="nanoamp-bundledr-"))
    try:
        local = tmp / "LocalAppData"
        local.mkdir(parents=True, exist_ok=True)
        root = local / "nanoamp"
        expected = build_fake_install(root)

        saved = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "NANOAMP_HOME", "NANOAMP_RSCRIPT")}
        os.environ["LOCALAPPDATA"] = str(local)
        os.environ.pop("NANOAMP_HOME", None)
        os.environ.pop("NANOAMP_RSCRIPT", None)
        try:
            found = rr.find_rscript()
            ok = found == expected
            print(f"  default install  -> {found}")
            if not ok:
                failures.append(f"expected {expected}, got {found}")
        except rr.RNotFoundError as exc:
            print(f"  default install  -> NOT FOUND\n{exc}")
            failures.append("bundled R under %LOCALAPPDATA%\\nanoamp was not found")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # --- case 2: a non-default install, found via the pointer file -----
        custom = tmp / "elsewhere" / "nanoamp-custom"
        expected2 = build_fake_install(custom)
        (local / "nanoamp.path").write_text(str(custom), encoding="utf-8")
        saved = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "NANOAMP_HOME", "NANOAMP_RSCRIPT")}
        os.environ["LOCALAPPDATA"] = str(local)
        os.environ.pop("NANOAMP_HOME", None)
        os.environ.pop("NANOAMP_RSCRIPT", None)
        try:
            found = rr.find_rscript()
            ok = found == expected2
            print(f"  moved install    -> {found}")
            if not ok:
                failures.append(f"expected {expected2}, got {found}")
        except rr.RNotFoundError as exc:
            print(f"  moved install    -> NOT FOUND")
            failures.append("bundled R recorded in nanoamp.path was not found")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # --- case 3: NANOAMP_HOME wins when nothing is installed ------------
        cfgroot = tmp / "cfgonly"
        expected3 = build_fake_install(cfgroot)
        saved = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "NANOAMP_HOME", "NANOAMP_RSCRIPT")}
        os.environ["LOCALAPPDATA"] = str(tmp / "empty-local")
        os.environ["NANOAMP_HOME"] = str(cfgroot)
        os.environ.pop("NANOAMP_RSCRIPT", None)
        try:
            found = rr.find_rscript()
            ok = found == expected3
            print(f"  NANOAMP_HOME     -> {found}")
            if not ok:
                failures.append(f"expected {expected3}, got {found}")
        except rr.RNotFoundError:
            print(f"  NANOAMP_HOME     -> NOT FOUND")
            failures.append("NANOAMP_HOME did not lead to the bundled R")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v

        # --- case 4: the error message still lists what was tried -----------
        # Note the well-known locations are still searched, so on a machine
        # that really has R (like the dev box) this case cannot raise. Only
        # assert the error shape when there genuinely is no R to be found.
        saved = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "NANOAMP_HOME", "NANOAMP_RSCRIPT")}
        os.environ["LOCALAPPDATA"] = str(tmp / "nothing-here")
        os.environ.pop("NANOAMP_HOME", None)
        os.environ.pop("NANOAMP_RSCRIPT", None)
        try:
            found = rr.find_rscript()
            print(f"  nothing installed-> found a system R at {found} (acceptable)")
        except rr.RNotFoundError as exc:
            mentions_ini = "config.ini" in str(exc) or "nanoamp" in str(exc)
            print(f"  nothing installed-> raised with {len(str(exc).splitlines())} lines")
            if not mentions_ini:
                failures.append("error message does not mention where it looked")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 62)
    if failures:
        print(f"FAIL  {len(failures)} problem(s):")
        for f in failures:
            print("   -", f)
        return 1
    print("PASS  bundled-R lookup (default, moved, NANOAMP_HOME, none)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
