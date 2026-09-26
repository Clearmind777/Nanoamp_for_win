# nanoamp

`nanoamp` is an R package for analyzing Oxford Nanopore reads from PCR
amplicons. It aligns reads to a target sequence, corrects sequencing errors,
reconstructs haplotypes, and reports the most abundant sequences with counts
and proportions.

The package is intended to answer the following questions:

- How many reads match the intended PCR product exactly?
- What other sequences are present, and at what proportions?
- Which variants are real, and which are nanopore sequencing errors?
- Which haplotype carries which combination of variants?

## Installation

### 1. Install dependencies

```r
install.packages(c(
  "Biostrings", "Rsamtools", "IRanges", "Matrix",
  "data.table", "optparse", "jsonlite", "readxl"
))

# Recommended for Mode B (de novo clustering)
if (!requireNamespace("BiocManager", quietly = TRUE)) install.packages("BiocManager")
BiocManager::install("DECIPHER")

# Required for aligner = "r" on Bioconductor >= 3.19, which moved
# pairwiseAlignment() out of Biostrings
BiocManager::install("pwalign")

# Optional GUI
install.packages(c("shiny", "DT"))
```

`ShortRead` is deliberately **not** required: the package reads FASTQ itself
(`R/io.R` handles plain and gzip input and rejects malformed records), which also
keeps `pwalign` an optional provider instead of a hard dependency.

### 2. Install `nanoamp`

From a built tarball (for example the one produced by `make check`; adjust the
version if needed):

```r
install.packages("tmp/builds/r/nanoamp_0.1.0.tar.gz", repos = NULL, type = "source")
```

From the source directory:

```bash
R CMD INSTALL 02_code/r
```

During development:

```r
devtools::install("02_code/r")
```

### 3. Install external tools

No separate installation is required: the repository bundles a native Windows `minimap2.exe`.
`minimap2` is resolved from `03_dependence/<os>-<arch>/bin/` first, then from
`PATH`. `samtools` is optional: SAM to BAM conversion uses
`Rsamtools::asBam()` by default.

`PATH` configuration and troubleshooting instructions are in
[inst/docs/INSTALL_DEPENDENCIES.md](inst/docs/INSTALL_DEPENDENCIES.md).

`nanoamp` prefers tools from `03_dependence/<os>-<arch>/bin/`, then falls back
to `PATH`. The repository bundles minimap2 2.31 for Windows x86_64 (built from
source in-repo, statically linked); the Windows support matrix, the rebuild
recipe and the R-native fallback are documented in `03_dependence/README.md`.

```bash
minimap2 --version
# optional:
# samtools --version
```

Check everything from R:

```r
library(nanoamp)
nanoamp::nanoamp_cli("doctor")
```

## Quick start

```r
library(nanoamp)

res <- run_haplotype_analysis(
  reads     = "sample.fastq",
  reference = "target.fa",
  outdir    = "results/sampleA",
  mode      = "A",
  top_n     = 20
)

# Top haplotypes
res$haplotypes

# Candidate variants
res$variants

# QC metrics
res$qc
```

Basic input requirements:

- `reads`: FASTQ or FASTQ.GZ, single-end nanopore reads;
- `reference`: FASTA containing the intended amplicon sequence;
- `outdir`: output directory (created automatically).

## Analysis modes

### Mode A: reference-guided correction (recommended)

Mode A aligns reads to the target sequence, discovers candidate variants,
treats differences that do not pass the variant filters as sequencing errors,
and groups reads by their corrected sequence.

Mode A is applicable when:

- a reliable target sequence is available;
- quantitative haplotype proportions are required;
- real variants must be distinguished from nanopore errors.

### Mode B: de novo clustering (exploratory)

Mode B clusters reads with `DECIPHER::Clusterize` and builds a polished
consensus for each cluster using `DECIPHER::AlignSeqs` followed by majority
voting.

Mode B is applicable when:

- no reliable reference is available;
- a data-driven overview of the main sequence groups is required;
- haplotypes differing by less than the sequencing error rate may remain
  unresolved.

If `DECIPHER` is unavailable, Mode B falls back to variant-pattern greedy
clustering and records this in `qc.tsv`.

`DECIPHER::Clusterize` is stochastic upstream (the same input under a different
RNG state returned 29 vs 30 clusters at one cutoff), so nanoamp seeds that call
and records the seed in `qc.tsv` as `clustering_seed` (default 42). The caller's
RNG stream is saved and restored, so a library call cannot disturb the session it
was called from; without the seed, every Mode B result would differ between runs
and the functional-regression baseline could not be compared.

