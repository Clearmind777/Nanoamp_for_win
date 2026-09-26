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

The second half covers the sibling bug found later: with the install's
"add nanoamp to PATH" option unchecked, nanoamp.exe could not find
minimap2.exe, because app.find_repo_root() only knew the *default* install
location and therefore never handed <install>\\bin to the runner.

Usage:
    python 02_code/PythonGUI/tests/test_bundled_r_lookup.py
"""

from __future__ import annotations

import contextlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import nanoamp_gui.r_runner as rr  # noqa: E402


@contextlib.contextmanager
def env(**values):
    """Set environment variables for the duration of the block."""
    saved = {k: os.environ.get(k) for k in values}
    try:
        for k, v in values.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


def same(a: Path | None, b: Path | None) -> bool:
    """Compare two paths, tolerating 8.3 short names and case."""
    if a is None or b is None:
        return a is None and b is None
    try:
        return (os.path.normcase(str(Path(a).resolve()))
                == os.path.normcase(str(Path(b).resolve())))
    except OSError:
        return os.path.normcase(str(a)) == os.path.normcase(str(b))


def build_fake_install(root: Path) -> Path:
    """An install tree whose R lives only in the bundled runtime."""
    rscript = root / "R" / "R-runtime" / "bin" / "Rscript.exe"
    rscript.parent.mkdir(parents=True, exist_ok=True)
    rscript.write_bytes(b"fake")           # content is irrelevant
    (root / "R" / "lib").mkdir(parents=True, exist_ok=True)
    (root / "bin").mkdir(parents=True, exist_ok=True)
    # the aligner install.exe always copies here, PATH option or not
    (root / "bin" / "minimap2.exe").write_bytes(b"MZ")
    (root / "app").mkdir(parents=True, exist_ok=True)
    (root / "app" / "nanoamp.exe").write_bytes(b"MZ")
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


def check_library_paths(failures: list[str]) -> None:
    """The install's own R\\lib must be searched, and searched first.

    This is the second half of the same blind spot: with a bundled R the
    nanoamp package and its 109 dependencies live ONLY in
    <install_root>\\R\\lib. That path used to be absent from the wrapper's
    .libPaths(), so R could not find nanoamp and the GUI reported
    "环境检测失败(退出码1)" and "R 包未安装".
    """
    root = Path(tempfile.mkdtemp(prefix="nanoamp-libs-"))
    try:
        expected = (root / "R" / "lib").as_posix()
        (root / "R" / "lib").mkdir(parents=True, exist_ok=True)
        saved = {k: os.environ.get(k)
                 for k in ("NANOAMP_R_LIB", "LOCALAPPDATA", "NANOAMP_HOME")}
        os.environ.pop("NANOAMP_R_LIB", None)
        os.environ["NANOAMP_HOME"] = str(root)
        # Isolate from any installation recorded on this machine: an earlier
        # `install.exe` run (for example a sandbox one) leaves
        # %LOCALAPPDATA%\nanoamp.path behind, and its R\lib would then legitimately
        # come first - which is not what this check is about.
        os.environ["LOCALAPPDATA"] = str(root / "localappdata")
        try:
            libs = rr._candidate_libs(root)
            print(f"  candidate libs   -> {libs[:2]}{' ...' if len(libs) > 2 else ''}")
            if expected not in libs:
                failures.append(f"{expected} missing from candidate libs")
            elif libs[0] != expected:
                failures.append(f"install lib is not first (got {libs[0]})")
            if len(libs) != len(set(p.lower() for p in libs)):
                failures.append("duplicate entries in candidate libs")
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_repo_root_and_aligner(failures: list[str]) -> None:
    """The window must find <install>\\bin\\minimap2.exe with PATH untouched.

    Reported bug: installing with "将 nanoamp 命令加入用户 PATH" unchecked left
    nanoamp.exe unable to find minimap2.exe. The installer always copies the
    aligner into <install>\\bin, and the runner pins that copy through
    NANOAMP_MINIMAP2 - but only after app.find_repo_root() has found the install
    directory, and that function only looked at the *default* location. A
    relocated install therefore lost its aligner unless PATH happened to
    contain it.
    """
    try:
        from nanoamp_gui import app as gui_app
    except ImportError as exc:          # tkinter missing: the GUI cannot run here
        print(f"  install root     -> skipped ({exc})")
        return

    tmp = Path(tempfile.mkdtemp(prefix="nanoamp-root-"))
    try:
        local = tmp / "LocalAppData"
        local.mkdir(parents=True, exist_ok=True)

        # --- default location, no pointer file -----------------------------
        default_root = local / "nanoamp"
        build_fake_install(default_root)
        with env(LOCALAPPDATA=str(local), NANOAMP_HOME=None, NANOAMP_RSCRIPT=None):
            found = gui_app.find_repo_root(default_root / "app")
            print(f"  default install  -> repo_root {found}")
            if not same(found, default_root):
                failures.append(f"default install root: expected {default_root}, got {found}")
                return
            runner = rr.NanoampRunner(found)
            expected = default_root / "bin" / "minimap2.exe"
            got = runner.minimap2_path()
            print(f"  default install  -> minimap2 {got}")
            if not same(got, expected):
                failures.append(f"default install aligner: expected {expected}, got {got}")
            if not same(Path(runner._env().get("NANOAMP_MINIMAP2") or ""), expected):
                failures.append(
                    "the aligner is not pinned for R: NANOAMP_MINIMAP2="
                    f"{runner._env().get('NANOAMP_MINIMAP2')!r}")

        # --- relocated install, recorded in %LOCALAPPDATA%\\nanoamp.path -----
        custom = tmp / "elsewhere" / "nanoamp-custom"
        build_fake_install(custom)
        (local / "nanoamp.path").write_text(str(custom), encoding="utf-8")
        shutil.rmtree(default_root, ignore_errors=True)   # nothing at the default place
        with env(LOCALAPPDATA=str(local), NANOAMP_HOME=None, NANOAMP_RSCRIPT=None):
            found = gui_app.find_repo_root(custom / "app")
            print(f"  moved install    -> repo_root {found}")
            if not same(found, custom):
                failures.append(f"moved install root: expected {custom}, got {found}")
            else:
                runner = rr.NanoampRunner(found)
                expected = custom / "bin" / "minimap2.exe"
                got = runner.minimap2_path()
                print(f"  moved install    -> minimap2 {got}")
                if not same(got, expected):
                    failures.append(f"moved install aligner: expected {expected}, got {got}")
                if not same(Path(runner._env().get("NANOAMP_MINIMAP2") or ""), expected):
                    failures.append("the moved install's aligner is not pinned for R")

        # --- PATH is only the last resort ---------------------------------
        on_path = tmp / "pathdir"
        on_path.mkdir(parents=True, exist_ok=True)
        (on_path / "minimap2.exe").write_bytes(b"MZ")
        bare = tmp / "bare-install"
        build_fake_install(bare)
        (bare / "bin" / "minimap2.exe").unlink()
        (local / "nanoamp.path").write_text(str(bare), encoding="utf-8")
        with env(LOCALAPPDATA=str(local), NANOAMP_HOME=None, NANOAMP_RSCRIPT=None,
                 PATH=str(on_path) + os.pathsep + os.environ.get("PATH", "")):
            runner = rr.NanoampRunner(bare)
            got = runner.minimap2_path()
            print(f"  no bundled copy  -> minimap2 {got}")
            if got is None or got.name.lower() != "minimap2.exe":
                failures.append(f"PATH fallback did not find minimap2 (got {got})")

        # --- the repository's own copy wins over PATH (a checkout) ---------
        # Mirrors R, which walks up from its working directory looking for
        # 03_dependence; without this the window reported "no minimap2" on a
        # developer machine where the analysis works.
        checkout = tmp / "checkout"
        bundled = checkout / "03_dependence" / rr._platform_dir() / "bin" / "minimap2.exe"
        bundled.parent.mkdir(parents=True, exist_ok=True)
        bundled.write_bytes(b"MZ")
        (checkout / "02_code").mkdir(parents=True, exist_ok=True)
        build_fake_install(checkout)          # gives it an R and a config.ini
        (checkout / "bin" / "minimap2.exe").unlink()
        (local / "nanoamp.path").write_text(str(checkout), encoding="utf-8")
        with env(LOCALAPPDATA=str(local), NANOAMP_HOME=None, NANOAMP_RSCRIPT=None,
                 NANOAMP_MINIMAP2=None,
                 PATH=str(on_path) + os.pathsep + os.environ.get("PATH", "")):
            runner = rr.NanoampRunner(checkout)
            got = runner.minimap2_path()
            print(f"  checkout copy    -> minimap2 {got}")
            if not same(got, bundled):
                failures.append(f"the repository copy was not preferred (got {got})")

        # --- an explicit NANOAMP_MINIMAP2 still wins (R's own precedence) ---
        chosen = tmp / "chosen-minimap2.exe"
        chosen.write_bytes(b"MZ")
        with env(LOCALAPPDATA=str(local), NANOAMP_HOME=None, NANOAMP_RSCRIPT=None,
                 NANOAMP_MINIMAP2=str(chosen),
                 PATH=str(on_path) + os.pathsep + os.environ.get("PATH", "")):
            runner = rr.NanoampRunner(checkout)
            got = runner.minimap2_path()
            print(f"  NANOAMP_MINIMAP2 -> minimap2 {got}")
            if not same(got, chosen):
                failures.append(f"an explicit NANOAMP_MINIMAP2 was ignored (got {got})")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    failures: list[str] = []

    # --- library path resolution (the "R 包未安装" half of the bug) --------
    print("  library paths:")
    check_library_paths(failures)

    # --- install root + bundled aligner (the "minimap2 not found" report) --
    print("  install root and aligner:")
    check_repo_root_and_aligner(failures)

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
    print("PASS  install root + bundled aligner (default, moved, checkout, PATH, env)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
