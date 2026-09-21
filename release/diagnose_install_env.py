"""Collect what is needed to diagnose an installer that appears to do nothing.

Run this ON THE MACHINE THAT FAILS, from the folder holding install.exe:

    install.exe --check                  (quick, opens no window)
    python diagnose_install_env.py       (if Python is available)
    diagnose_install_env.bat             (same thing without Python)

It prints, and writes to nanoamp_diagnose.txt:

  * Windows version / build, architecture
  * free RAM and free disk space
  * whether the bundle is complete (_offline, R installer, R packages)
  * whether a previous attempt left a partial install behind
  * whether an R is already present
  * the tail of nanoamp_install.log, if the installer wrote one

Nothing is installed, changed or deleted by this script.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def find_bundle_root() -> Path:
    """The folder holding install.exe.

    Normally the user runs this from the extracted folder, so the working
    directory is right. Fall back to walking up from this script, because the
    script lives in _installer/ inside the release tree.
    """
    for start in (Path.cwd(), HERE):
        p = start.resolve()
        for _ in range(5):
            if (p / "install.exe").is_file() or (p / "_offline").is_dir():
                return p
            if p.parent == p:
                break
            p = p.parent
    return Path.cwd()


ROOT = find_bundle_root()
OUT = ROOT / "nanoamp_diagnose.txt"
LINES: list[str] = []


def say(text: str = "") -> None:
    print(text)
    LINES.append(text)


def section(title: str) -> None:
    say()
    say("=" * 66)
    say(title)
    say("=" * 66)


def run(cmd: list[str]) -> str:
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        return ((p.stdout or "") + (p.stderr or "")).strip()
    except (OSError, subprocess.SubprocessError) as exc:
        return f"<failed: {exc}>"


def main() -> int:
    section("1. this machine")
    say(f"Windows      : {platform.platform()}")
    say(f"version      : {platform.version()}")
    say(f"architecture : {platform.machine()} ({platform.architecture()[0]})")
    say(f"processor    : {os.environ.get('PROCESSOR_IDENTIFIER', '?')}")
    say(f"python       : {platform.python_version() if sys.version_info else 'n/a'}")

    section("2. memory and disk")
    total = os.environ.get("NUMBER_OF_PROCESSORS", "?")
    say(f"logical CPUs : {total}")
    say(run(["wmic", "OS", "get", "FreePhysicalMemory,TotalVisibleMemorySize", "/value"]))
    install_home = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "nanoamp"
    anchor = install_home.anchor or "C:\\"
    try:
        usage = shutil.disk_usage(anchor)
        say(f"disk {anchor} free : {usage.free / 1e9:.1f} GB "
            f"(need about 1.5 GB; the installer copies ~545 MB)")
    except OSError as exc:
        say(f"disk {anchor} : <cannot read: {exc}>")

    section("3. is the bundle complete?")
    offline = ROOT / "_offline"
    say(f"install.exe           : {(ROOT / 'install.exe').is_file()}")
    say(f"_offline/ exists      : {offline.is_dir()}")
    rdir = offline / "r"
    installers = sorted(rdir.glob("R-*-win.exe")) if rdir.is_dir() else []
    say(f"_offline/r/*.exe      : {[p.name for p in installers] or 'MISSING'}")
    contrib = offline / "r-packages" / "bin" / "windows" / "contrib"
    tags = sorted(d.name for d in contrib.iterdir() if d.is_dir()) if contrib.is_dir() else []
    say(f"R package versions    : {tags or 'MISSING'}")
    for tag in tags:
        zips = list((contrib / tag).glob("*.zip"))
        say(f"  R {tag}: {len(zips)} .zip files in {contrib / tag}")
    tarballs = sorted((ROOT / "01_R-package").glob("nanoamp_*.tar.gz"))
    say(f"01_R-package tarball  : {[p.name for p in tarballs] or 'MISSING'}")
    say(f"03_GUI/nanoamp.exe    : {(ROOT / '03_GUI' / 'nanoamp.exe').is_file()}")

    section("4. previous attempts / existing install")
    say(f"install dir {install_home} : {install_home.is_dir()}")
    cfg = install_home / "config.ini"
    say(f"  config.ini present  : {cfg.is_file()}")
    if cfg.is_file():
        for line in cfg.read_text(encoding="utf-8", errors="replace").splitlines():
            say(f"    {line}")
    for p in (install_home / "R" / "R-runtime" / "bin" / "Rscript.exe",
              install_home / "app" / "nanoamp.exe",
              install_home / "bin" / "minimap2.exe"):
        say(f"  {p.relative_to(install_home)} : {p.is_file()}")
    manual = Path("D:/nanoamp")
    say(f"D:\\nanoamp exists      : {manual.is_dir()}")
    marker = Path(os.environ.get("LOCALAPPDATA", "")) / "nanoamp.path"
    if marker.is_file():
        say(f"pointer file          : {marker.read_text(encoding='utf-8', errors='replace').strip()}")

    section("5. is R already installed?")
    for cand in (Path("C:/Program Files/R"), Path("C:/Program Files (x86)/R"),
                 Path("D:/tools/R")):
        if cand.is_dir():
            say(f"{cand}: {[d.name for d in cand.glob('R-*')]}")
    which = shutil.which("Rscript")
    say(f"Rscript on PATH       : {which or 'no'}")
    say(f"NANOAMP_RSCRIPT       : {os.environ.get('NANOAMP_RSCRIPT', '(unset)')}")
    renv = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents" / ".Renviron"
    say(f"Documents\\.Renviron   : {renv.is_file()}")
    if renv.is_file():
        for line in renv.read_text(encoding="utf-8", errors="replace").splitlines():
            say(f"    {line}")

    section("6. leftover installer processes")
    say(run(["tasklist", "/FI", "IMAGENAME eq install.exe", "/FO", "CSV", "/NH"]))
    say(run(["tasklist", "/FI", "IMAGENAME eq R-4.6.1-win.exe", "/FO", "CSV", "/NH"]))

    section("7. installer log")
    log = ROOT / "nanoamp_install.log"
    if not log.is_file():
        alt = Path(os.environ.get("LOCALAPPDATA", "")) / "nanoamp_install.log"
        log = alt if alt.is_file() else log
    say(f"log path : {log}")
    if log.is_file():
        say(f"size     : {log.stat().st_size} bytes")
        lines = log.read_text(encoding="utf-8", errors="replace").splitlines()
        say("--- last 40 lines ---")
        for line in lines[-40:]:
            say(line)
    else:
        say("NO LOG FILE - the installer never reached its first logged step,")
        say("which means the click did not get as far as starting the work.")

    section("8. windows application error log (last 10 entries)")
    say(run(["wevtutil", "qe", "Application", "/c:10", "/rd:true",
             "/q:*[System[Level=2]]", "/f:text"]))

    OUT.write_text("\n".join(LINES) + "\n", encoding="utf-8", errors="replace")
    print()
    print(f"written to {OUT}")
    print("Please send that file back.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