### Mode C: raw exact matching (diagnostic)

Mode C counts raw reads that match the reference exactly on either strand. It
is useful for demonstrating the effect of nanopore errors, but it is not
recommended for quantitative haplotype analysis.

## Parameters

Default parameters can be inspected with:

```r
nanoamp_defaults()
```

| Parameter | Default | Description |
|---|---:|---|
| `top_n` | 20 | Number of top haplotypes to report |
| `min_reads` | 3 | Minimum supporting reads for a candidate variant |
| `min_freq` | 0.02 | Minimum variant frequency |
| `min_identity` | 0.90 | Minimum read identity to the reference |
| `min_ref_coverage` | 0.90 | Minimum fraction of the reference covered by a read |
| `homopolymer` | 4 | Homopolymer length threshold for filtering |
| `strand_bias` | 0.90 | Strand bias threshold |
| `identity_cutoff` | 0.99 | Mode B clustering identity cutoff |
| `min_cluster_reads` | 2 | Mode B minimum cluster size |
| `max_msa_seqs` | 100 | Maximum sequences per consensus alignment |
| `consensus_method` | `"decipher"` | `"decipher"` or `"medoid"` |
| `aligner` | `"minimap2"` | `"minimap2"` or `"r"` (R-native fallback) |
| `use_samtools` | `FALSE` | Use samtools instead of Rsamtools for SAM to BAM |
| `threads` | 4 | Number of threads |
| `keep_intermediates` | `TRUE` | Keep BAM and other intermediate files |

## Functional annotation (optional)

Annotation is opt-in and off by default: without `annotation = "<config.json>"`
(CLI: `--annotate-config`) the outputs are byte for byte what they were before
the feature existed. When enabled, each haplotype's variants are translated into
biological consequences:

- **`cds` route (offline)**: the config supplies the CDS interval on the amplicon
  reference (`start`, `end`, `strand`, `frame`, `boundaries`). The length must be
  a multiple of three. No network, no reference files.
- **`genome` route (online)**: the amplicon is located in GRCh38 and the
  transcript structure is fetched from Ensembl REST. A reference that does not
  match the genome well enough is refused with an actionable error rather than
  force-located.

Extra outputs (see `shared/docs/output_schema.md` for every column):

| File | Content |
|---|---|
| `annotation.tsv` | One row per haplotype × transcript: English/Chinese consequence, protein change, `consequence_any_transcript`, `transcript_conflict` |
| `variants_annotation.tsv` | `annotation_detail = TRUE`: one row per variant with genomic/CDS position, codon and amino-acid change |
| `transcripts.tsv` | `list_transcripts = TRUE`: the transcripts overlapping the amplicon |

Skipped transcripts are recorded, not hidden: `qc.tsv` carries
`n_transcripts_annotated`, `n_transcripts_skipped` and (when something was
dropped) `annotation_skip_reason`, and `run_manifest.json` lists every dropped
transcript under `annotation.skipped_transcripts`. A run whose annotation was
skipped still exits 0, because the sequence analysis itself succeeded; use
`strict = TRUE` (CLI `--strict`) to turn that into a non-zero exit for pipelines.
Annotation adds no new R dependency (Biostrings/jsonlite are already required);
the online route additionally needs an HTTP client (`curl.exe` preferred, with an
R download fallback).

Example configs ship inside the package (`inst/configs/example_cds.json`,
`example_online.json`); `nanoamp doctor` prints the directory, and `install.exe`
also copies them to `<install root>\configs\`.

## Runtime status

Each run writes `run_manifest.json` and `nanoamp.log` into the output directory.
The manifest records the parameters, versions and input checksums plus
`status` (`done`/`failed`/`cancelled`), `error_class`
(`input`/`environment`/`network`/`internal`), `error_message` and `log_path`. A
failed run creates the directory and writes both files, so a failure is never
indistinguishable from a run that produced nothing. Exit codes are 0 for success
and 1 for failure.

## Output files

```text
outdir/
|-- haplotypes.tsv
|-- haplotypes.fasta
|-- variants.tsv
|-- qc.tsv
|-- run_manifest.json
|-- nanoamp.log                # the same log the console shows (written even on failure)
|-- annotation.tsv             # annotation = TRUE
|-- variants_annotation.tsv    # annotation_detail = TRUE
|-- transcripts.tsv            # list_transcripts = TRUE
`-- alignments.bam(.bai)       # Modes A and B, when keep_intermediates = TRUE
```

