"""Check the pinned dependency set and the decisions that use it.

The offline package is optional now: without it the installer must still install
exactly the same dependency versions, from a mirror it first measures. That rests
on `deps/pinned-R<tag>.tsv`, so this test fences in:

  * the manifest itself (shape, hashes, dependency graph, install order),
  * that it agrees with the offline bundle when the bundle is present,
  * the mirror ordering rule and the download URLs,
  * that a bundle-less tree still yields the right R tag (so R 4.5 is rejected
    and R 4.6 accepted exactly as with the bundle).

No network access is needed.

    python release/_installer/test_pinned_deps.py
"""

from __future__ import annotations

import hashlib
import re
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
RELEASE = HERE.parent
REPO = RELEASE.parent
sys.path.insert(0, str(HERE))

import install_nanoamp as ins  # noqa: E402

failures: list[str] = []


def check(ok: bool, what: str) -> None:
    print(("   OK   " if ok else "   FAIL ") + what)
    if not ok:
        failures.append(what)


manifest = RELEASE / "deps" / "pinned-R4.6.tsv"
print(f"manifest: {manifest.relative_to(REPO)}")
check(manifest.is_file(), "the pinned manifest ships with the setup package")
pinned = ins.load_pinned_set(manifest)
check(pinned is not None, "it parses")
assert pinned is not None

print("\n=== the manifest ===")
check(pinned.r_tag == "4.6", f"declares the R tag the packages were built for ({pinned.r_tag})")
check(bool(re.fullmatch(r"\d+\.\d+", pinned.bioconductor)),
      f"declares a Bioconductor version ({pinned.bioconductor})")
check(len(pinned.packages) >= 100, f"covers the whole closure ({len(pinned.packages)} packages)")
check(all(re.fullmatch(r"[0-9a-f]{64}", p.sha256) for p in pinned.packages.values()),
      "every package has a sha256")
check(all(re.fullmatch(r"[0-9a-f]{32}", p.md5) for p in pinned.packages.values()),
      "every package has an md5")
check(re.fullmatch(r"[0-9a-f]{64}", pinned.r_installer_sha256) is not None,
      "the R runtime is pinned by sha256 too")

print("\n=== install order ===")
order = pinned.order()
check(len(order) == len(pinned.packages), "every package appears exactly once")
pos = {pkg.name: i for i, pkg in enumerate(order)}
violations = [(pkg.name, dep) for pkg in order for dep in pkg.deps
              if dep in pos and pos[dep] > pos[pkg.name]]
check(not violations, f"dependencies come first (0 violations, {len(violations)} found)")
for pkg in ("Biostrings", "Rsamtools", "ShortRead", "data.table", "DECIPHER"):
    check(pkg in pinned.packages, f"{pkg} is pinned")

print("\n=== mirror handling ===")
check(ins.rank_mirrors([("slow", 1.0), ("down", None), ("fast", 100.0), ("mid", 10.0)])
      == ["fast", "mid", "slow", "down"],
      "rank_mirrors puts the fastest first and unreachable ones last")
check(all(m[1].startswith("https://") and m[1].endswith("/") for m in ins.MIRRORS),
      f"every mirror has an https base ({len(ins.MIRRORS)} mirrors)")
check(sum(1 for m in ins.MIRRORS if m[1].endswith("/CRAN/")) >= 5,
      "the Chinese mirrors all use the /CRAN/ layout")
check(sum(1 for m in ins.MIRRORS if m[2]) >= 4, "most mirrors also carry Bioconductor")

pkg = pinned.packages["abind"]
tuna = ins.MIRRORS[0]
urls = ins.Installer._package_urls(tuna, pinned, pkg)
check(urls[0].endswith(f"/CRAN/bin/windows/contrib/{pinned.r_tag}/{pkg.filename}"),
      "CRAN URL is <mirror>/CRAN/bin/windows/contrib/<tag>/<pkg>_<ver>.zip")
check(urls[1].endswith(f"/bioconductor/packages/{pinned.bioconductor}/bioc/bin/windows/"
                       f"contrib/{pinned.r_tag}/{pkg.filename}"),
      "Bioconductor URL is <mirror>/packages/<bioc>/bioc/bin/windows/contrib/<tag>/...")
official = ins.MIRRORS[-1]
check(ins.Installer._r_installer_url(official, pinned)
      == f"https://cloud.r-project.org/bin/windows/base/{pinned.r_installer_name}",
      "the R runtime is taken from <mirror>/bin/windows/base/")

