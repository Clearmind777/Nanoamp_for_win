# nanoamp — Windows

`nanoamp` analyzes Oxford Nanopore reads from PCR amplicons. Given a FASTQ file
and a target sequence, it corrects sequencing errors, reconstructs haplotypes,
and reports the most abundant sequences with counts and proportions.

This is the **Windows variant** of the project. It owns all Windows-specific
material: the native `minimap2.exe`, the MSYS2/MINGW-w64 build recipe, the
Windows R environment helpers and the air-gapped installer bundle.

The Linux variant lives in the sister repository
`a_09_18_26_mapping_programs_dev_for_linux`.

Neither variant uses conda, and neither uses WSL.

## Repository layout

```text
00_materials/     project brief, development plan and work reports
01_data/          raw test data and the normalized link layer
02_code/          source code
  r/              nanoamp R package
  cli/            standalone R CLI entry points and launchers
  gui/            standalone R Shiny GUI entry points and launchers
  shared/         cross-language parameter and output contracts
03_dependence/    bundled minimap2.exe, build recipe, offline bundle, R helpers
04_results/       run outputs (Git ignores everything except README)
05_builds/        R tarballs and R CMD check outputs (Git ignored)
06_GUI/           Python/Tkinter desktop window; ships 06_GUI/dist/nanoamp.exe
tmp/              scratch space (Git ignored)
```

## Quick start

The bundle ships `minimap2.exe` (statically linked, no MSYS2/Cygwin/conda/WSL
needed at runtime), so a normal run needs nothing but R.

### Easiest: double-click the desktop window

```text
06_GUI\dist\nanoamp.exe
```

A native Windows window: pick the FASTQ, pick the reference, press 开始分析, and
read the haplotype table and QC in the same window. See `06_GUI/README.md`.

### Command line

```powershell
# 1. Install the R package (see 03_dependence/r-environment/README.md for R itself)
R CMD INSTALL 02_code/r

# 2. Check the environment
sh 02_code/cli/nanoamp doctor

# 3. Install the test-data link layer (see the note below), then run one sample
Rscript 03_dependence/r-environment/materialize_test_data.R
sh 02_code/cli/nanoamp call `
  --reads 01_data/ln_test_data/TSM20260826/E4-3/reads.fastq `
  --reference 01_data/ln_test_data/TSM20260826/E4-3/reference.self.fa `
  --mode A --top-n 20 `
  --outdir 04_results/cli/demo

# 4. Launch the GUI
Rscript 02_code/gui/run_gui.R
```

R console:

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/ln_test_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/ln_test_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "04_results/r/demo/E4-3",
  mode      = "A"
)
res$haplotypes
```

### The `ln_test_data` link layer on Windows

`01_data/ln_test_data/**` is stored in Git as symlinks. Windows can only create
symlinks with Developer Mode (or `SeCreateSymbolicLinkPrivilege`) enabled, so in
a normal checkout those files land as ~100 byte text stubs containing a path
instead of sequence data. Run this once after cloning:

```powershell
Rscript 03_dependence/r-environment/materialize_test_data.R
```

It copies the real target content where a link is a stub, leaves genuine
symlinks alone, and finishes with an MD5 check of all 201 entries.

## Documentation

| Document | Content |
|---|---|
| `02_code/README.md` | source tree and component status |
| `02_code/r/README.md` | R package tutorial (English) |
| `02_code/r/README-CN.md` | R package tutorial (Chinese) |
| `02_code/cli/README.md` | CLI contract and launchers |
| `02_code/gui/README.md` | Shiny GUI (browser based) and Windows packaging |
| `06_GUI/README.md` | Python/Tkinter desktop window and exe packaging |
| `03_dependence/README.md` | bundled tools and Windows support matrix |
| `03_dependence/windows-x86_64/README.md` | Windows source build of minimap2 |
| `03_dependence/r-environment/README.md` | R environment setup and test runners |
| `03_dependence/offline-bundle/README.md` | air-gapped installation |
| `00_materials/README.md` | planning documents and work reports |

## External tools

`nanoamp` resolves tools in this order:

1. `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS`;
2. `03_dependence/<os>-<arch>/bin/` (`.exe` on Windows);
3. `PATH`.

The repository bundles **minimap2 2.31 for Windows x86_64**, built from upstream
source in this repository and statically linked, so it needs no MSYS2, Cygwin,
conda or WSL at runtime (it depends only on `KERNEL32.dll` and `msvcrt.dll`).
There is no official Windows build upstream; to reproduce this one:

```powershell
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1  # toolchain (~1.5 GB)
bash 03_dependence/windows-x86_64/build_minimap2.sh                  # build
```

On Windows on ARM, use the R-native backend instead:

```r
run_haplotype_analysis(..., aligner = "r")
```

samtools is optional and not bundled: SAM to BAM conversion uses
`Rsamtools::asBam()` by default, so no samtools binary is needed.

## Running the test suite

```powershell
# repair the test-data link layer first (once per clone)
Rscript 03_dependence/r-environment/materialize_test_data.R

# unit tests (uses the bundled minimap2)
Rscript 03_dependence/r-environment/run_tests.R

# functional regression over the real datasets in 01_data/
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir 04_results/r/test_run_win --modes A,B,C --threads 4
```

See `03_dependence/r-environment/README.md` for a from-scratch Windows
environment setup (R install, mirrors, dependency installation).

## Offline / air-gapped installation

To provision a machine with no network, build a pinned bundle of every upstream
installer (the R installer, the full R package closure, the MSYS2 toolchain for
rebuilds, and the minimap2 source) and install from it:

```powershell
# on a machine with a network
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R

# on the offline machine
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

The bundle lands in `dist/`, which is git-ignored: the repository keeps the
reproducible recipe and hashes, not the binaries. Rationale, the exact size
breakdown and the self-contained alternatives (USB payload, GitHub release
assets) are in `03_dependence/offline-bundle/README.md`.

## Common commands

```bash
make install          # install the R package
make test             # run testthat tests
make check            # build and R CMD check
make cli              # run `nanoamp doctor`
make gui              # launch the Shiny GUI (browser based)
make gui-python       # launch the Python/Tkinter desktop GUI
make gui-exe          # rebuild 06_GUI/dist/nanoamp.exe
make gui-test         # run the Python GUI self-tests
make deps             # show how the bundled minimap2.exe was built
make toolchain        # install the MSYS2/MINGW-w64 build toolchain
make offline-bundle   # fetch the offline installer bundle into dist/
make offline-install  # install everything from the bundle (no network)
```

## License

MIT.
