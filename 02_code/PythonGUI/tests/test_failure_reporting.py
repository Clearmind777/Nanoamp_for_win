"""A failed run must explain itself - in the GUI and in the output directory.

Covers P0-7 end to end:

  * `run_manifest.json` of a failed run carries status / error_class /
    error_message / log_path (checked against a real CLI run, not a fixture);
  * the GUI maps each `error_class` to its own hint instead of one generic
    "analysis failed" dialog, and falls back safely for an unknown class;
  * a cancelled run is recorded as `cancelled`, because a killed R process
    cannot write that itself.

    python 02_code/PythonGUI/tests/test_failure_reporting.py
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUI = HERE.parent
sys.path.insert(0, str(GUI))

from nanoamp_gui.app import (  # noqa: E402
    ERROR_CLASS_FALLBACK, ERROR_CLASS_HINTS, NanoampApp, find_repo_root,
    resource_base,
)
from nanoamp_gui.r_runner import NanoampRunner  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("   OK   " if ok else "   FAIL ") + what + (f"  -- {extra}" if extra else ""))
    if not ok:
        failures.append(what)


print("=== 1) every documented error_class has its own hint ===")
for cls in ("input", "environment", "network", "internal"):
    hint = NanoampApp._failure_hint({"error_class": cls})[1]
    check(hint != ERROR_CLASS_FALLBACK and len(hint) > 20,
          f"{cls} has a class-specific hint", hint.splitlines()[0][:40])
check("离线" in ERROR_CLASS_HINTS["network"],
      "the network hint points at the offline CDS route")
check(NanoampApp._failure_hint({})[1] == ERROR_CLASS_FALLBACK,
      "a manifest without error_class falls back safely")
check(NanoampApp._failure_hint({"error_class": "nonsense"})[1] == ERROR_CLASS_FALLBACK,
      "an unknown error_class falls back safely")

print("\n=== 2) manifest reading is defensive ===")
td = Path(tempfile.mkdtemp(prefix="nanoamp_fail_"))
check(NanoampApp._read_manifest(td) == {}, "a missing manifest reads as {}")
(td / "run_manifest.json").write_text("{not json", encoding="utf-8")
check(NanoampApp._read_manifest(td) == {}, "unparsable JSON reads as {}")
(td / "run_manifest.json").write_text(json.dumps({"status": "failed"}), encoding="utf-8")
check(NanoampApp._read_manifest(td).get("status") == "failed", "a real manifest is read")

print("\n=== 3) cancellation is recorded, not deleted ===")
outdir = td / "cancelled"
outdir.mkdir()
(outdir / "run_manifest.json").write_text(
    json.dumps({"status": "done", "mode": "A", "qc": {"n_reads_total": 12}}),
    encoding="utf-8",
)
app = NanoampApp.__new__(NanoampApp)          # no window needed for this call
app._append_log = lambda _line: None
app._mark_cancelled(outdir)
info = json.loads((outdir / "run_manifest.json").read_text(encoding="utf-8"))
check(info.get("status") == "cancelled", "status becomes cancelled")
check(info.get("cancelled_by") == "gui", "the writer is recorded")
check(info.get("qc", {}).get("n_reads_total") == 12,
      "the existing content is preserved")
check(info.get("mode") == "A", "unrelated keys survive")
empty = td / "cancel_without_manifest"
empty.mkdir()
app._mark_cancelled(empty)
check(json.loads((empty / "run_manifest.json").read_text(encoding="utf-8")).get("status")
      == "cancelled", "a manifest is created when none existed")

print("\n=== 4) a real failed CLI run writes a readable manifest ===")
root = find_repo_root(resource_base())
runner = NanoampRunner(root)
work = td / "run"
work.mkdir()
ref = work / "ref.fa"
ref.write_text(">r\n" + "ACGT" * 60 + "\n", encoding="utf-8")
out = work / "out"
code, lines = runner.run([
    "call",
    "--reads", str(work / "does-not-exist.fastq"),
    "--reference", str(ref),
    "--outdir", str(out),
    "--mode", "A",
    "--no-intermediates",
])
print("      returncode:", code)
manifest = out / "run_manifest.json"
check(code != 0, "a missing FASTQ exits non-zero")
check(manifest.is_file(), "run_manifest.json exists for the failed run")
if manifest.is_file():
    info = json.loads(manifest.read_text(encoding="utf-8"))
    check(info.get("status") == "failed", "status is failed", str(info.get("status")))
    check(info.get("error_class") == "input", "error_class is input",
          str(info.get("error_class")))
    check(bool(str(info.get("error_message") or "").strip()),
          "error_message explains the failure",
          str(info.get("error_message"))[:60])
    log_path = str(info.get("log_path") or "")
    check(bool(log_path) and Path(log_path).is_file(),
          "log_path points at an existing file", log_path)
    check(Path(log_path).read_text(encoding="utf-8", errors="replace").strip() != "",
          "the log file is not empty")
    cls, hint = NanoampApp._failure_hint(info)
    check(cls == "input" and "FASTQ" in hint,
          "the GUI picks the input hint for this failure")

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  failure reporting (manifest status/class/log + GUI hints)")