### haplotypes.tsv

| Column | Description |
|---|---|
| `rank` | Rank by supporting read count |
| `haplotype_id` / `cluster_id` | Haplotype or cluster identifier |
| `count` | Supporting reads |
| `proportion` | Fraction of assigned reads |
| `ci_low`, `ci_high` | 95% Wilson confidence interval |
| `is_reference` | Whether the sequence matches the reference |
| `n_snv`, `n_ins`, `n_del` | Number of variants |
| `length` | Haplotype length |
| `variants` | Variant description; `.` means no variant |

### variants.tsv

Mode A uses a company-compatible layout:

```text
Chr  Pos  Ref  Alt  DP  Ref_dp  Alt_dp  Freq  DP4  Seq  Filter_Status  Filter_Reason
```

- `Freq` is a fraction between 0 and 1;
- `-` in `Ref` or `Alt` represents an insertion or deletion;
- `Filter_Status` is `PASS` or `FILTERED`.

### qc.tsv

Two columns, `metric` and `value`, including read counts, mapping rate, mean
identity, coverage, clustering method, consensus method and DECIPHER version.
Mode B adds `clustering_seed` and `clustering_note`; `aligner = "r"` adds
`pairwise_provider`. Annotation adds `annotation_enabled`, `annotation_name`,
`annotation_route`, `annotation_source`, `ensembl_release`, `genetic_code`,
`n_transcripts`, `n_transcripts_annotated`, `n_transcripts_skipped`,
`annotation_available`, `n_haplotypes_annotated`, `n_haplotypes_skipped`,
`n_frameshift`, `n_stop_gained`, `n_stop_lost`, `n_start_lost`, `n_missense`,
`n_synonymous`, `n_inframe`, `n_transcript_conflicts` and, when transcripts were
dropped, `annotation_skip_reason`.

### run_manifest.json

Parameters, versions, reference metadata, input checksums, the QC values and (when
annotation ran) an `annotation` section with `enabled`, `available`, `source`,
`ensembl_release`, `config`, `genomic`, `transcripts` and `skipped_transcripts`.
It also carries the run status described under *Runtime status* above.

## Command line interface

The package ships a CLI based on the same R code.

```bash
nanoamp doctor

nanoamp call \
  --reads sample.fastq \
  --reference target.fa \
  --mode A \
  --top-n 20 \
  --outdir results/sampleA

nanoamp batch \
  --sample-sheet samples.tsv \
  --mode A \
  --outdir results/batch
```

The batch sample sheet is a TSV with at least:

```text
sample	reads	reference
```

Optional columns: `ref_label`.

Use `--aligner r` to select the R-native alignment backend on platforms
without minimap2. The repository-level launcher is `02_code/cli/nanoamp`
(`02_code/cli/nanoamp.bat` on Windows).

### Subcommands and the flags that changed most recently

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]
nanoamp doctor [--check-online]
nanoamp cache  [--cache-dir <dir>] [--clear]
nanoamp help
```

| Flag | Default | Notes |
|---|---|---|
| `--min-ref-coverage <p>` | 0.90 | Minimum fraction of the reference a read must cover |
| `--annotate-config <config.json>` | off | Enables annotation; the route comes from the file's `"route"` field |
| `--transcript <ENST...\|all>` | config value | Restrict annotation to one transcript, or annotate all of them |
| `--list-transcripts` | off | Print the overlapping transcripts and exit (also writes `transcripts.tsv`) |
| `--annotation-proteins` / `--annotation-detail` | off | Add protein sequences to `annotation.tsv` / write `variants_annotation.tsv` |
| `--cache-dir <dir>` / `--no-cache` / `--clear-cache` | — | Cache location, bypass for one run (never deletes), and empty-and-exit (works without input files) |
| `--strict` | off | Annotation that had to skip transcripts becomes a non-zero exit |

`doctor --check-online` reports whether Ensembl is reachable and exits non-zero
when it is not; `nanoamp cache` prints the cache directory, size and file count.
The cache directory is resolved as `NANOAMP_CACHE_DIR` →
`%LOCALAPPDATA%\nanoamp\cache\ref` → `%TEMP%\nanoamp\ref`, and a corrupted cache
entry is dropped and refetched instead of being reused.

### Install the `nanoamp` command

```bash
sh "$(Rscript --vanilla -e 'cat(system.file("scripts", "install_cli.sh", package = "nanoamp"))')" ~/.local/bin
export PATH="$HOME/.local/bin:$PATH"
nanoamp doctor
```

Alternatively, call the CLI directly from R:

```r
library(nanoamp)
nanoamp_cli(c("call", "--reads", "sample.fastq", "--reference", "target.fa",
              "--outdir", "results/sampleA"))
