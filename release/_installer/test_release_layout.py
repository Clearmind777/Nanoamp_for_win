"""Verify the three deliverables are genuinely separated and self-contained.

Checks, per deliverable:
  * its own directory holds everything it needs (no cross-references)
  * the pieces it references actually exist
  * install.exe can report a healthy installed state
  * the bundled minimap2 in release/_offline matches the repo copy
  * no file under release/ contains an absolute path from this machine
    (which would break for anyone else)

Read-only: installs nothing and does not touch PATH.
"""
from __future__ import annotations

import hashlib
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
RELEASE = REPO / "release"

FAIL = []


def check(ok: bool, label: str, detail: str = "") -> None:
    mark = "PASS" if ok else "FAIL"
    print(f"  [{mark}] {label}" + (f"  -- {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


print("=== 1) 三个交付形态目录 ===")
for name, must_have in (
    ("01_R-package", ["README.md"]),
    ("02_CLI", ["README.md", "bin/nanoamp.cmd"]),
    ("03_GUI", ["README.md", "nanoamp.exe"]),
):
    d = RELEASE / name
    check(d.is_dir(), f"{name}/ 存在")
    for f in must_have:
        check((d / f).is_file(), f"  {name}/{f}")

print("\n=== 2) R 包版：tarball 可被 R 识别 ===")
tarballs = list((RELEASE / "01_R-package").glob("nanoamp_*.tar.gz"))
check(len(tarballs) == 1, "恰好一个 tarball", tarballs[0].name if tarballs else "无")
if tarballs:
    check(tarballs[0].stat().st_size > 10_000, "tarball 体积合理",
          f"{tarballs[0].stat().st_size/1024:.1f} KB")

print("\n=== 3) CLI 版：启动器是纯 ASCII（cmd.exe 要求） ===")
cmd = RELEASE / "02_CLI" / "bin" / "nanoamp.cmd"
if cmd.is_file():
    raw = cmd.read_bytes()
    non_ascii = sum(1 for b in raw if b > 127)
    check(non_ascii == 0, "nanoamp.cmd 无非 ASCII 字节", f"{non_ascii} 个")
    text = raw.decode("ascii", "replace")
    check("rscript" in text, "启动器会从 config.ini 读取 rscript")
    check("R_LIBS_USER" in text, "启动器会设置 R_LIBS_USER")

print("\n=== 4) GUI 版：exe 与仓库内产物一致 ===")
gui_rel = RELEASE / "03_GUI" / "nanoamp.exe"
gui_dev = REPO / "02_code/PythonGUI" / "dist" / "nanoamp.exe"
check(gui_rel.is_file(), "release/03_GUI/nanoamp.exe 存在")
if gui_rel.is_file() and gui_dev.is_file():
    same = sha256(gui_rel) == sha256(gui_dev)
    check(same, "与 02_code/PythonGUI/dist/nanoamp.exe 一致",
          "" if same else f"{sha256(gui_rel)[:16]} vs {sha256(gui_dev)[:16]}")

print("\n=== 5) 离线依赖完整 ===")
off = RELEASE / "_offline"
check(off.is_dir(), "_offline/ 存在")
r_inst = list((off / "r").glob("R-*-win.exe"))
check(len(r_inst) == 1, "R 安装器存在", r_inst[0].name if r_inst else "无")
pkgs = list((off / "r-packages").rglob("*.zip"))
check(len(pkgs) >= 100, "R 包齐全", f"{len(pkgs)} 个")
idx = list((off / "r-packages").rglob("PACKAGES"))
check(len(idx) == 1, "PACKAGES 索引存在")

mm_rel = off / "minimap2.exe"
mm_repo = REPO / "03_dependence" / "windows-x86_64" / "bin" / "minimap2.exe"
check(mm_rel.is_file(), "minimap2.exe 存在")
if mm_rel.is_file() and mm_repo.is_file():
    same = sha256(mm_rel) == sha256(mm_repo)
    check(same, "与仓库内 minimap2.exe 一致", "" if same else "hash 不同")

print("\n=== 5b) setup 资产里也带 minimap2（不装离线包时的比对程序） ===")
# The assets are git-ignored build products, so only check the one that exists.
import zipfile  # noqa: E402

BUILD = RELEASE / "_build"
setup_zips = sorted(BUILD.glob("nanoamp-*-windows-setup.zip"))
if not setup_zips:
    print("   skip  (尚未运行 release/_build/build_assets.py 生成 setup 资产)")
else:
    setup = setup_zips[-1]
    with zipfile.ZipFile(setup) as zf:
        names = zf.namelist()
        entry = f"nanoamp-windows/bin/minimap2.exe"
        check(entry in names, f"{setup.name} 含 {entry}")
        if entry in names and mm_repo.is_file():
            with zf.open(entry) as fh:
                want = sha256(mm_repo)
                got = hashlib.sha256(fh.read()).hexdigest()
            check(got == want, "  与仓库内 minimap2.exe 内容一致",
                  "" if got == want else f"{got[:16]} vs {want[:16]}")
    deps_entry = "nanoamp-windows/deps/pinned-R4.6.tsv"
    with zipfile.ZipFile(setup) as zf:
        check(deps_entry in zf.namelist(), f"{setup.name} 含 {deps_entry}（联网用的固定版本清单）")

print("\n=== 6) install.exe / uninstall.exe 与源码 ===")
check((RELEASE / "install.exe").is_file(), "install.exe 存在")
check((RELEASE / "uninstall.exe").is_file(), "uninstall.exe 存在")
for f in ("install_nanoamp.py", "uninstall_nanoamp.py", "nanoamp_common.py",
          "install.spec", "uninstall.spec", "build_exe.py", "rthook_paths.py"):
    check((RELEASE / "_installer" / f).is_file(), f"_installer/{f}")

print("\n=== 6b) 两个 exe 的控制台模式 ===")
for exe_name, flag, expect in (
    ("install.exe", "--check", None),
    ("uninstall.exe", "--dry-run", None),
):
    exe = RELEASE / exe_name
    if not exe.is_file():
        continue
    proc = subprocess.run([str(exe), flag], capture_output=True, timeout=300)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    check(bool(out.strip()), f"{exe_name} {flag} 有输出",
          (out.strip().splitlines() or ["(空)"])[0][:70])

# The installer's spec must not bundle the 250 MB payload.
spec = RELEASE / "_installer" / "install.spec"
if spec.is_file():
    text = spec.read_text(encoding="utf-8", errors="replace")
    check("onefile=False" in text, "install.spec 使用 onedir（不打包离线依赖）")
    check("_offline" not in text, "install.spec 未引用 _offline（负载外置）")

print("\n=== 7) release/ 里没有本机绝对路径 ===")
needle = str(REPO).encode()
# Files that legitimately record this machine: the installer's own run log and
# the diagnosis report (both are generated output, git-ignored, and a log that
# did not name the paths it touched would be useless).
RUNTIME_OUTPUT = {"nanoamp_install.log", "nanoamp_diagnose.txt"}
offenders = []
for p in RELEASE.rglob("*"):
    if not p.is_file() or p.suffix in {".exe", ".zip", ".gz", ".zst", ".ab1", ".xlsx", ".bam"}:
        continue
    # __pycache__ is generated by running the scripts here and is git-ignored;
    # .pyc files embed source paths by design.
    if "__pycache__" in p.parts:
        continue
    if p.name in RUNTIME_OUTPUT or p.name.startswith("nanoamp_diagnose"):
        continue
    if p.stat().st_size > 2_000_000:
        continue
    try:
        if needle in p.read_bytes():
            offenders.append(p.relative_to(RELEASE))
    except OSError:
        pass
check(not offenders, "没有指向本机仓库的绝对路径",
      f"{len(offenders)} 个文件：{offenders[:5]}" if offenders else "")

print("\n=== 8) install.exe --check（报告当前状态，未安装也属正常） ===")
exe = RELEASE / "install.exe"
if exe.is_file():
    proc = subprocess.run([str(exe), "--check"], capture_output=True, timeout=300)
    out = (proc.stdout or b"").decode("utf-8", "replace")
    lines = [ln for ln in out.splitlines() if ln.strip()]
    tail = lines[-1].strip() if lines else "(无输出)"
    usable = "状态：可用" in out
    clean = "未安装" in out
    check(bool(lines), "install.exe --check 有输出", tail[:70])
    check(usable or clean, "输出判定明确（可用 / 未安装）", tail[:70])
else:
    check(False, "install.exe 存在（无法检查）")

print("\n" + "=" * 60)
if FAIL:
    print(f"FAILED {len(FAIL)} check(s):")
    for f in FAIL:
        print("  -", f)
    sys.exit(1)
print("ALL DELIVERABLE CHECKS PASSED")