print("\n=== a tree with no _offline/ still knows which R it needs ===")
tmp = Path(tempfile.mkdtemp(prefix="nanoamp-pinned-"))
try:
    (tmp / "deps").mkdir()
    shutil.copy(manifest, tmp / "deps" / manifest.name)
    ctx = ins.Context(root=tmp, install_root=tmp / "out")
    check(ctx.pinned is not None, "the context finds deps/pinned-R*.tsv")
    check(ctx.available_r_tags() == [pinned.r_tag],
          f"available R tags come from the manifest ({ctx.available_r_tags()})")
    check(ins.r_choice(ctx.available_r_tags(), (4, 5)) == "bundled",
          "R 4.5 is still rejected without the offline package")
    check(ins.r_choice(ctx.available_r_tags(), (4, 6)) == "system",
          "R 4.6 is still accepted without the offline package")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

print("\n=== a package zip is identified by name+version, not by bytes ===")
identity_probe = None
for candidate in ("generics", "abind", "praise"):
    path = RELEASE / "_offline" / "r-packages" / "bin" / "windows" / "contrib" / pinned.r_tag / \
        pinned.packages[candidate].filename
    if path.is_file():
        identity_probe = path
        break
if identity_probe is not None:
    ident = ins.zip_package_identity(identity_probe)
    want = (identity_probe.name[:-4].rsplit("_", 1)[0],
            identity_probe.name[:-4].rsplit("_", 1)[1])
    check(ident == want, f"reads Package/Version out of the zip ({ident})")
else:
    print("   skip  (no bundle to read a real package from)")
check(ins.zip_package_identity(Path(__file__)) is None,
      "returns None for something that is not a package zip")

print("\n=== the aligner is found with or without _offline/ ===")
tmp = Path(tempfile.mkdtemp(prefix="nanoamp-aligner-"))
try:
    (tmp / "deps").mkdir()
    shutil.copy(manifest, tmp / "deps" / manifest.name)
    bare = ins.Context(root=tmp, install_root=tmp / "out")
    check(bare.minimap2_exe is None,
          "a setup tree with no bin/ and no _offline/ reports no aligner "
          "(preflight then refuses instead of installing a broken copy)")

    (tmp / "bin").mkdir()
    shutil.copy(RELEASE / "_offline" / "minimap2.exe", tmp / "bin" / "minimap2.exe")
    online = ins.Context(root=tmp, install_root=tmp / "out")
    check(online.minimap2_exe == tmp / "bin" / "minimap2.exe",
          "bin/minimap2.exe (setup asset) is used for an online install")

    (tmp / "_offline").mkdir()
    shutil.copy(RELEASE / "_offline" / "minimap2.exe", tmp / "_offline" / "minimap2.exe")
    offline = ins.Context(root=tmp, install_root=tmp / "out")
    check(offline.minimap2_exe == tmp / "_offline" / "minimap2.exe",
          "_offline/minimap2.exe wins when the offline package is unpacked too")
finally:
    shutil.rmtree(tmp, ignore_errors=True)
check(not (RELEASE / "bin").exists(),
      "the tree keeps only one copy of the aligner (build_assets.py renames "
      "_offline/minimap2.exe to bin/minimap2.exe inside the asset)")
sys.path.insert(0, str(RELEASE / "_build"))
import build_assets as ba  # noqa: E402

check(ba.TREE == RELEASE and ba.OUT == RELEASE / "_build",
      "the build script packs release/ and writes into release/_build/")
check(("_offline/minimap2.exe", "bin/minimap2.exe") in ba.SETUP_EXTRA,
      "build_assets.py does ship it as bin/minimap2.exe in the setup asset")

check(ins.BIN_DIR == "bin", "the installer looks for that directory by name")

print("\n=== the manifest agrees with the offline bundle (when present) ===")
bundle = RELEASE / "_offline" / "r-packages" / "bin" / "windows" / "contrib" / pinned.r_tag
if bundle.is_dir():
    missing, wrong = [], []
    for p in pinned.packages.values():
        path = bundle / p.filename
        if not path.is_file():
            missing.append(p.name)
            continue
        if path.stat().st_size != p.size:
            wrong.append(p.name)
            continue
        h = hashlib.sha256(path.read_bytes()).hexdigest()
        if h != p.sha256:
            wrong.append(p.name)
    check(not missing, f"every pinned file exists in the bundle ({len(pinned.packages)} files)")
    check(not wrong, f"every bundled file matches the pinned sha256 ({wrong[:3]})")
else:
    print("   skip  (no _offline bundle in this checkout)")

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  pinned dependency set: versions, hashes, install order and mirror rules")
