"""Prove the installer retries file copies that Windows has locked.

Why: a real install failed with

    PermissionError: [WinError 32] 另一个程序正在使用此文件，进程无法访问。
      File install_nanoamp.py, line 1268, in _configure_gui -> shutil.copy2

because the previous GUI was still running (PyInstaller onefile keeps a child
process alive, which holds <install>\\app\\nanoamp.exe). Antivirus scanning a
freshly written .exe produces the same error. `copy_with_retry` now retries with
a growing delay, mirroring the uninstaller's delete retries.

Cases:
  1. a lock that clears after a few attempts       -> copy succeeds
  2. a lock that never clears                      -> clear error, N attempts made
  3. a real Windows sharing violation (msvcrt)     -> succeeds once released
  4. destination directory does not exist yet      -> created

    python release/_installer/test_copy_retry.py
"""
from __future__ import annotations

import threading
import time
from pathlib import Path
import shutil
import sys
import tempfile

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_nanoamp as ins  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("   OK   " if ok else "   FAIL ") + what)
    if not ok:
        failures.append(what)


print("=== 0) the production ladder ===")
check(len(ins.COPY_RETRY_DELAYS) >= 3,
      f"retries several times ({len(ins.COPY_RETRY_DELAYS)} attempts)")
check(ins.COPY_RETRY_DELAYS[0] == 0.0 and list(ins.COPY_RETRY_DELAYS) == sorted(ins.COPY_RETRY_DELAYS),
      f"delays grow and the first attempt is immediate {ins.COPY_RETRY_DELAYS}")
check(ins.COPY_RETRY_DELAYS[-1] >= 2.0,
      "the last wait is long enough for an antivirus scan to finish")

# Keep the test quick without changing what is being tested: the retry logic is
# driven by this constant.
real_delays = ins.COPY_RETRY_DELAYS
ins.COPY_RETRY_DELAYS = (0.0, 0.01, 0.02, 0.03)

tmp = Path(tempfile.mkdtemp(prefix="nanoamp-copyretry-"))
try:
    src = tmp / "payload" / "minimap2.exe"
    src.parent.mkdir(parents=True, exist_ok=True)
    src.write_bytes(b"binary-payload" * 100)

    print("\n=== 1) a lock that clears after a few attempts ===")
    dst = tmp / "out" / "minimap2.exe"
    attempts = {"n": 0}
    real_copy = shutil.copy2
    lines: list[str] = []

    def flaky(a, b, *args, **kwargs):
        attempts["n"] += 1
        if attempts["n"] <= 3:
            raise PermissionError(32, "另一个程序正在使用此文件，进程无法访问。")
        return real_copy(a, b, *args, **kwargs)

    ins.shutil.copy2 = flaky
    try:
        result = ins.copy_with_retry(src, dst, lines.append)
    finally:
        ins.shutil.copy2 = real_copy
    check(attempts["n"] == 4, f"kept trying until it worked ({attempts['n']} attempts)")
    check(result == dst and dst.read_bytes() == src.read_bytes(),
          "the file really landed, byte for byte")
    check(any("复制未完成" in line for line in lines),
          "the retry is reported in the install log")
    check(any("复制成功" in line for line in lines), "the successful retry is reported too")

    print("\n=== 2) a lock that never clears ===")
    dst2 = tmp / "out2" / "nanoamp.exe"
    attempts["n"] = 0

    def always_locked(a, b, *args, **kwargs):
        attempts["n"] += 1
        raise PermissionError(32, "另一个程序正在使用此文件，进程无法访问。")

    ins.shutil.copy2 = always_locked
    raised: Exception | None = None
    try:
        ins.copy_with_retry(src, dst2)
    except OSError as exc:
        raised = exc
    finally:
        ins.shutil.copy2 = real_copy
    check(raised is not None, "it fails instead of pretending to succeed")
    if raised is not None:
        text = str(raised)
        check(attempts["n"] == len(ins.COPY_RETRY_DELAYS),
              f"all {len(ins.COPY_RETRY_DELAYS)} attempts were made ({attempts['n']})")
        check("关闭正在运行的 nanoamp" in text,
              "the error tells the user what to do about it")
        check(str(dst2) in text, "the error names the file it could not write")

    print("\n=== 3) a real Windows sharing violation ===")
    try:
        import msvcrt  # noqa: PLC0415 - Windows only
    except ImportError:
        print("   skip  (not Windows)")
    else:
        dst3 = tmp / "out3" / "nanoamp.exe"
        dst3.parent.mkdir(parents=True, exist_ok=True)
        dst3.write_bytes(b"locked-by-another-program")
        holder = open(dst3, "r+b")
        msvcrt.locking(holder.fileno(), msvcrt.LK_NBLCK, 1)
        result: dict[str, object] = {}

        def run() -> None:
            try:
                result["path"] = ins.copy_with_retry(src, dst3, lines.append)
            except Exception as exc:  # noqa: BLE001 - reported below
                result["error"] = exc

        worker = threading.Thread(target=run)
        worker.start()
        time.sleep(0.05)
        held = worker.is_alive()
        msvcrt.locking(holder.fileno(), msvcrt.LK_UNLCK, 1)
        holder.close()
        worker.join(timeout=10)
        check(held, "the copy really was blocked while the file was locked")
        check("path" in result, f"and succeeded once the lock was released ({result.get('error')})")
        if "path" in result:
            check(dst3.read_bytes() == src.read_bytes(), "the locked destination was overwritten correctly")

    print("\n=== 4) destination directory is created ===")
    dst4 = tmp / "deep" / "nested" / "dir" / "file.bin"
    ins.shutil.copy2 = real_copy
    ins.copy_with_retry(src, dst4)
    check(dst4.is_file(), "the parent directories were created as needed")
finally:
    ins.COPY_RETRY_DELAYS = real_delays
    shutil.rmtree(tmp, ignore_errors=True)

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  copy retries: locked files are retried, then reported clearly")
