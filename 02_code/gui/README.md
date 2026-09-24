# Windows GUI (R Shiny)

The GUI is implemented with R Shiny and shipped inside the `nanoamp` R package.
The GUI calls the same R analysis functions as the CLI.

> A Python/Tkinter desktop window is also provided in `02_code/PythonGUI/`, and it
> ships as a double-clickable `02_code/PythonGUI/dist/nanoamp.exe`. It is a native
> window with no browser and no HTTP server, but it exposes fewer parameters.
> Both front ends call the same R package, so they cannot disagree about
> results; the choice between them depends on requirements. See
> `02_code/PythonGUI/README.md`.

## Current implementation

```r
library(nanoamp)
nanoamp_gui()
```

The app provides:

- FASTQ and reference FASTA file pickers;
- output directory selection;
- mode selection (A reference-guided, B de novo, C exact);
- `top_n` and advanced parameters;
- run button with progress and captured log;
- interactive haplotype and variant tables (DT);
- download buttons for `haplotypes.tsv` and `variants.tsv`;
- links to the output directory;
- alignment backend selection (`minimap2` or the R-native `r` fallback).

## Windows launch

After installing the R package and its dependencies:

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"
```

Or use the launcher shipped with the package:

```bat
02_code\gui\nanoamp-gui.bat
```

The app starts a local Shiny server and opens the default browser.

## Windows packaging plan

For a double-clickable Windows installer:

1. Build the R package on Windows;
2. Use RInno to bundle R, the package and its dependencies into one installer;
3. Bundle `minimap2.exe` if native speed is required. `samtools.exe` is optional
   because `Rsamtools` handles SAM to BAM conversion; the R-native backend
   (`aligner = "r"`) requires no external tool;
4. Test on a clean Windows 10/11 machine without R installed.

The RInno skeleton is in `inst/windows/build_installer.R`; it must be run on a
Windows machine.

External tools are resolved from `03_dependence/<os>-<arch>/bin/` first; see
`03_dependence/README.md`.

## Required packages

```r
install.packages(c("shiny", "DT"))
```

These are listed in `Suggests` so the core package remains lightweight.
