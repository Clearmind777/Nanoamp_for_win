#!/usr/bin/env python
"""Build the two GitHub Release assets from this repository.

Two assets, both rooted at `nanoamp-windows/`:

    nanoamp-0.1.5-windows-setup.zip          install.exe + uninstall.exe +
                                            README.md + 01_R-package/ +
                                            02_CLI/ + 03_GUI/ + deps/ + bin/
    nanoamp-0.1.0-windows-offline-deps.zip   _offline/  (R installer, 109 R
                                            package binaries, minimap2.exe)

Both archives use the same single root folder, `nanoamp-windows/`, so the user
unpacks them into one directory and double-clicks `install.exe`:

    nanoamp-windows/
      install.exe  uninstall.exe  01_R-package/  02_CLI/  03_GUI/  deps/  bin/
      _offline/            <- from the second asset (optional)

The setup package alone is enough to install: without `_offline/` the installer
reads `deps/pinned-R<tag>.tsv`, picks the fastest mirror and downloads exactly
the versions listed there (plus R itself, if the machine has none). The offline
package just makes that step unnecessary. `bin/minimap2.exe` is the same binary
as `_offline/minimap2.exe`, included in the setup asset so an online-only
install still ends up with a working aligner.

Usage:
    python release/build_assets.py                 # build both zips here
    python release/build_assets.py --verify-only   # check what is present
    python release/build_assets.py --compare-published <setup.zip> <deps.zip>

The zips are ~31 MB and ~248 MB: GitHub refuses files over 100 MiB, so they are
NOT committed (.gitignore). What is committed next to this script is
SHA256SUMS.txt, so a published asset can always be traced back to a revision.
"""

from __future__ import annotations

import argparse
import hashlib
import os
import sys
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = "nanoamp-windows"

SETUP_VERSION = "0.1.5"
SETUP_ZIP = f"nanoamp-{SETUP_VERSION}-windows-setup.zip"
OFFLINE_ZIP = "nanoamp-0.1.0-windows-offline-deps.zip"

# What goes into the setup asset (relative to this directory). Same shape as the
# published v0.1.2 setup asset (README at the root, no installer sources), plus
# `deps/`: the pinned dependency list that lets install.exe install without the
# offline package (it then picks the fastest mirror and downloads those exact
# versions).
SETUP_ITEMS = [
    "install.exe",
    "uninstall.exe",
    "README.md",
    "01_R-package",
    "02_CLI",
    "03_GUI",
    "deps",
]
# Shipped under a different name than in the tree: the aligner is kept once, in
# `_offline/` (shared with the offline asset), but every install needs it, so
# the setup asset carries it as `bin/minimap2.exe` -- the location install.exe
# copies from and the location it installs to.
SETUP_EXTRA = [("_offline/minimap2.exe", "bin/minimap2.exe")]
# What goes into the offline-dependencies asset.
OFFLINE_ITEMS = ["_offline"]
OFFLINE_EXTRA: list[tuple[str, str]] = []

# (asset name, tree items, files renamed on the way in)
ASSETS = [
    (SETUP_ZIP, SETUP_ITEMS, SETUP_EXTRA),
    (OFFLINE_ZIP, OFFLINE_ITEMS, OFFLINE_EXTRA),
]

# Fixed timestamp so the same inputs give the same archive bytes.
ZIP_DATE = (2026, 9, 22, 0, 0, 0)

# PyInstaller/pytest intermediates that must never end up in an asset.
SKIP_DIRS = {"__pycache__", "build", "dist", ".pytest_cache", ".mypy_cache"}


def iter_files(items: list[str], extra: list[tuple[str, str]] = ()):
    """Yield (source path, archive path) for every file under *items*.

    *extra* adds files that are stored under a different name in the archive:
    each entry is (path relative to this directory, archive path relative to the
    asset root).
    """
    for item in items:
        path = HERE / item
        if path.is_dir():
            for dirpath, dirnames, filenames in os.walk(path):
                dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
                for name in sorted(filenames):
                    full = Path(dirpath) / name
                    rel = full.relative_to(HERE).as_posix()
                    yield full, f"{ROOT}/{rel}"
        elif path.is_file():
            yield path, f"{ROOT}/{item}"
        else:
            raise SystemExit(f"missing: {path}")
    for src_rel, arc_rel in extra:
        src = HERE / src_rel
        if not src.is_file():
            raise SystemExit(f"missing: {src}")
        yield src, f"{ROOT}/{arc_rel}"


