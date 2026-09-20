# Installing dependencies for nanoamp (Windows)

This guide explains how to install and configure `minimap2`, `samtools` and
the R packages required by `nanoamp` on Windows.

This is the Windows variant of the project. `conda` and `WSL` are deliberately
not used; the Linux variant lives in the sister repository
`a_09_18_26_mapping_programs_dev_for_linux`.

## 1. What is needed

| Dependency | Type | Required for |
|---|---|---|
| `minimap2` | external command | Modes A and B (read alignment) |
| `samtools` | optional external command | Compatibility fallback; Rsamtools is used by default |
| R packages | R packages | Core analysis |
| `DECIPHER` | optional R package | Mode B de novo clustering |
| `shiny`, `bslib`, `DT` | optional R packages | GUI |

Mode C (raw exact matching) does not need `minimap2`. `samtools` is never
required because `Rsamtools::asBam()` handles SAM to BAM conversion.

## 2. minimap2 is already bundled

You normally do not have to install anything: the repository ships a native
Windows build of minimap2 2.31 at

```text
03_dependence\windows-x86_64\bin\minimap2.exe
```

`nanoamp` finds tools in this order:

1. `NANOAMP_MINIMAP2` / `NANOAMP_SAMTOOLS` environment variables;
2. `03_dependence\<os>-<arch>\bin\` (`.exe` on Windows);
3. `PATH`.

Because the bundled binary sits at level 2, it is picked up automatically with
no PATH changes. It is statically linked against libwinpthread and zlib, so it
depends only on `KERNEL32.dll` and `msvcrt.dll` and runs on a machine with no
MSYS2, Cygwin, conda or WSL installed.

Verify:

```r
library(nanoamp)
nanoamp:::nanoamp_tool_path("minimap2")
# ".../03_dependence/windows-x86_64/bin/minimap2.exe"
nanoamp:::nanoamp_tool_version("minimap2")
# "2.31-r1302"
```

### Rebuilding it from source

Upstream publishes no official Windows binary, but minimap2 compiles natively
with the MSYS2 MINGW-w64 toolchain. Two unattended, non-admin steps:

```powershell
# 1. portable MSYS2 + MINGW-w64 toolchain (~1.5 GB, outside the repo)
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1

# 2. build and install minimap2.exe
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

Pinned versions, the compiler flags that matter and the resulting hash are in
`03_dependence/windows-x86_64/README.md`.

### If you cannot use the bundled binary

On Windows on ARM, or if you prefer no external tool at all, use the R-native
alignment backend:

```r
run_haplotype_analysis(..., aligner = "r")
```

This is slower than minimap2 and is intended for small and medium amplicons.
Mode C needs no external tool either.

You can also supply your own build: drop `minimap2.exe` into
`03_dependence\windows-x86_64\bin\` and nanoamp will resolve it, or point
`NANOAMP_MINIMAP2` at it. Adding the folder to `PATH` works too, but is not
necessary.

## 3. samtools

Not needed and not bundled. `Rsamtools::asBam()` converts minimap2's SAM output
to BAM by default. Set `use_samtools = TRUE` only if you explicitly want the
samtools path, in which case you must build samtools yourself — htslib
documents MSYS2/MINGW64 as the recommended Windows build environment.

## 4. R packages

Required:

```r
install.packages(c(
  "Biostrings", "Rsamtools", "ShortRead", "IRanges", "Matrix",
  "data.table", "optparse", "jsonlite", "readxl"
))
```

If the Bioconductor packages are not available from CRAN:

```r
if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
BiocManager::install(c("Biostrings", "Rsamtools", "ShortRead", "IRanges"))
```

Optional:

```r
BiocManager::install("DECIPHER")     # Mode B clustering
BiocManager::install("pwalign")      # required by aligner = "r" on Bioconductor >= 3.19
install.packages(c("shiny", "DT"))   # GUI
```

For a fully scripted setup, including a dedicated library outside the
repository and mirrors that work from this network, use:

```powershell
Rscript 03_dependence/r-environment/setup_r_environment.R
```

## 5. Verification checklist

```r
library(nanoamp)
nanoamp_cli("doctor")
```

Expected output:

```text
nanoamp version: 0.1.0
R version: ...
Rscript: ...
  Biostrings   TRUE
  ...
  DECIPHER     TRUE
  minimap2     .../03_dependence/windows-x86_64/bin/minimap2.exe
  samtools     NOT FOUND
```

What to check:

- `minimap2` shows a path, not `NOT FOUND`;
- `samtools` showing `NOT FOUND` is expected and harmless;
- R packages show `TRUE`;
- `DECIPHER` may be `FALSE`: Mode B still works with a fallback, but DECIPHER
  is recommended.

## 6. Windows pitfalls

- **`conda install minimap2 samtools` will not work**: there is no win-64 build
  for these packages, and this project does not use conda anyway.
- **WSL is not used** by this project; there is no need to install it.
- **PATH not refreshed**: restart RStudio after changing `PATH`.
- **Spaces or non-ASCII characters in paths**: prefer `C:\tools\...`.
- **Windows SmartScreen**: allow the downloaded binaries if prompted.
- **Multiple R installations**: check `Rscript -e 'cat(R.home())'` and make
  sure the package is installed into the R you actually use.

## 7. Dependency reduction status

Already implemented:

1. `Rsamtools::asBam()` performs SAM to BAM conversion by default, so the
   `samtools` command is optional;
2. a native Windows `minimap2.exe` is bundled, so no external installation step
   is needed;
3. `aligner = "r"` provides an R-native pairwise alignment backend for small
   and medium datasets, and for Windows on ARM;
4. `minimap2` remains the recommended backend for large datasets.

Set `use_samtools = TRUE` only if you explicitly need the samtools path.
