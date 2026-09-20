"""Prove that the uninstaller copes with a locked file.

Windows refuses to delete a file while another process holds an open handle to
it, which is the normal case right after the GUI was used: the user closes the
window, the process lingers for a moment, and uninstall.exe starts working.

Run with:

    python release/_installer/test_locked_file_retry.py

Three cases are covered:

  1. a running nanoamp.exe inside the install dir      -> must be stopped and
     the tree deleted (this is the everyday case: the user left the GUI open)
  2. the lock is never released                        -> must fail loudly,
     and the directory must still be there afterwards (no half-deleted tree
     reported as success)
  3. a free directory                                  -> must succeed on the
     first attempt with no delay
"""

from __future__ import annotations

import msvcrt
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import uninstall_nanoamp as un  # noqa: E402


class Harness:
    """Minimal stand-in for an installed nanoamp tree."""

    def __init__(self, root: Path):
        self.root = root
        (root / "bin").mkdir(parents=True, exist_ok=True)
        (root / "app").mkdir(parents=True, exist_ok=True)
        (root / "bin" / "nanoamp.cmd").write_text("@echo off\r\n", encoding="ascii")
        (root / "app" / "payload.txt").write_text("x" * 4096, encoding="ascii")

    def lock(self, relative: str = "app/payload.txt"):
        """Open + region-lock a file so Windows refuses to unlink it."""
        handle = open(self.root / relative, "r+b")
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return handle

    @staticmethod
    def unlock(handle) -> None:
        try:
            handle.seek(0)
            msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        finally:
            handle.close()


def drain(events: queue.Queue) -> list[str]:
    out: list[str] = []
    while not events.empty():
        item = events.get()
        if item and item[0] == "log":
            out.append(item[1])
    return out


def attempt(root: Path) -> tuple[bool, list[str], float]:
    plan = un.Plan(install_root=root, remove_dir=True, remove_shortcut=False)
    events: queue.Queue = queue.Queue()
    inst = un.Uninstaller(plan, events)
    t0 = time.monotonic()
    ok = inst._remove_dir()
    return ok, drain(events), time.monotonic() - t0


def show(name: str, ok: bool, gone: bool, elapsed: float, logs: list[str]) -> None:
    print(f"\n=== {name} ===")
    for line in logs:
        print("   ", line)
    print(f"    ok={ok}  removed={gone}  elapsed={elapsed:.2f}s")


def cleanup(root: Path) -> None:
    for _ in range(4):
        if not root.exists():
            break
        shutil.rmtree(root, ignore_errors=True)
        time.sleep(0.2)
    try:
        root.parent.rmdir()
    except OSError:
        pass


def main() -> int:
    results: list[bool] = []
    real_delays = un.REMOVE_RETRY_DELAYS
    real_sleep = un.time.sleep
    # The code path is identical, only the schedule is compressed.
    un.REMOVE_RETRY_DELAYS = (0.0, 0.4, 0.8, 1.2)
    un.time.sleep = lambda s: real_sleep(min(s, 0.4))

    try:
        # Case 1: the GUI (here a stand-in process) is still running from inside
        # the install dir, so its own image file is locked. This is the everyday
        # case: the user left nanoamp open and ran the uninstaller anyway.
        py = Path(sys.executable)
        if py.is_file():
            root = Path(tempfile.mkdtemp(prefix="nanoamp-running-")) / "nanoamp"
            Harness(root)
            holder = root / "bin" / "nanoamp.exe"
            shutil.copy2(py, holder)
            sleeper = root / "bin" / "loop.py"
            sleeper.write_text("import time\ntime.sleep(60)\n", encoding="ascii")
            child = subprocess.Popen([str(holder), str(sleeper)])
            try:
                time.sleep(1.0)  # let the process start and lock its own image
                ok, logs, elapsed = attempt(root)
                gone = not root.exists()
                show("nanoamp.exe still running (must stop it, then delete)",
                     ok, gone, elapsed, logs)
                good = ok and gone and any("结束仍在运行的" in line for line in logs)
                if not good:
                    print("    FAIL: a running nanoamp.exe was not stopped and removed")
                results.append(good)
            finally:
                if child.poll() is None:
                    child.kill()
                    child.wait(timeout=10)
                cleanup(root)
        else:
            print("\n(skipping the running-process case: python.exe not found)")

        # Case 2: a lock that is never released.
        root = Path(tempfile.mkdtemp(prefix="nanoamp-lock-")) / "nanoamp"
        harness = Harness(root)
        handle = harness.lock()
        ok, logs, elapsed = attempt(root)
        gone = not root.exists()
        show("lock never released (must fail and keep the tree)", ok, gone, elapsed, logs)
        joined = " ".join(logs)
        attempts = sum(1 for line in logs if "次删除未完成" in line)
        good = (
            (not ok)
            and root.exists()
            and "删除失败" in joined
            and attempts == len(un.REMOVE_RETRY_DELAYS)
            and "payload.txt" in joined
        )
        if not good:
            print("    FAIL: expected a loud failure that names the locked file")
        results.append(good)
        Harness.unlock(handle)
        cleanup(root)

        # Case 3: nothing locked at all.
        root = Path(tempfile.mkdtemp(prefix="nanoamp-free-")) / "nanoamp"
        Harness(root)
        ok, logs, elapsed = attempt(root)
        gone = not root.exists()
        show("nothing locked (must delete immediately)", ok, gone, elapsed, logs)
        retried = any("次删除未完成" in line for line in logs)
        good = ok and gone and not retried
        if not good:
            print("    FAIL: expected a first-attempt success with no retry chatter")
        results.append(good)
        cleanup(root)

        # Case 4: a read-only file. Windows says no to unlinking it, and R and
        # the offline bundle both leave some behind.
        root = Path(tempfile.mkdtemp(prefix="nanoamp-ro-")) / "nanoamp"
        Harness(root)
        ro = root / "app" / "readonly.dat"
        ro.write_text("read only\n", encoding="ascii")
        os.chmod(ro, 0o444)
        ok, logs, elapsed = attempt(root)
        gone = not root.exists()
        show("read-only file (must clear the bit and delete)", ok, gone, elapsed, logs)
        good = ok and gone
        if not good:
            print("    FAIL: a read-only file stopped the uninstall")
        results.append(good)
        try:
            os.chmod(ro, 0o666)
        except OSError:
            pass
        cleanup(root)
    finally:
        un.REMOVE_RETRY_DELAYS = real_delays
        un.time.sleep = real_sleep

    print("\n" + "=" * 60)
    if all(results):
        print(f"PASS  {len(results)}/{len(results)} locked-file retry cases")
        return 0
    print(f"FAIL  {sum(results)}/{len(results)} locked-file retry cases")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
