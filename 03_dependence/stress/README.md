# Environment stress tests (plan section 6)

`run_stress_tests.py` runs the *real* CLI (through the same runner the GUI uses)
for the cases from the plan's section 6 matrix that can be automated on one
machine, and reports the rest as `SKIP` with the manual procedure. Nothing here
is a mock: every case checks exit codes, `run_manifest.json`, `qc.tsv` and the
result tables that a user would get.

```powershell
# everything (group A needs internet)
python 03_dependence/stress/run_stress_tests.py --group A,B,C,D

# offline only
python 03_dependence/stress/run_stress_tests.py --group B,C,D

# keep the scratch directory even when everything passes
python 03_dependence/stress/run_stress_tests.py --group A --keep
```

Results are written to `tmp/test_results/stress/stress_results.tsv`
(`group`, `case`, `status`, `detail`); the process exits 1 if any case fails.
The last full run on this machine: **47 PASS / 0 FAIL / 2 SKIP** (the two SKIPs are
the manual cases below).

## What is covered

| Plan case | Status | Where |
|---|---|---|
| A1 normal online run | automated | group A: genome route on a real GRCh38 amplicon, release + consequence checks |
| A2 through an HTTP proxy | automated (skips if no proxy is up) | group A; set `NANOAMP_STRESS_PROXY` to override `http://127.0.0.1:7890` |
| A3 throttling / intermittent failure | partly | group A (retry + backoff visible in the log); the backoff itself is unit-tested in R |
| A4 completely offline | automated | group A: proxy variables pointed at a dead port |
| A5 DNS/host unreachable | automated | group A: the A4 error text must be actionable |
| A6 cache hit | automated | group A: warm cache replayed with no network, cache size unchanged, same consequences |
| A7 corrupted cache | automated | group A: three entries corrupted, run must refetch or fail loudly |
| A8 download interrupted | partly | A7 + A4 (a partially cached run must not produce a half annotation) |
| A9 `--no-cache` | automated | group A: bypasses the cache and never deletes it |
| B1 annotation schema | automated | group B: offline cds route, `annotation.tsv`, `variants_annotation.tsv` |
| B2 `--transcript all` | automated | group A: 5 transcripts annotated, 1 skipped **with the reason recorded** |
| B3 large annotation matrix | automated | group B: 41 haplotypes, timed |
| B4 long CDS / proteins | automated | group B: `--annotation-proteins` |
| B5 degenerate CDS | automated | group B: non-multiple-of-3 is skipped, recorded, exit 0; `--strict` makes it exit 1 |
| B6 empty / malformed FASTQ | automated | group B: exit 1, `error_class = input`, readable message |
| C1 spaces + Chinese paths | automated | group C |
| C2 path > 260 characters | automated | group C: must fail with an error naming the directory |
| C3 `%TEMP%` unwritable / cache fallback | automated | group C: cache resolution order asserted in a child R process |
| C4 disk full | manual | needs a full volume (see below) |
| C5 no `curl` | partly automated | `Sys.which` finds the system copy regardless of PATH, so the R client is exercised directly; the offline route is also run |
| C6 no `pwalign` / no `DECIPHER` | partly automated | group C: provider reported, offline route without external tools; `R CMD check` covers the Suggests semantics |
| C7 two R versions | automated | group C runs `release/_installer/test_r_version_choice.py` |
| C8 no PATH help | automated | group C: PATH without the install directory |
| C9 Windows ARM64 | manual | needs ARM64 hardware (see below) |
| C10 locked files / antivirus | automated | group C runs `test_copy_retry.py` and `test_locked_file_retry.py` |
| D1 cancel during a run | automated | group D: kill mid-run, partial output kept, no "done" status |
| D2 cancel during annotation | automated | group D: kill as soon as `haplotypes.tsv` exists |
| D3 two concurrent runs | automated | group A: two live online runs sharing one cache, then an offline replay |
| D4 install while running | manual | installer retry logic is covered by `make release-test` |
| D5 network loss mid-annotation | partly | A4/A7 |
| E1/E2/E3/E5/E7 GUI layout & interaction | partly automated | `make gui-test` (`test_annotation_gui.py`, `test_window_fit.py`); high-DPI needs a real session |
| E4 malformed `annotation.tsv` | automated | `test_annotation_gui.py` §6e |
| E6 long/Chinese log text | automated | `test_annotation_gui.py` §6f |
| F1-F7 installer routes | automated elsewhere | `make release-test` + the offline/online install verification |

## Manual cases

* **C4 disk full** - put the output directory on a volume with no free space and
  run any analysis; the message must name the disk and the run must not produce a
  half-written result table.
* **C9 Windows ARM64** - run with `--aligner r` (there is no ARM64 minimap2 in
  this repository) and confirm annotation is unaffected.
* **E2 high DPI (125 % / 150 %)** - start the GUI on such a display and check
  that nothing overlaps; screenshot into the work report.

## Fixtures

`data/znf8_exon_amplicon.fa` is a real 400 bp slice of GRCh38
(`19:58,294,617-58,295,016`, plus strand) taken from a coding exon of the
canonical ZNF8 transcript `ENST00000621650`, so the online route can locate it
through the built-in gene panel without scanning a chromosome. Provenance (gene,
transcript, exon, Ensembl coordinates, retrieval date) is in
`data/znf8_exon_amplicon.json`; `../baselines/functional/README.md` describes the
functional baseline.
