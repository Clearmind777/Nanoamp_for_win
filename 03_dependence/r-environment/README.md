# R environment setup on Windows

This directory contains the reproducible setup used to run the `nanoamp` test
suite and functional regression on a Windows machine, without conda and
without WSL.

## What is installed where

| Item | Location | In git? |
|---|---|---|
| R 4.6.1 | `D:\tools\R\R-4.6.1` | no (binary install) |
| R library | `D:\tools\R\lib` | no (installed packages) |
| MSYS2 + MINGW-w64 | `D:\tools\msys2` | no (see `../windows-x86_64/`) |
| build recipe (this repo) | `03_dependence/` | yes |

Nothing R-related lives inside the repository, so the working tree stays clean.

## 1. Install R

Download the official Windows installer and run it silently, current-user only
(no administrator rights needed):

```powershell
curl.exe -L --ssl-no-revoke -o R-win.exe https://cloud.r-project.org/bin/windows/base/R-4.6.1-win.exe
Start-Process .\R-win.exe -ArgumentList '/VERYSILENT','/NORESTART','/CURRENTUSER','/DIR=D:\tools\R\R-4.6.1' -Wait
```

## 2. Point R at a dedicated library

Add this to `D:\tools\R\R-4.6.1\etc\Rprofile.site` so every session finds the
private library and a mirror that is reachable:

```r
local({
  lib <- "D:/tools/R/lib"
  if (dir.exists(lib)) .libPaths(c(lib, .libPaths()))
  options(
    repos = c(CRAN = "https://mirrors.tuna.tsinghua.edu.cn/CRAN/"),
    BioC_mirror = "https://bioconductor.org",
    Ncpus = max(1L, parallel::detectCores() - 1L)
  )
})
```

## 3. Install the dependencies

```powershell
Rscript 03_dependence/r-environment/setup_r_environment.R
```

This installs `BiocManager`, `data.table`, `jsonlite`, `optparse`, `readxl`,
`testthat`, `pkgload`, the Bioconductor packages `Biostrings`, `IRanges`,
`Rsamtools`, `ShortRead`, and the optional `shiny`, `DT`, `DECIPHER`
(Mode B clustering) and `pwalign` (see the compatibility note below).

## 4. Install nanoamp and run the tests

```powershell
R CMD INSTALL --library=D:/tools/R/lib 02_code/r

# testthat suite
Rscript 03_dependence/r-environment/run_tests.R

# functional regression over the real datasets in 01_data/
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
```

## Test data

`01_data/<dataset>/<sample>/` holds the analysis files under fixed names
(`reads.fastq`, `reference.self.fa`, `reference.wt.fa`, `consensus.N.fa`,
`variants.N.xlsx`, `sanger.N.ab1`) plus a `meta.tsv` that records which company
deliverable each file came from. They are ordinary files committed to Git, so a
clone is usable immediately — there is no link layer to repair and no
post-clone step. `run_functional_tests.R` discovers samples by walking
`01_data/*/*/meta.tsv`.

The company's original deliverables (including the two `SD…` batches, which
have no FASTQ) and their naming rules are documented in
`01_data/README-raw.md`.

## Notes on this network

Two environment quirks shaped the setup above and are worth knowing if you
reproduce it:

1. **Git and curl fail with `CRYPT_E_REVOCATION_OFFLINE`.** The certificate
   revocation responder is unreachable here. Fixes used:
   `curl --ssl-no-revoke`, and for git either
   `git config http.sslBackend openssl` or
   `git config http.schannelCheckRevoke false`.
2. **Throughput is very uneven between hosts.** Mirrors used:
   `mirrors.tuna.tsinghua.edu.cn` (~3 MB/s), while `github.com` release
   assets, `raw.githubusercontent.com` and `sourceforge.net` measured
   ~30-60 KB/s and `mirror.msys2.org` stalled at ~8 KB/s. Prefer TUNA for
   CRAN, MSYS2 and Rtools downloads.

## `pwalign` compatibility

Bioconductor 3.19 moved `pairwiseAlignment()`, `pattern()`, `subject()`,
`aligned()` and `score()` from **Biostrings** into **pwalign**. On current
Bioconductor, `Biostrings::pairwiseAlignment()` therefore errors with
`'pairwiseAlignment' is not an exported object from 'namespace:Biostrings'`,
which broke the `aligner = "r"` backend.

`nanoamp` now resolves the provider at load time (`R/zzz.R`, `.onLoad`) and
uses whichever package exports it, so the R-native backend works on both old
and new Bioconductor. `pwalign` is listed in `Suggests`.
`nanoamp:::pa_provider_name()` reports which provider is active.
