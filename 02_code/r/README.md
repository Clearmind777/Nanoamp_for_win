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
  "Biostrings", "Rsamtools", "ShortRead", "IRanges", "Matrix",
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

## Output files

```text
outdir/
|-- haplotypes.tsv
|-- haplotypes.fasta
|-- variants.tsv
|-- qc.tsv
|-- run_manifest.json
`-- alignments.bam(.bai)     # Modes A and B, when keep_intermediates = TRUE
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
identity, coverage, clustering method, consensus method, and DECIPHER version.

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

The package has been verified with `R CMD check` and currently passes with
`Status: OK`.

## Troubleshooting

| Symptom | Solution |
|---|---|
| `minimap2` not found | Install minimap2 and add it to `PATH` |
| `samtools` not found | Usually not required: `Rsamtools` is the default. Install samtools only if `use_samtools = TRUE` |
| Mode B runs slowly | Reduce `max_msa_seqs`, increase `threads`, or use `mode = "A"` |
| Mode B cannot resolve closely related haplotypes | This is expected below the sequencing error rate; use Mode A |
| `DECIPHER` not installed | Mode B falls back to greedy clustering; install DECIPHER for better results |
| `pairwiseAlignment` is not an exported object from Biostrings | Bioconductor >= 3.19 moved it to `pwalign`; install it with `BiocManager::install("pwalign")` |
| All proportions are low in Mode C | Nanopore reads contain errors; use Mode A |

## License

MIT.
