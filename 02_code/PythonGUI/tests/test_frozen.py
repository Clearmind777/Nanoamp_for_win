"""Verify the frozen bundle behaves correctly.

PyInstaller was frozen with console=False, so R output has nowhere to go. This
launches the exe and, separately, confirms the path-resolution logic that the
frozen build relies on.
"""
from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUI = HERE.parent
REPO = GUI.parent
EXE = GUI / "dist" / "nanoamp.exe"

print("exe exists :", EXE.is_file(), f"({EXE.stat().st_size / 1024 / 1024:.1f} MB)" if EXE.is_file() else "")

# What the frozen app computes from sys.executable = <repo>\02_code/PythonGUI\dist\nanoamp.exe
frozen_base = EXE.parent
print("\nfrozen resource_base() would be:", frozen_base)
root = frozen_base.resolve()
for _ in range(8):
    if (root / "03_dependence").is_dir() or (root / "02_code").is_dir():
        break
    root = root.parent
print("frozen find_repo_root()        :", root)
assert (root / "03_dependence").is_dir(), "frozen build would not find the repo root"
assert (root / "03_dependence" / "windows-x86_64" / "bin" / "minimap2.exe").is_file()
print("minimap2.exe reachable from frozen root: OK")

# Standard library only - the excluded packages must not be needed.
print("\nlaunching the exe and checking it stays up...")
proc = subprocess.Popen([str(EXE)])
time.sleep(8)
alive = proc.poll() is None
print("still running after 8s:", alive)
proc.terminate()
try:
    proc.wait(timeout=10)
except subprocess.TimeoutExpired:
    proc.kill()
assert alive, "the exe exited on its own - it would have shown a dialog with the reason"
print("\nFROZEN BUILD OK")
