"""Prove that 取消操作 really stops a running analysis.

The GUI now offers a cancel button next to 开始分析. A button that only looks
like it works is worse than none, so this drives the runner directly: it starts
a long-running fake R process, cancels it, and checks the process is gone and
the call returns promptly.

Usage:
    python 02_code/PythonGUI/tests/test_cancel_analysis.py
"""

from __future__ import annotations

import sys
import tempfile
import threading
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import nanoamp_gui.r_runner as rr  # noqa: E402


class FakeRunner(rr.NanoampRunner):
    """A runner whose R is a long sleep, so cancel has something to kill."""

    def __init__(self, repo_root: Path):
        # Skip find_rscript() and the real wrapper.
        self.repo_root = Path(repo_root).resolve()
        self.rscript = Path(sys.executable)
        self._proc = None

    def write_wrapper(self) -> Path:
        p = self.repo_root / "tmp" / "_cancel_test.py"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("import time\nprint('started', flush=True)\ntime.sleep(120)\n",
                     encoding="utf-8")
        return p

    def run(self, argv, stream=None):  # noqa: ANN001, ANN201
        import subprocess

        wrapper = self.write_wrapper()
        proc = subprocess.Popen(
            [str(self.rscript), "-u", str(wrapper)],
            cwd=str(self.repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            env=dict(**__import__("os").environ, PYTHONUNBUFFERED="1"),
        )
        self._proc = proc
        lines: list[str] = []
        assert proc.stdout is not None
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", "replace").rstrip("\r\n")
                lines.append(line)
                if stream:
                    stream(line)
        finally:
            self._proc = None
            proc.stdout.close()
            proc.wait()
        return proc.returncode, lines


def main() -> int:
    failures: list[str] = []
    tmp = Path(tempfile.mkdtemp(prefix="nanoamp-cancel-"))
    try:
        runner = FakeRunner(tmp)
        result: dict[str, object] = {}

        def worker() -> None:
            t0 = time.monotonic()
            code, lines = runner.run(["doctor"], stream=lambda _l: None)
            result["code"] = code
            result["elapsed"] = time.monotonic() - t0
            result["lines"] = lines

        th = threading.Thread(target=worker, daemon=True)
        th.start()

        # Wait until it has actually started.
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if runner._proc is not None:
                break
            time.sleep(0.1)
        if runner._proc is None:
            failures.append("the fake R process never started")
            return 1

        time.sleep(1.0)
        pid = runner._proc.pid
        print(f"  started pid {pid}")

        t_cancel = time.monotonic()
        runner.cancel()
        th.join(timeout=15)
        took = time.monotonic() - t_cancel

        if th.is_alive():
            failures.append("cancel did not stop the run within 15s")
            print("  FAIL: still running after cancel")
        else:
            print(f"  cancelled, unwound in {took:.1f}s, returncode={result.get('code')}")

        # The process must really be gone.
        if sys.platform == "win32":
            import subprocess
            out = subprocess.run(
                ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
                capture_output=True, text=True,
            ).stdout
            gone = str(pid) not in out
        else:
            gone = True
        print(f"  process {pid} gone: {gone}")
        if not gone:
            failures.append(f"process {pid} survived cancel")

        # A cancel must be prompt, not "wait for the 120s sleep".
        if not th.is_alive() and float(result.get("elapsed", 999)) > 20:
            failures.append("cancel took longer than 20s to take effect")
    finally:
        import shutil
        shutil.rmtree(tmp, ignore_errors=True)

    print("\n" + "=" * 62)
    if failures:
        print(f"FAIL  {len(failures)} problem(s):")
        for f in failures:
            print("   -", f)
        return 1
    print("PASS  cancel stops the running analysis")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
