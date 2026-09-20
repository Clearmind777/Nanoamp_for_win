"""Headless checks for the GUI's non-window logic."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))  # 02_code/PythonGUI, which contains nanoamp_gui/

from nanoamp_gui.app import find_repo_root, resource_base, NanoampApp  # noqa: E402
from nanoamp_gui.r_runner import NanoampRunner  # noqa: E402

print("resource_base() :", resource_base())
root = find_repo_root(resource_base())
print("find_repo_root():", root)
assert (root / "03_dependence").is_dir(), "repo root not found"

runner = NanoampRunner(root)
print("rscript         :", runner.rscript)
wrapper = runner.write_wrapper()
print("wrapper written :", wrapper, f"({wrapper.stat().st_size} bytes)")

print("\n--- doctor ---")
code, lines = runner.run(["doctor"])
print("returncode:", code)
for line in lines[:14]:
    print("   ", line)

print("\n--- FASTA parser ---")
outdir = root / "tmp/test_results" / "gui"
fa = outdir / "haplotypes.fasta"
if fa.is_file():
    parsed = NanoampApp._load_fasta(fa)
    print(f"parsed {len(parsed)} sequences from {fa.name}")
    for k, v in list(parsed.items())[:3]:
        print(f"   {k}: {len(v)} bp  {v[:50]}...")
else:
    print("(no haplotypes.fasta yet; run the CLI first)")

print("\n--- TSV parser ---")
tsv = outdir / "haplotypes.tsv"
if tsv.is_file():
    fields, rows = NanoampApp._read_tsv(tsv)
    print("fields:", fields)
    print("rows  :", len(rows))
    print("first :", rows[0] if rows else None)
else:
    print("(no haplotypes.tsv yet)")

print("\nHEADLESS CHECKS OK")
