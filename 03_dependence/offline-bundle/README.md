# offline-bundle — pre-positioning the installers inside the project

R, the build toolchain and the external tools can all be pre-positioned inside
the project, and the mechanism is implemented and verified. The installers
themselves must not be committed to Git: this directory holds the scripts, and
the artifacts live in `dist/`, which is git-ignored.

## Self-contained components vs components requiring installation

| Piece | Size | Status |
|---|---:|---|
| `minimap2.exe` | 1.3 MB | **already committed** — Windows analysis requires no further installation |
| samtools | — | **not needed** — `Rsamtools::asBam()` is the default SAM -> BAM path |
| R runtime + 109 R packages | ~430 MB | must be installed (or provisioned from `dist/`) |
| MSYS2 + MINGW-w64 toolchain | ~1.5 GB installed / 51 MB tarball | only needed to *rebuild* minimap2 from source |

An end user therefore needs R plus the package library. Rebuilding minimap2
additionally requires the toolchain.

## What the bundle contains

`fetch_offline_bundle.R` downloads, into `dist/`:

```text
dist/
|-- R-4.6.1-win.exe                   87.5 MB   R installer
|-- r-packages/
|   `-- bin/windows/contrib/4.6/       ~200 MB   109 package .zip files
|       |-- *.zip                                plus a PACKAGES index
|       `-- PACKAGES
|-- msys2/
|   `-- msys2-base-x86_64-20250830.tar.zst  51.3 MB   toolchain for rebuilds
|-- src/
|   `-- minimap2-2.31.tar.gz           0.3 MB   minimap2 source
|-- SOURCES.tsv                        provenance + SHA256 per file
`-- SHA256SUMS.txt                     integrity manifest
```

Total: **291 MB**, reproducible and pinned.

The published offline asset
`release/_build/nanoamp-0.1.0-windows-offline-deps.zip` (~248 MB) is packed by
`release/_build/build_assets.py` from `release/_offline/`, which holds the R
4.6.1 installer, the 109 R package binaries, the `PACKAGES` index,
`minimap2.exe` and `build_minimap2.sh`. It therefore corresponds to the R
runtime, R package repository and aligner parts of `dist/` above; the `msys2/`
toolchain and `src/` trees are needed only to rebuild the aligner and are not
shipped.

The package set is not a hand-written list. The script resolves the recursive
`Depends` / `Imports` / `LinkingTo` closure and then iterates until the closure
closes (new packages bring their own dependencies — e.g. `futile.logger` pulls
in `lambda.r` and `futile.options`). It finishes at 109 packages and reports
`complete`, or prints exactly what is still missing.

## Usage

```powershell
# on a machine WITH a network: build the bundle
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R

# on a machine WITHOUT a network: install everything from it
pwsh -File 03_dependence/offline-bundle/install_offline.ps1
```

`install_offline.ps1` verifies every file against `SHA256SUMS.txt`, installs R
silently as the current user (no administrator rights), installs all bundled
packages from the local repository, installs `nanoamp` and runs the bundled
test suite. It does not use the network.

## Verified offline

Tests run with `http_proxy`/`https_proxy` pointed at a dead port, so any network
attempt fails immediately, and with only the bundle-provided library visible:

```text
bundle packages visible      : 109
installed package dirs       : 109
nanoamp CMD INSTALL          : DONE
testthat                     : 34 passed, 0 failed, 0 errors, 0 skipped
functional (Mode A, E4-3)    : 2/2 ok, mean_overlap 1.0
```

## Why the artifacts are not committed to Git

1. **Hard file-size limits.** GitHub rejects any push containing a file over
   100 MiB and warns above 50 MiB. The R installer is 87.5 MB — under the hard
   limit but close enough that it would be refused outright on most other
   hosts, and it would be blocked the moment R ships a slightly larger build.
2. **History is permanent.** `git rm` does not reclaim the space; the blobs stay
   in history forever. A 291 MB bundle would make every future clone pay for it,
   permanently, on top of the 65 MB the repository already needs.
3. **Git LFS is not a free escape.** The free tier is 1 GB of storage and 1 GB
   of monthly bandwidth; a 291 MB bundle consumes a large share of both, and
   LFS traffic goes to `github.com` — the same endpoint that currently resets
   the connection from this network.
4. **Redistribution and licensing.** R, Rtools and MSYS2 are GPL-family; the
   109 packages carry their own licenses. Vendoring binaries into a repository
   makes the repository a redistributor and requires shipping all of that
   license text. Downloading at build time avoids the question entirely.
5. **It goes stale immediately.** A committed installer is obsolete the moment
   R or Bioconductor releases. A pinned recipe plus hashes stays correct.

## Pre-positioning the bundle outside the repository

A self-contained directory that can be copied by USB to an air-gapped machine is
produced by pointing `dest` at a location outside the Git repository:

```powershell
Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R D:\nanoamp-offline
```

The repository then stays small and the removable payload is explicit. Keeping
the bundle inside the repository requires an exception in `.gitignore`; items
1-4 above still apply and the push will most likely be rejected:

```gitignore
!dist/
```

For hosting rather than USB, `dist/` can be published as GitHub **release
assets** instead of commits: release assets are not counted against repository
size and keep `git clone` fast. Uploading them requires the same push access
that is currently blocked (see work report 6).

## Implementation notes

Two R behaviours affect the bundle build and are recorded here:

* **`contriburl=` and `repos=` are not interchangeable for a local repository
  root.** `repos="file:///<root>"` resolves
  `<root>/bin/windows/contrib/<rver>/PACKAGES`; `contriburl="file:///<root>"`
  looks for `<root>/PACKAGES`. Use `repos=` with a repository root.
* **Stale index files silently hide packages.** `write_PACKAGES(addFiles=TRUE)`
  also writes `PACKAGES.gz` / `PACKAGES.rds`, and a leftover index in a parent
  directory makes `available.packages()` report fewer packages than exist on
  disk (observed: 90 reported versus 109 present). The script deletes stale
  indexes in both the leaf and the root directory, keeps only the plain
  `PACKAGES`, and asserts that the index exposes every `.zip`.
