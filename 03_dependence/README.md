# 03_dependence

External tools bundled with the **Windows build** of nanoamp.

This repository is the Windows variant. The Linux variant lives in the sister
repository `a_09_18_26_mapping_programs_dev_for_linux`.

## Layout

```text
03_dependence/
|-- README.md
|-- README-CN.md
|-- manifest.tsv
|-- licenses/
|   `-- minimap2-LICENSE.txt
|-- windows-x86_64/
|   |-- README.md
|   |-- install_msys2_toolchain.ps1   # reproducible toolchain installer
|   |-- build_minimap2.sh             # builds minimap2.exe from source
|   `-- bin/minimap2.exe              # built in-repo, statically linked
|-- windows-arm64/README.md
|-- offline-bundle/                   # air-gapped provisioning (R + packages)
|   |-- README.md
|   |-- fetch_offline_bundle.R
|   `-- install_offline.ps1
|-- stress/                           # environment stress matrix
|   |-- README.md
|   |-- run_stress_tests.py           # groups A-D, driven through the real CLI
|   `-- data/znf8_exon_amplicon.fa    # real GRCh38 slice used by the online tests
|-- baselines/
|   `-- functional/                   # committed functional-regression baseline
|       |-- README.md
|       |-- comparison.tsv
|       |-- summary_by_mode.tsv
|       `-- run_index.tsv
`-- r-environment/                    # R setup and test runners for Windows
    |-- README.md
    |-- setup_r_environment.R
    |-- run_tests.R
    |-- run_functional_regression.R
    `-- check_functional_baseline.R   # compares a run with baselines/functional/
```

## How nanoamp finds external tools

Resolution order:

1. environment variable `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`;
2. `03_dependence/<os>-<arch>/bin/<tool>.exe`;
3. `PATH`.

`NANOAMP_DEPENDENCE_DIR` can point to a different `03_dependence` location
(useful after installing the R package).

`nanoamp doctor` prints the detected platform, the dependence directory, and
the resolved path and version of each tool.

## Windows support matrix

| Platform | minimap2 | samtools | Notes |
|---|---|---|---|
| windows-x86_64 | bundled 2.31 (built in-repo) | not bundled | statically linked, runs without MSYS2/Cygwin/conda/WSL; samtools unnecessary because `Rsamtools::asBam()` is the default SAM -> BAM path |
| windows-arm64 | no binary | not bundled | use the R-native backend (`aligner = "r"`), or run the x86_64 build under emulation |

Upstream facts:

- minimap2 publishes a Linux x86_64 binary; no *official* Windows binary is
  published, but the source builds natively on Windows with the MSYS2 MINGW-w64
  toolchain. `windows-x86_64/bin/minimap2.exe` was produced this way.
- samtools publishes only source and is not required by this project:
  `Rsamtools::asBam()` converts minimap2 SAM to BAM by default. The samtools
  path is used only when `use_samtools = TRUE` is set explicitly, which requires
  building samtools separately (htslib documents MSYS2/MINGW64 as the
  recommended Windows build environment).
- conda and WSL are not used in this project.

## R-native fallback

`run_haplotype_analysis(..., aligner = "r")` uses Biostrings/pwalign pairwise
alignment and requires no external binary. It is slower than minimap2 and is
intended for small and medium amplicons, and for platforms where no minimap2
build exists (Windows on ARM).

The coverage and identity this backend reports come from the segment of the
reference the read actually aligned to. (Earlier versions claimed every read
spanned the whole reference, so a half-length read passed
`--min-ref-coverage 0.99` and was counted as the reference haplotype; the default
`minimap2` backend was always correct.)

Mode C (`mode = "C"`) also requires no external tool.

## R package dependencies

The R package reads FASTQ itself (`R/io.R`: gzip detected by extension or magic
bytes, malformed records rejected), so **ShortRead is not required** by the
package, its `DESCRIPTION`, the CLI or the GUI. The remaining imports are
`Biostrings`, `IRanges`, `Matrix`, `Rsamtools`, `data.table`, `jsonlite`,
`methods`, `optparse`, `readxl`, `stats` and `utils`; `DECIPHER` (Mode B
clustering) and `pwalign` (the `aligner = "r"` backend on Bioconductor >= 3.19)
are optional, and `shiny`/`DT` are only needed for the Shiny GUI.

