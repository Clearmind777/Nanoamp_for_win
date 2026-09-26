"""install.exe now leaves uninstall.exe inside the install directory.

That makes two new things testable without installing anything:

  * ``nanoamp_common.config_candidates()`` prefers the config.ini next to the
    running program, so the copy inside the install directory describes that
    installation even if the pointer file is gone;
  * the uninstaller can remove a directory that contains *itself*: everything
    else goes immediately and the running exe (which Windows keeps locked) is
    handed to a detached helper that deletes it once this process is gone.

Usage:
    python release/_installer/test_uninstaller_selfdelete.py
"""

from __future__ import annotations

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import nanoamp_common as common  # noqa: E402
import uninstall_nanoamp as un  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("   OK   " if ok else "   FAIL ") + what + (f"  -- {extra}" if extra else ""))
    if not ok:
        failures.append(what)


def check_config_candidates() -> None:
    """A config.ini beside the running program wins."""
    tmp = Path(tempfile.mkdtemp(prefix="nanoamp-cfg-"))
    try:
        here = tmp / "install"
        here.mkdir()
        (here / "config.ini").write_text(
            f"[nanoamp]\nhome={here}\nrscript={here / 'R' / 'Rscript.exe'}\n",
            encoding="utf-8",
        )
        default = tmp / "localappdata" / "nanoamp"
        default.mkdir(parents=True)
        (default / "config.ini").write_text("[nanoamp]\nhome=elsewhere\n",
                                            encoding="utf-8")
        pointer_dir = tmp / "moved"
        pointer_dir.mkdir()
        (pointer_dir / "config.ini").write_text("[nanoamp]\nhome=moved\n",
                                                encoding="utf-8")

        saved_env = {k: os.environ.get(k) for k in ("LOCALAPPDATA", "NANOAMP_HOME")}
        real_running = common.running_dir
        os.environ["LOCALAPPDATA"] = str(tmp / "localappdata")
        os.environ.pop("NANOAMP_HOME", None)
        try:
            common.write_pointer(pointer_dir)
            common.running_dir = lambda: here           # pretend we run from there
            candidates = common.config_candidates()
            print(f"  candidates: {[str(c) for c in candidates[:3]]}")
            check(candidates and candidates[0] == here / "config.ini",
                  "the config.ini next to the program comes first",
                  str(candidates[0]) if candidates else "(none)")
            check(len(candidates) == len({os.path.normcase(str(c)) for c in candidates}),
                  "candidates contain no duplicates")

            found = common.find_existing_install()
            check(found is not None and found[0] == here,
                  "so the installed uninstaller finds its own installation",
                  str(found[0]) if found else "(none)")
        finally:
            common.running_dir = real_running
            common.remove_pointer()
            for k, v in saved_env.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def check_inside() -> None:
    root = Path(tempfile.mkdtemp(prefix="nanoamp-inside-"))
    try:
        (root / "app").mkdir()
        inside = root / "uninstall.exe"
        inside.write_bytes(b"MZ")
        check(un._inside(inside, root), "a file in the install root counts as inside")
        check(un._inside(root / "app" / "nanoamp.exe", root),
              "so does a file in a subdirectory")
        check(not un._inside(root, root), "the root itself is not inside")
        check(not un._inside(Path(tempfile.gettempdir()) / "x.exe", root),
              "an unrelated file is not inside")
        check(un._running_exe() is None,
              "from source there is no frozen exe to delete")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_remove_tree_skipping() -> None:
    """Everything except the running exe goes; a real lock still reports."""
    root = Path(tempfile.mkdtemp(prefix="nanoamp-rmtree-"))
    try:
        (root / "app").mkdir()
        (root / "app" / "nanoamp.exe").write_bytes(b"MZ")
        (root / "bin").mkdir()
        (root / "bin" / "minimap2.exe").write_bytes(b"MZ")
        me = root / "uninstall.exe"
        me.write_bytes(b"MZ")

        un._remove_tree_skipping(root, {me.resolve()})
        check(me.is_file(), "the running exe is left in place")
        check(not (root / "app").exists() and not (root / "bin").exists(),
              "everything else is gone")
        check(root.is_dir(), "the directory itself stays until the exe is gone")

        # A file held open cannot be deleted; that must raise, not pass silently.
        locked = root / "locked.exe"
        locked.write_bytes(b"MZ")
        fd = os.open(str(locked), os.O_RDONLY)
        try:
            raised = ""
            try:
                un._remove_tree_skipping(root, {me.resolve()})
            except OSError as exc:
                raised = str(exc)
            check(bool(raised), "a locked file is reported instead of ignored", raised)
        finally:
            os.close(fd)
        locked.unlink()
        me.unlink()
        un._remove_tree_skipping(root, set())
        check(not root.exists(), "with nothing locked the directory disappears")
    finally:
        shutil.rmtree(root, ignore_errors=True)


def check_scheduled_cleanup() -> None:
    """The detached helper deletes the exe and the directory after we exit."""
    root = Path(tempfile.mkdtemp(prefix="nanoamp-sched-"))
    exe = root / "uninstall.exe"
    exe.write_bytes(b"MZ")
    script = Path(tempfile.gettempdir()) / f"nanoamp_finish_uninstall_{os.getpid()}.cmd"
    script.unlink(missing_ok=True)
    try:
        ok = un._schedule_final_cleanup(exe.resolve(), root)
        check(ok, "the cleanup helper starts")

        # Windows keeps a *running* exe locked: hold the file open for a moment
        # and only then release it. The helper must keep retrying - waiting for
        # the file to disappear on its own would wait forever.
        fd = os.open(str(exe), os.O_RDONLY)
        time.sleep(2.0)
        os.close(fd)
        exe.unlink()
        deadline = time.time() + 25
        while time.time() < deadline and root.exists():
            time.sleep(0.5)
        check(not root.exists(), "the helper removes the directory",
              f"still there after 25 s: {root}")
        check(not script.exists(), "and the helper removes itself", str(script))
    finally:
        shutil.rmtree(root, ignore_errors=True)
        script.unlink(missing_ok=True)


print("=== 1) config.ini next to the running program wins ===")
check_config_candidates()

print("\n=== 2) is the running exe inside the install root? ===")
check_inside()

print("\n=== 3) deleting a directory that contains the running uninstaller ===")
check_remove_tree_skipping()

print("\n=== 4) the detached helper finishes the job ===")
check_scheduled_cleanup()

print()
if failures:
    print(f"FAIL  {len(failures)} problem(s):")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  installer places a self-deleting uninstaller (helpers verified)")