def make_zip(target: Path, items: list[str], extra=()) -> tuple[int, int]:
    """Write *target*; return (file count, total uncompressed bytes)."""
    files = list(iter_files(items, extra))
    target.unlink(missing_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
        for src, arc in files:
            info = zipfile.ZipInfo(arc, date_time=ZIP_DATE)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            zf.writestr(info, src.read_bytes())
    return len(files), sum(s.stat().st_size for s, _ in files)


def verify_zip(target: Path, items: list[str], extra=()) -> None:
    """Every entry must match its source file byte for byte."""
    with zipfile.ZipFile(target) as zf:
        bad = zf.testzip()
        if bad:
            raise SystemExit(f"{target.name}: corrupt entry {bad}")
        expected = {arc: src for src, arc in iter_files(items, extra)}
        names = set(zf.namelist())
        if names != set(expected):
            missing = sorted(set(expected) - names)[:5]
            extra = sorted(names - set(expected))[:5]
            raise SystemExit(f"{target.name}: entry mismatch missing={missing} extra={extra}")
        for arc, src in expected.items():
            with zf.open(arc) as fh:
                if hashlib.sha256(fh.read()).digest() != hashlib.sha256(src.read_bytes()).digest():
                    raise SystemExit(f"{target.name}: content mismatch for {arc}")
    print(f"   verified {target.name}: {len(expected)} entries match the tree")


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def compare_published(asset: Path, published: Path) -> int:
    """Compare one of our zips with the asset published on GitHub."""
    with zipfile.ZipFile(asset) as a, zipfile.ZipFile(published) as b:
        an = {i.filename: i for i in a.infolist() if not i.is_dir()}
        bn = {i.filename: i for i in b.infolist() if not i.is_dir()}
        only_a = sorted(set(an) - set(bn))
        only_b = sorted(set(bn) - set(an))
        diffs = []
        for name in sorted(set(an) & set(bn)):
            ia, ib = an[name], bn[name]
            if ia.file_size != ib.file_size or ia.CRC != ib.CRC:
                diffs.append((name, ib.file_size, ia.file_size))
        print(f"   {asset.name}: {len(an)} entries, {published.name}: {len(bn)} entries")
        if only_a or only_b:
            print(f"   only in ours  : {only_a[:5]}")
            print(f"   only in theirs: {only_b[:5]}")
        for name, was, now in diffs[:10]:
            print(f"   differs: {name}  published={was} ours={now}")
        same = len(set(an) & set(bn)) - len(diffs)
        print(f"   identical entries: {same}   differing: {len(diffs)}")
        return 0 if not (only_a or only_b or diffs) else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--verify-only", action="store_true")
    ap.add_argument("--compare-published", nargs=2, metavar=("SETUP", "DEPS"))
    args = ap.parse_args()

    if args.compare_published:
        rc = compare_published(HERE / SETUP_ZIP, Path(args.compare_published[0]))
        rc |= compare_published(HERE / OFFLINE_ZIP, Path(args.compare_published[1]))
        return rc

    if not args.verify_only:
        for name, items, extra in ASSETS:
            target = HERE / name
            n, total = make_zip(target, items, extra)
            print(f"built {name}: {n} files, {total / 1e6:.1f} MB uncompressed, "
                  f"{target.stat().st_size / 1e6:.1f} MB packed")

    lines = []
    for name, items, extra in ASSETS:
        target = HERE / name
        if not target.is_file():
            raise SystemExit(f"missing {target}; run without --verify-only first")
        verify_zip(target, items, extra)
        lines.append(f"{sha256(target)}  {name}")
    (HERE / "SHA256SUMS.txt").write_text("\n".join(lines) + "\n", encoding="ascii")
    print("wrote SHA256SUMS.txt")
    for line in lines:
        print("  ", line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
