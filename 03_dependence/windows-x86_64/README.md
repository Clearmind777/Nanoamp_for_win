# windows-x86_64

Native Windows x86_64 support for nanoamp's external tools.

## Status

| Tool | Status | Notes |
|---|---|---|
| minimap2 | **bundled** `bin/minimap2.exe` (2.31-r1302) | built from source on Windows, statically linked |
| samtools | not bundled (not needed) | `Rsamtools::asBam()` handles SAM -> BAM by default |

`minimap2.exe` is built from the upstream v2.31 source with the MSYS2
MINGW-w64 toolchain. It is statically linked against libwinpthread and zlib, so
it has **no MSYS2 runtime dependency**: it runs from a plain Windows shell, on a
machine without MSYS2, Cygwin, conda or WSL.

```text
DLL Name: KERNEL32.dll
DLL Name: msvcrt.dll
```

nanoamp resolves it automatically, because `nanoamp_tool_path()` looks for
`03_dependence/<os>-<arch>/bin/<tool>.exe` before `PATH`:

```r
nanoamp:::nanoamp_tool_path("minimap2")
# ".../03_dependence/windows-x86_64/bin/minimap2.exe"
nanoamp:::nanoamp_tool_version("minimap2")
# "2.31-r1302"
```

## Rebuilding from source

Two steps, both unattended. Neither conda nor WSL is used.

### 1. Install the build toolchain

```powershell
pwsh -File 03_dependence/windows-x86_64/install_msys2_toolchain.ps1
```

This script:

1. downloads the pinned MSYS2 portable base tarball
   (`msys2-base-x86_64-20250830.tar.zst`) and verifies its SHA256
   (`A6C00B86...2EC57`);
2. extracts it with 7-Zip into `D:\tools\msys2` (override with `-ToolRoot`);
3. pins pacman to a fast mirror (override with `-Mirror`);
4. installs `base-devel`, `mingw-w64-x86_64-toolchain`,
   `mingw-w64-x86_64-zlib`, `mingw-w64-x86_64-cmake`,
   `mingw-w64-x86_64-ninja`.

It requires no administrator rights: the toolchain is a portable extraction,
not an installer, and it lives outside the repository. A full toolchain is
roughly 1.5 GB, so it is not committed; the repository commits this recipe plus
the resulting `minimap2.exe` (~1.3 MB).

Verified toolchain versions:

```text
gcc / binutils : 16.2.0-3 / 2.47-3
zlib           : 1.3.2-2
make           : 4.4.1-3
```

### 2. Build minimap2

```bash
bash 03_dependence/windows-x86_64/build_minimap2.sh
```

This downloads minimap2 v2.31, builds it, and installs `minimap2.exe` into
`bin/`. It prints `minimap2 --version` and the resulting DLL dependency list,
so the static-link status is verifiable.

### Build flags that matter

| Flag | Why |
|---|---|
| `-std=gnu11` | `kalloc.h` uses anonymous struct members, which gnu17/gnu23 reject; GCC 16 defaults to gnu23 and would otherwise fail |
| `-static` | folds in libwinpthread, so the exe does not need MSYS2 at runtime |
| `-static-libgcc` | removes the need for `libgcc_s_seh-1.dll` |
| `-Wno-error` | upstream warns on `%ld` vs `size_t` format specifiers under MINGW-w64 |

Building in the plain **MSYS** shell instead of **MINGW64** produces an
executable that depends on `msys-2.0.dll` and `msys-z.dll`; that variant only
runs with MSYS2 present, so it is not what this repository ships.

### Provenance of the bundled binary

| Field | Value |
|---|---|
| upstream | `https://github.com/lh3/minimap2` tag `v2.31` |
| version string | `2.31-r1302` |
| SHA256 | `82F0433956552B4D1ED0E09641F71F5750FC783548E317A302CA05A348BD1542` |
| license | MIT (`03_dependence/licenses/minimap2-LICENSE.txt`) |

## Alternatives (not used by this build)

* `aligner = "r"` — no external binary at all, uses Biostrings/pwalign pairwise
  alignment. Correct but roughly an order of magnitude slower on real data.
* Third-party Windows binaries — drop `minimap2.exe` / `samtools.exe` into
  `bin/` and nanoamp will resolve them.

## samtools on Windows

htslib officially supports Windows through MSYS2 MINGW64 and documents the
build. samtools is not required here: `Rsamtools::asBam()` is the default
SAM -> BAM path and is pure R + Bioconductor. Build samtools only when
`use_samtools = TRUE` is set explicitly.
