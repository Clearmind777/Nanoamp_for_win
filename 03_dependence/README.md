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
`-- r-environment/                    # R setup and test runners for Windows
    |-- README.md
    |-- setup_r_environment.R
    |-- run_tests.R
    |-- run_functional_regression.R
    `-- materialize_test_data.R
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

Official upstream facts:

- minimap2 publishes a Linux x86_64 binary; there is no *official* Windows
  binary, but the source builds natively on Windows with the MSYS2 MINGW-w64
  toolchain — that is how `windows-x86_64/bin/minimap2.exe` was made.
- samtools publishes only source, and is not needed by this project at all:
  `Rsamtools::asBam()` converts minimap2 SAM to BAM by default. Only set
  `use_samtools = TRUE` if you explicitly want the samtools path, in which case
  you would have to build it yourself (htslib documents MSYS2/MINGW64 as the
  recommended Windows build environment).
- conda and WSL are deliberately not used anywhere in this project.

## R-native fallback

`run_haplotype_analysis(..., aligner = "r")` uses Biostrings/pwalign pairwise
alignment and needs no external binary at all. It is slower than minimap2 and
is intended for small and medium amplicons, and for platforms where no
minimap2 build exists (Windows on ARM).

Mode C (`mode = "C"`) also needs no external tool.

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
bundle so a machine with no network can be provisioned:

```powershell
# with a network
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R
# without a network
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

The bundle (R installer, the full R package closure, the MSYS2 toolchain and
the minimap2 source) is written to the git-ignored `dist/`. Why the binaries are
not committed, and the USB / release-asset alternatives, are documented in
`offline-bundle/README.md`.

## Licenses

- minimap2: MIT;
- samtools: MIT/Expat (not bundled here).

License text for the bundled minimap2 binary is in `licenses/`.
