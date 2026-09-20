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

# repair the test-data link layer (see below)
Rscript 03_dependence/r-environment/materialize_test_data.R

# testthat suite
Rscript 03_dependence/r-environment/run_tests.R

# functional regression over the real datasets in 01_data/
Rscript 03_dependence/r-environment/run_functional_regression.R `
  --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
```

## The `ln_test_data` symlink layer on Windows

`01_data/ln_test_data/**` is stored in Git as **symlinks** (mode `120000`).
Windows can only create symlinks with Developer Mode (or
`SeCreateSymbolicLinkPrivilege`) enabled, so in a normal Windows checkout:

* `git checkout` writes each link target as a **~100 byte text stub** instead
  of a symlink, and
* `file.symlink()` used by `prepare_test_data.R` returns `FALSE` without
  creating anything.

Every `ln_test_data` file then contains a path string rather than sequence
data, and any analysis reading them fails. This is visible as failures in
`test-gui.R` (Mode C analysis) plus a stub-content README string.

`materialize_test_data.R` repairs this state: for each row of `manifest.tsv`
it compares the link path against the real target and **copies** the content
where needed. Genuine symlinks are detected via `Sys.readlink()` and left
alone, so the script is a no-op on Linux. It finishes with a full MD5
verification of all 201 entries.

Alternative if you do have symlink privileges:

```powershell
git config --global core.symlinks true   # requires Developer Mode, then re-clone
```

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