```

## Graphical user interface

Launch the Shiny GUI:

```r
library(nanoamp)
nanoamp_gui()
```

The GUI provides file pickers, mode selection, advanced parameters, a run
button, a captured log, interactive haplotype/variant tables, QC output and
download buttons.

On Windows:

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"

:: or use the shipped launcher
02_code\r\inst\scripts\nanoamp-gui.bat
```

To obtain the Shiny app object without starting a server:

```r
app <- nanoamp_gui_app()
```

For Windows installer packaging with RInno, see `inst/windows/README.md`.

### External tools and the R-native backend

`aligner = "minimap2"` uses the bundled minimap2 binary when available.
On Windows, ARM platforms, or any machine without minimap2, use:

```r
run_haplotype_analysis(..., aligner = "r")
```

The R-native backend uses Biostrings pairwise alignment and requires no
external tool. It is slower and is intended for small and medium amplicons.

It reports the coverage, identity and aligned end of the reference segment a read
actually aligned to. (Earlier versions reported the whole reference as covered for
every read, so a half-length read passed `--min-ref-coverage 0.99` and was counted
as the reference haplotype; the default `minimap2` backend was always correct.)

`samtools` is optional: SAM -> BAM conversion uses `Rsamtools::asBam()` by
default. Set `use_samtools = TRUE` only when the samtools path is explicitly
required.

## RStudio workflow

1. Open `02_code/r/nanoamp.Rproj`.
2. Edit the `CONFIG` block in `inst/scripts/run_analysis.R`.
3. Run the whole script.

The script locates the repository root automatically and writes results under
`tmp/test_results/r/`.

## Using the test data

The repository ships the samples directly under `01_data/<dataset>/<sample>/`
(ordinary files committed to Git; no preparation is required after cloning):

```text
reads.fastq
reference.self.fa
reference.wt.fa
consensus.N.fa
variants.N.xlsx
sanger.N.ab1
meta.tsv
```

Example:

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A"
)
```

## Tests and verification

```r
# Unit tests
testthat::test_check("nanoamp")   # from an installed package

# Or during development
devtools::test("02_code/r")
```

Full functional test across datasets:

```bash
Rscript 02_code/r/inst/scripts/run_functional_tests.R \
  --outdir tmp/test_results/r/test_run_2 --modes A,B,C --threads 4
```

The package has been verified with `R CMD check` (currently `Status: OK`) and
with 48 testthat cases / 192 assertions. The repository also runs a functional
regression over every sample in `01_data/` (168 runs) and compares it row by row
against the committed baseline in `03_dependence/baselines/functional/`:

```bash
make functional-test       # run the regression and compare with the baseline
make functional-baseline   # re-run and refresh the baseline (review the diff!)
```

`make stress-test` runs the automatable part of the environment stress matrix
(network/proxy/cache, degenerate inputs, paths with spaces and Chinese characters,
over-long paths, cancellation, concurrency); the last full run was
47 PASS / 0 FAIL / 2 SKIP, the two skips being the manual cases (disk full,
ARM64).

## Troubleshooting

| Symptom | Solution |
|---|---|
| `minimap2` not found | Install minimap2 and add it to `PATH` |
| `samtools` not found | Usually not required: `Rsamtools` is the default. Install samtools only if `use_samtools = TRUE` |
| Mode B runs slowly | Reduce `max_msa_seqs`, increase `threads`, or use `mode = "A"` |
| Mode B cannot resolve closely related haplotypes | This is expected below the sequencing error rate; use Mode A |
| `DECIPHER` not installed | Mode B falls back to greedy clustering; install DECIPHER for better results |
| `pairwiseAlignment` is not an exported object from Biostrings | Bioconductor >= 3.19 moved it to `pwalign`; install it with `BiocManager::install("pwalign")` |
| Annotation was skipped but the run exited 0 | That is the documented degradation: read `qc.tsv`'s `annotation_skip_reason` and the manifest's `annotation.skipped_transcripts`, or add `--strict` to fail instead |
| Ensembl unreachable / online route fails | Check network/proxy, retry with `--no-cache`, or switch the config to `"route": "cds"` (offline, needs the CDS interval) |
| All proportions are low in Mode C | Nanopore reads contain errors; use Mode A |

## License

MIT.
