# Building a Windows installer with RInno

This directory contains a skeleton for packaging the Shiny GUI as a Windows
installer with RInno.

RInno bundles R, the `nanoamp` package and its dependencies into a single
installer, so end users do not need to install R manually.

## Requirements

- Windows 10/11 build machine;
- R and Rtools;
- the `RInno` package;
- `minimap2.exe` (recommended); `samtools.exe` is optional because Rsamtools
  handles SAM to BAM conversion by default. The R-native backend
  (`aligner = "r"`) needs no external tool.

## Steps

1. Build and install the `nanoamp` package on Windows:

```bat
R CMD build 02_code\r
R CMD INSTALL nanoamp_0.1.0.tar.gz

:: If the tarball was produced by `make check` on a Unix-like environment:
:: R CMD INSTALL 04_builds\r\nanoamp_0.1.0.tar.gz
```

2. Run the skeleton:

```bat
Rscript 02_code\r\inst\windows\build_installer.R
```

3. The installer is written under the RInno working directory.

`build_installer.R` is a starting point and must be adapted to the local R
version, package list and browser choice.
