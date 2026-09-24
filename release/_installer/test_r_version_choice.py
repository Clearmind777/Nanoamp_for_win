"""Prove the installer picks an R that the bundle can actually serve.

The case this locks down is the one users hit in practice:

    the machine has R 4.5, the bundle carries 109 packages compiled for R 4.6

R's binary packages are not compatible across minor versions, so R 4.5 can never
be used with those packages. The installer used to accept it anyway (the check
was only ">= 4.2") and then fail in the dependency step, telling the user to go
find a matching R -- even though the bundle ships its own R 4.6 installer.

Run with:

    python release/_installer/test_r_version_choice.py
"""

from __future__ import annotations

import queue
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import install_nanoamp as ins  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("   OK   " if ok else "   FAIL ") + what)
    if not ok:
        failures.append(what)


# ---------------------------------------------------------------------------
print("=== r_choice(): the decision table ===")
CASES = [
    (["4.6"], (4, 6), "system", "matching version -> use the system R"),
    (["4.6"], (4, 5), "bundled", "R 4.5 with a 4.6 bundle -> install the bundled R"),
    (["4.6"], (4, 4), "bundled", "older minor -> bundled"),
    (["4.6"], (5, 0), "bundled", "newer minor -> bundled (binaries still differ)"),
    (["4.6"], (4, 2), "bundled", ">= minimum but mismatched -> bundled"),
    (["4.6"], (3, 6), "bundled", "too old -> bundled"),
    (["4.6"], None, "bundled", "no R at all -> bundled"),
    ([], (4, 5), "system", "bundle without packages -> any supported R"),
    ([], (4, 1), "bundled", "bundle without packages, R too old -> bundled"),
    (["4.5", "4.6"], (4, 5), "system", "multi-tag bundle -> matching system R"),
]
for tags, version, want, why in CASES:
    got = ins.r_choice(tags, version)
    check(got == want, f"r_choice({tags}, {version}) = {got} (want {want}) -- {why}")


# ---------------------------------------------------------------------------
def ensure_r(tags: list[str], version: tuple[int, int] | None, system_r: Path | None):
    """Run _ensure_r with stubbed version detection and R installation."""
    with tempfile.TemporaryDirectory(prefix="nanoamp-rchoice-") as tmp:
        root = Path(tmp) / "bundle"
        (root / "_offline" / "r").mkdir(parents=True)
        (root / "_offline" / "r" / "R-4.6.1-win.exe").write_bytes(b"stub installer")
        target = Path(tmp) / "install"

        ctx = ins.Context(root=root, install_root=target,
                          make_shortcut=False, touch_path=False)
        inst = ins.Installer(ctx, queue.Queue())

        orig = (ins.Context.available_r_tags, ins.find_rscript,
                ins.r_version, ins.Installer.run)

        def fake_run(self, cmd, timeout=0):
            rdir = next(Path(a.split("=", 1)[1]) for a in cmd if a.startswith("/DIR="))
            (rdir / "bin").mkdir(parents=True, exist_ok=True)
            (rdir / "bin" / "Rscript.exe").write_bytes(b"stub")
            return 0, ""

        ins.Context.available_r_tags = lambda self: tags
        ins.find_rscript = lambda: system_r
        ins.r_version = lambda path: version if system_r is not None and Path(path) == system_r else None
        ins.Installer.run = fake_run
        try:
            ok = inst._ensure_r()
        finally:
            (ins.Context.available_r_tags, ins.find_rscript,
             ins.r_version, ins.Installer.run) = orig
        return ok, inst, list(ctx.log)


print("\n=== the installer actually switches to the bundled R ===")

real_r = ins.find_rscript()
print(f"   (system R on this machine: {real_r})")

# The reported case: R 4.5 installed, bundle has 4.6 packages.
fake45 = Path(tempfile.gettempdir()) / "fake-R-4.5" / "bin" / "Rscript.exe"
fake45.parent.mkdir(parents=True, exist_ok=True)
fake45.write_bytes(b"stub")

ok, inst, log = ensure_r(["4.6"], (4, 5), fake45)
joined = "\n".join(log)
check(ok, "install proceeds instead of failing on the version mismatch")
check(inst.rscript is not None and "R-runtime" in str(inst.rscript),
      f"uses the bundled R runtime ({inst.rscript})")
check("为 R 4.6 编译的" in joined, "explains that the bundled packages are for R 4.6")
check("R 4.5" in joined, "names the R version it found on the machine")
check("不会改动也不会卸载你现有的 R" in joined, "reassures that the existing R is untouched")

# Control: a matching system R is still preferred (no 500 MB install).
if real_r is not None:
    ver = ins.r_version(real_r)
    if ver is not None:
        ok, inst, log = ensure_r([f"{ver[0]}.{ver[1]}"], ver, real_r)
        check(ok and Path(inst.rscript) == real_r,
              f"matching system R {ver[0]}.{ver[1]} is used as-is")
        check(any("检测到已安装的 R" in line for line in log),
              "logs the detected system R")

# Control: nothing installed at all.
ok, inst, log = ensure_r(["4.6"], None, None)
check(ok and inst.rscript is not None and "R-runtime" in str(inst.rscript),
      "with no system R the bundled one is installed (unchanged behaviour)")

# The fake R 4.5 tree is only a stub file; clean it up.
try:
    fake45.parent.parent.rmdir()
    fake45.parent.rmdir()
except OSError:
    pass

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  R version choice: matching system R is used, mismatching R falls back "
      "to the bundled one")