The Windows R environment script (`r-environment/setup_r_environment.R`) installs
exactly that set and deliberately not ShortRead, because ShortRead imports
`pwalign` unconditionally and would turn an optional provider into a hard
requirement of every installation. The installer's pinned manifest
(`release/deps/pinned-R4.6.tsv`) is a **deliberate superset**: it is frozen
together with the offline asset, so it may still contain ShortRead, which changes
nothing about what the package needs.

The two example annotation configs (`example_cds.json`, `example_online.json`)
travel inside the R package (`nanoamp/inst/configs/`, printed by `nanoamp doctor`
under `configs`) and are used with `--annotate-config`; `install.exe` also copies
them to `<install root>\configs\`.

## Environment stress matrix

`stress/run_stress_tests.py` exercises the automatable cases of the plan's
environment matrix through the real CLI (same runner the GUI uses) and records
the rest as `SKIP` with the manual procedure:

```powershell
# everything (group A needs internet)
python 03_dependence/stress/run_stress_tests.py --group A,B,C,D

# offline groups only
python 03_dependence/stress/run_stress_tests.py --group B,C,D
```

Groups: **A** network/proxy/cache, **B** input degeneracy and annotation shape,
**C** environment (paths with spaces and Chinese characters, over-long paths,
cache-directory resolution, missing curl, no PATH help), **D** cancellation and
concurrency. Results land in `tmp/test_results/stress/stress_results.tsv`; the
last full run was **47 PASS / 0 FAIL / 2 SKIP** (the skips are the manual
disk-full and ARM64 cases). `make stress-test` runs all four groups, and
`stress/README.md` maps every case to the plan's numbering.

## Functional-regression baseline

`r-environment/run_functional_regression.R` runs Modes A/B/C over every sample in
`01_data/` (168 runs). `r-environment/check_functional_baseline.R` compares such a
run row by row against the committed snapshot in `baselines/functional/`
(`status`, variant counts, `top1_variants`, read counts, `mapping_rate`,
`mean_identity`, `top1_proportion`; a run that used to be `ok` and no longer is
fails immediately).

```bash
make functional-test       # run the regression, then compare with the baseline
make functional-baseline   # re-run and refresh the baseline (review the diff!)
```

Mode B calls `DECIPHER::Clusterize`, which is stochastic upstream (the same input
under a different RNG state returned 29 vs 30 clusters at one cutoff), so the
package seeds that call and records `clustering_seed` (default 42) in `qc.tsv`
while leaving the caller's RNG stream untouched. Without that, every Mode B row
would differ between runs and the baseline could only have been advisory.

## Rebuilding minimap2 on Windows

```powershell
# 1. portable MSYS2 + MINGW-w64 toolchain (~1.5 GB, outside the repo)
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

# 2. build and install minimap2.exe
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

The toolchain itself is not committed (too large); the repository commits the
two scripts above plus the resulting binary and its provenance.
See `windows-x86_64/README.md` for pinned versions, flags and hashes.

## Offline / air-gapped installation

Every upstream installer can be pre-positioned as a pinned, integrity-checked
bundle, so that a machine without network access can be provisioned:

```powershell
# with a network
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R
# without a network
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

The bundle written to the git-ignored `dist/` contains the R installer, the full
R package closure, the MSYS2 toolchain and the minimap2 source. The published
offline asset `release/_build/nanoamp-0.1.0-windows-offline-deps.zip` (~248 MB)
contains the R 4.6.1 installer, 109 R package binaries and `minimap2.exe`. Why
the binaries are not committed, and the USB / release-asset alternatives, are
documented in `offline-bundle/README.md`.

## Licenses

- minimap2: MIT;
- samtools: MIT/Expat (not bundled here).

License text for the bundled minimap2 binary is in `licenses/`.
