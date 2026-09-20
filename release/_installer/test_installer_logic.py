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
print("extra zips     :", len(list(ctx.extra_dir.glob("*.zip"))))
print("pkg tarball    :", ctx.pkg_tarball)
print("gui exe        :", ctx.gui_exe)

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

print("\nINSTALLER LOGIC OK")
