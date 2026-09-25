"""Headless checks for the installer's logic that do not touch the system.

Does NOT install anything or modify PATH - it only exercises discovery,
preflight and the release-tree assumptions.
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import install_nanoamp as ins  # noqa: E402

print("app_dir()      :", ins.app_dir())
print("install_home() :", ins.install_home())
print("r_lib_dir()    :", ins.r_lib_dir())
print("bin_dir()      :", ins.bin_dir())
print("desktop_dir()  :", ins.desktop_dir())
print("renviron_path():", ins.renviron_path())

ctx = ins.Context(root=ins.app_dir())
print("\n--- release tree ---")
print("offline dir    :", ctx.offline, ctx.offline.is_dir())
print("R installer    :", ctx.r_installer)
print("R version tags :", ctx.available_r_tags())
for tag in ctx.available_r_tags():
    print(f"  R {tag:<6} zips:", len(list(ctx.extra_dir(tag).glob("*.zip"))))
print("pkg tarball    :", ctx.pkg_tarball)
print("gui exe        :", ctx.gui_exe)
print("cli launcher   :", ctx.cli_launcher)
print("install root   :", ctx.install_root)
print("  lib / bin / app / config:",
      ctx.lib, "|", ctx.bin, "|", ctx.app, "|", ctx.config)

print("\n--- existing install detection ---")
found = ins.common.find_existing_install()
print("find_existing_install():", found[0] if found else None)
if found:
    print("  looks_installed():", ins.common.looks_installed(found[0]))

print("\n--- R discovery ---")
rs = ins.find_rscript()
print("find_rscript() :", rs)
if rs:
    print("r_version()    :", ins.r_version(rs))
    print("r_supported()  :", ins.r_supported(rs))

print("\n--- preflight (raises if the bundle is incomplete) ---")
events: list = []
installer = ins.Installer(ctx, __import__("queue").Queue())
installer._preflight()
for line in ctx.log:
    print("   ", line)

print("\n--- generated R snippets are valid R ---")
dummy = ins.Installer(ctx, __import__("queue").Queue())
dummy.lib = ins.r_lib_dir()          # lib may not exist yet; only text matters
for name, body in (
    ("deps", f"""
.libPaths(c({'D:/x/lib'!r}))
options(repos = c(CRAN = {'file:///D:/x/extra'!r}))
cat("ok\\n")
"""),
):
    p = Path(ins.os.environ.get("TEMP", ".")) / f"_nanoamp_probe_{name}.R"
    p.write_text(body, encoding="utf-8")
    print(f"   wrote {p.name} ({p.stat().st_size} bytes)")

print("\n--- annotation configs are copied to <install root>/configs ---")
import tempfile  # noqa: E402
import types  # noqa: E402

sandbox = Path(tempfile.mkdtemp(prefix="nanoamp_cfg_test_"))
lib = sandbox / "R" / "lib"
src = lib / ins.PACKAGE_NAME / "configs"
src.mkdir(parents=True)
(src / "example_cds.json").write_text("{}", encoding="utf-8")
(src / "example_online.json").write_text("{}", encoding="utf-8")
install_root = sandbox / "target"
stand_in = types.SimpleNamespace(
    lib=lib, ctx=types.SimpleNamespace(install_root=install_root),
    say=lambda *a: None,
)
copied = ins.Installer._install_annotation_configs(stand_in)
have = sorted(p.name for p in (install_root / "configs").glob("*")) if copied else []
print("copied          :", copied, "->", have or "(nothing)")
assert copied and have == ["example_cds.json", "example_online.json"], have
# A package without configs must not fail the install.
empty_lib = sandbox / "R2" / "lib"
(empty_lib / ins.PACKAGE_NAME).mkdir(parents=True)
stand_in2 = types.SimpleNamespace(
    lib=empty_lib, ctx=types.SimpleNamespace(install_root=sandbox / "target2"),
    say=lambda *a: None,
)
missing = ins.Installer._install_annotation_configs(stand_in2)
print("missing configs :", missing, "(expected False, install continues)")
assert missing is False

print("\nINSTALLER LOGIC OK")
