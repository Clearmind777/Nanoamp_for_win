# CLI contract

The CLI is implemented in R and is part of the `nanoamp` R package. The Python
CLI planned earlier has been cancelled; all CLI development targets the R
implementation.

## Commands

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C] [options]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C] [options]
nanoamp doctor [--check-online]
nanoamp cache  [--cache-dir <dir>] [--clear]
nanoamp help
```

## call options

| Option | Type | Default | Description |
|---|---:|---:|---|
| `--reads` | path | required | Input FASTQ (plain or gz) |
| `--reference` | path | required | Target sequence FASTA |
| `--outdir` | path | required | Output directory |
| `--mode` | string | `A` | A reference-guided, B de novo, C exact |
| `--top-n` | int | 20 | Number of top haplotypes |
| `--min-reads` | int | 3 | Minimum supporting reads per variant |
| `--min-freq` | float | 0.02 | Minimum variant frequency |
| `--min-identity` | float | 0.90 | Minimum read identity |
| `--min-ref-coverage` | float | 0.90 | Minimum fraction of the reference a read must cover |
| `--identity-cutoff` | float | 0.99 | Mode B clustering identity cutoff |
| `--min-cluster-reads` | int | 2 | Mode B minimum cluster size |
| `--consensus-method` | string | `decipher` | `decipher` or `medoid` |
| `--aligner` | string | `minimap2` | `minimap2` or `r` (R-native fallback) |
| `--threads` | int | 4 | Number of threads |
| `--ref-label` | string | reference name | Reference label in outputs |
| `--no-intermediates` | flag | false | Do not keep BAM files |

## Functional annotation options (optional)

Annotation is opt-in: without `--annotate-config` the outputs are byte-identical to
a run without it.

| Option | Type | Default | Description |
|---|---:|---:|---|
| `--annotate-config` | path | off | JSON config; the **only** switch that enables annotation. Its `"route"` is `genome` (online) or `cds` (offline) |
| `--transcript` | string | from config | `ENST…` or `all`; overrides the config for this run only |
| `--list-transcripts` | flag | false | Print the amplicon's overlapping transcripts, write `transcripts.tsv`, and exit |
| `--annotation-proteins` | flag | false | Add reference/alternate protein columns to `annotation.tsv` |
| `--annotation-detail` | flag | false | Also write `variants_annotation.tsv` |
| `--cache-dir` | path | per-user cache | Reference-slice cache location (`NANOAMP_CACHE_DIR`) |
| `--no-cache` | flag | false | Do not read or write the cache for this run (never deletes it) |
| `--clear-cache` | flag | — | Empty the cache and exit; works **without** `--reads`/`--reference`/`--outdir` |
| `--strict` | flag | false | Exit non-zero when annotation had to skip transcripts |

An abbreviated flag such as `--annotate` is rejected with the closest implemented
option named; `--annotation-route` does not exist (the route lives in the config);
`--ensembl-release` is not implemented (read `annotation.ensembl_release` from
`run_manifest.json`).

## doctor / cache

`nanoamp doctor` prints R, dependency, tool and annotation prerequisites,
including `curl`, `cache-dir`, `cache-size`, `configs` and `annotation`.
With `--check-online` it additionally probes Ensembl and exits non-zero when it
is unreachable, so the online route can be checked before a run.

`nanoamp cache` prints `cache-dir`, `cache-size` and `cache-files`;
`--clear` empties the cache (only data that can be re-downloaded).

## Batch input

A TSV file that contains at least:

```text
sample	reads	reference
```

Optional column: `ref_label`.

## Installation

### Linux / macOS

```bash
sh 02_code/cli/install_cli.sh ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
nanoamp doctor
```

The installed R package also contains an equivalent script at
`system.file("scripts", "install_cli.sh", package = "nanoamp")`.

### Windows

After installing the R package, the available options are:

```bat
:: Install a wrapper
02_code\cli\install_cli.bat %USERPROFILE%\bin

:: Or use the repository launcher directly
02_code\cli\nanoamp.bat call --reads sample.fastq --reference target.fa --outdir results\sampleA
```

A `nanoamp.cmd` wrapper can also be placed in a directory on `PATH`:

```bat
@echo off
Rscript --vanilla -e "library(nanoamp); nanoamp_cli()" %*
```

## Outputs

`call` writes `haplotypes.tsv`, `haplotypes.fasta`, `variants.tsv`, `qc.tsv`,
`run_manifest.json` and `nanoamp.log` into `--outdir`; with annotation enabled it
also writes `annotation.tsv` (and `variants_annotation.tsv` with
`--annotation-detail`, `transcripts.tsv` with `--list-transcripts`). Field
definitions are in `02_code/shared/docs/output_schema.md`.

`run_manifest.json` carries `status` (`done`/`failed`), `error_class`
(`input`/`environment`/`network`/`internal`), `error_message` and `log_path`, and a
failed run writes the manifest and the log too.

## External tools

`minimap2` is resolved from `03_dependence/<os>-<arch>/bin/` first, then from
`PATH`. On platforms without a minimap2 binary, `--aligner r` selects the
R-native pairwise alignment backend. samtools is optional: SAM -> BAM is
handled by `Rsamtools` by default.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success (including a run that had to skip annotation transcripts — that is recorded in `qc.tsv`/`run_manifest.json`) |
| 1 | Any error (invalid arguments, missing input, missing dependency, network failure, analysis failure; also annotation skipped transcripts when `--strict` is given) |

All failures exit with code 1: the R error handling keeps a single non-zero code so
the launcher and the GUI can rely on it. Use `--strict` to make a degraded
annotation count as a failure.
