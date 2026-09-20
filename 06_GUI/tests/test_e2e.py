"""End-to-end check: drive the GUI's runner through a real analysis, then
verify the parsers the window uses to display the results."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from nanoamp_gui.app import NanoampApp, find_repo_root, resource_base  # noqa: E402
from nanoamp_gui.r_runner import NanoampRunner  # noqa: E402

root = find_repo_root(resource_base())
runner = NanoampRunner(root)

sample = root / "01_data" / "ln_test_data" / "TSM20260826" / "E4-3"
reads = sample / "reads.fastq"
reference = sample / "reference.self.fa"
assert reads.is_file(), f"missing {reads}"
assert reference.is_file(), f"missing {reference}"

outdir = root / "04_results" / "gui" / "E4-3"
argv = [
    "call",
    "--reads", str(reads),
    "--reference", str(reference),
    "--outdir", str(outdir),
    "--mode", "A",
    "--top-n", "5",
]
print("command:", " ".join(argv[:1] + argv[1:3]) + " ...")
code, lines = runner.run(argv, stream=lambda s: None)
print("returncode:", code)
for line in lines[-6:]:
    print("   ", line)
assert code == 0, "analysis failed"

print("\n--- files produced ---")
for p in sorted(outdir.iterdir()):
    if p.is_file():
        print(f"   {p.name:<28} {p.stat().st_size:>9,} bytes")

print("\n--- haplotypes.tsv via the GUI parser ---")
fields, rows = NanoampApp._read_tsv(outdir / "haplotypes.tsv")
print("fields:", fields)
print(f"rows  : {len(rows)}")
for r in rows:
    prop = float(r["proportion"])
    print(f"   {r['rank']:>2}  {r['haplotype_id']:<3} {r['count']:>4} reads  "
          f"{prop:6.1%}  ref={r['is_reference']:<5}  {r['variants']}")

print("\n--- qc.tsv via the GUI parser ---")
_qf, qc = NanoampApp._read_tsv(outdir / "qc.tsv")
for r in qc[:8]:
    print(f"   {r['metric']:<24} {r['value']}")

print("\n--- haplotypes.fasta via the GUI parser ---")
parsed = NanoampApp._load_fasta(outdir / "haplotypes.fasta")
print(f"sequences: {len(parsed)}")
for k, v in list(parsed.items())[:3]:
    print(f"   {k:<4} {len(v):>4} bp  {v[:60]}...")

# haplotypes.fasta only carries the top-n sequences, so the GUI must have a
# sequence for every row it displays *within* top-n, and must handle the rest
# without rendering an empty box.
top_n = 5
exported = [r["haplotype_id"] for r in rows[:top_n]]
missing = [h for h in exported if h not in parsed]
assert not missing, f"no sequence for top-n haplotype ids: {missing}"
print(f"\ntop-{top_n} haplotype ids all resolve to a sequence: OK")

below = [r["haplotype_id"] for r in rows[top_n:]]
print(f"rows below top-{top_n} with no exported sequence (handled with a "
      f"message): {below if below else 'none'}")

print("\nEND-TO-END OK")
