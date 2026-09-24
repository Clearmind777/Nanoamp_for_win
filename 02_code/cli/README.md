# CLI contract

The CLI is implemented in R and is part of the `nanoamp` R package. The Python
CLI planned earlier has been cancelled; all CLI development targets the R
implementation.

## Commands

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C] [options]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C] [options]
nanoamp doctor
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
| `--identity-cutoff` | float | 0.99 | Mode B clustering identity cutoff |
| `--min-cluster-reads` | int | 2 | Mode B minimum cluster size |
| `--consensus-method` | string | `decipher` | `decipher` or `medoid` |
| `--aligner` | string | `minimap2` | `minimap2` or `r` (R-native fallback) |
| `--threads` | int | 4 | Number of threads |
| `--ref-label` | string | reference name | Reference label in outputs |
| `--no-intermediates` | flag | false | Do not keep BAM files |

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

`call` writes `haplotypes.tsv`, `haplotypes.fasta`, `variants.tsv`, `qc.tsv` and
`run_manifest.json` into `--outdir`. Field definitions are in
`02_code/shared/docs/output_schema.md`.

## External tools

`minimap2` is resolved from `03_dependence/<os>-<arch>/bin/` first, then from
`PATH`. On platforms without a minimap2 binary, `--aligner r` selects the
R-native pairwise alignment backend. samtools is optional: SAM -> BAM is
handled by `Rsamtools` by default.

## Exit codes

| Code | Meaning |
|---:|---|
| 0 | Success |
| 1 | Any error (invalid arguments, missing input, missing dependency, analysis failure) |

The current implementation uses R error handling, so all failures exit with
code 1. More granular exit codes are a future improvement.
