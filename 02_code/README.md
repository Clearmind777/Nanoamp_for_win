# 02_code: Source Code

This directory contains the R package, the R-based command line interface and
the graphical user interfaces.

This is the **Windows variant** of the project; the Linux variant lives in the
sister repository `a_09_18_26_mapping_programs_dev_for_linux`.

```text
02_code/
|-- README.md / README-CN.md
|-- shared/                 # Cross-language parameters and output schema
|   |-- params/default_params.json
|   `-- docs/output_schema.md
|-- r/                      # nanoamp R package
|   |-- DESCRIPTION / NAMESPACE / LICENSE
|   |-- R/                  # align.R, io.R (own FASTQ reader), annotate.R,
|   |                       #   annotate_config.R, ref_online.R, cli.R, ...
|   |-- inst/
|   |   |-- configs/        # bundled annotation example configs (shipped in the tarball)
|   |   |-- docs/           # dependency installation guides
|   |   |-- scripts/        # run_analysis.R, CLI and test scripts
|   |   |-- shiny/          # standalone Shiny entry point
|   |   `-- windows/        # RInno packaging skeleton
|   |-- tests/testthat/     # 48 cases / 192 assertions
|   |-- exec/nanoamp        # package CLI wrapper
|   |-- man/                # generated help
|   `-- README.md / README-CN.md
|-- cli/                    # repository CLI entry points and launchers
`-- gui/                    # repository Shiny GUI entry points and launchers
```

R is the analysis core; the CLI and the GUI front ends are thin shells that
call the `nanoamp` R package rather than reimplementing the analysis. The
Python/Tkinter GUI is an additional front end of the same kind. External tools
are bundled under `03_dependence/` at the repository root.

The Python CLI planned in an earlier revision was not implemented: CLI development
targets the R package (`nanoamp_cli()`). The Python code in `PythonGUI/` is a
desktop front end, not a CLI, and is what `release/03_GUI/` packages as
`nanoamp.exe`.

## Design principles

1. **One algorithm, thin front ends**: CLI and GUI call the `nanoamp` R package
   instead of reimplementing the analysis.
2. **Shared contracts**: parameter names, defaults and output columns are
   defined once in `shared/`.
3. **Data and code are separate**: test data lives in `01_data/`; run outputs
   live in `tmp/test_results/<front-end>/`.
4. **Windows first for the GUI**: the GUI is built with Shiny so it runs on
   Windows, and can be packaged with RInno later. The Python/Tkinter front end
   in `PythonGUI/` targets the same Windows desktop and is packaged with
   PyInstaller instead.
5. **Bundled tools first**: external tools are resolved from
   `03_dependence/<os>-<arch>/bin/` before `PATH`.

## R package quick start

```bash
# Install the package
R CMD INSTALL 02_code/r

# Check the environment (repository launcher)
sh 02_code/cli/nanoamp doctor

# Run one sample
nanoamp call \
  --reads 01_data/TSM20260826/E4-3/reads.fastq \
  --reference 01_data/TSM20260826/E4-3/reference.self.fa \
  --mode A --top-n 20 \
  --outdir tmp/test_results/r/demo/E4-3
```

R console:

```r
library(nanoamp)
res <- run_haplotype_analysis(
  reads     = "01_data/TSM20260826/E4-3/reads.fastq",
  reference = "01_data/TSM20260826/E4-3/reference.self.fa",
  outdir    = "tmp/test_results/r/demo/E4-3",
  mode      = "A"
)
res$haplotypes
```

## GUI

```r
library(nanoamp)
nanoamp_gui()
```

On Windows, after installing the package, run:

```bat
Rscript -e "library(nanoamp); nanoamp_gui()"
```

See `gui/README.md` for the GUI plan, launchers and Windows packaging notes.

## Functional annotation (optional)

Off by default: without `--annotate-config` (CLI) or the 「功能注释…」 checkbox (GUI)
the outputs are byte for byte what they were before the feature existed. When
enabled, each haplotype's variants are translated into biological consequences
and two extra files are written:

| File | Content |
|---|---|
| `annotation.tsv` | One row per haplotype × transcript, with English/Chinese consequence columns, protein change and a transcript-conflict flag |
| `variants_annotation.tsv` | With `--annotation-detail`: one row per variant, with CDS position, codon and amino-acid change |
| `transcripts.tsv` | With `--list-transcripts` / the GUI's 「列出转录本」: the overlapping transcripts of the amplicon |

Two routes, chosen in the config file (`"route": "genome"` or `"cds"`):

- **`cds` (offline)**: the user supplies the CDS interval on the amplicon
  reference (1-based, inclusive, length a multiple of three); no network is used;
- **`genome` (online)**: the amplicon is located in GRCh38 and the transcript
  structure is fetched from Ensembl REST.

Skipped transcripts are recorded rather than hidden (`qc.tsv`'s
`annotation_skip_reason`, `run_manifest.json`'s `annotation.skipped_transcripts`)
and the run still exits 0, because the sequence analysis itself succeeded;
`--strict` turns that same situation into exit 1 for pipelines. Annotation adds
no new R dependency (it reuses Biostrings/jsonlite); the only external
prerequisite is `curl.exe` for the online route, with an R download fallback.
Example configs ship inside the package (`inst/configs/`, path printed by
`nanoamp doctor` under `configs`), and `install.exe` also copies them to
`<install root>\configs\`.

The CLI surface behind all of this:

```text
nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]
nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]
nanoamp doctor [--check-online]      # environment check; also probes Ensembl
nanoamp cache  [--cache-dir <dir>] [--clear]
nanoamp help
```

Recent flags: `--annotate-config`, `--transcript <ENST...|all>`,
`--list-transcripts`, `--annotation-proteins`, `--annotation-detail`,
`--min-ref-coverage <p>`, `--cache-dir`, `--no-cache`, `--clear-cache` and
`--strict`; `clustering_seed` in `qc.tsv` records the seed that makes Mode B
reproducible.

## Runtime status

Every run writes `run_manifest.json` (parameters, versions, input checksums, and
now `status` = `done`/`failed`/`cancelled`, `error_class` =
`input`/`environment`/`network`/`internal`, `error_message`, `log_path`) plus
`nanoamp.log`. A failed run creates its output directory and writes both files,
so a failure is never indistinguishable from a run that produced nothing. Exit
codes remain 0 (success) and 1 (failure).

## Status

| Component | Status |
|---|---|
| R package | Implemented; `R CMD check` reports `Status: OK`; 48 testthat cases / 192 assertions; reads FASTQ itself, so no ShortRead dependency |
| R-based CLI | Implemented (`nanoamp_cli()` and `02_code/cli`), including `doctor [--check-online]` and `cache [--clear]` |
| Functional annotation | Implemented and tested (offline `cds` and online `genome` routes) |
| Functional regression | 168 runs over `01_data/` compared row by row against the committed baseline in `03_dependence/baselines/functional/` (`make functional-test`); Mode B reproducible via the recorded `clustering_seed` |
| Environment stress matrix | `03_dependence/stress/run_stress_tests.py` (groups A–D): last full run 47 PASS / 0 FAIL / 2 SKIP (manual disk-full and ARM64) |
| R Shiny GUI | Initial version implemented (`nanoamp_gui()` and `02_code/gui`) |
| Python/Tkinter GUI | Implemented and packaged as `02_code/PythonGUI/dist/nanoamp.exe`; 7 self-test scripts all pass |
| Windows installer | Implemented with PyInstaller (`release/_installer/`; ships `install.exe` and `uninstall.exe`); 9 logic-test scripts all pass |

External tools are bundled under `03_dependence/`; see `03_dependence/README.md`
for the platform support matrix and the R-native fallback.

## Shared contracts

- `shared/params/default_params.json`: parameter names and defaults;
- `shared/docs/output_schema.md`: output file and column definitions, including the
  annotation chapter (`transcripts.tsv`, `annotation.tsv`,
  `variants_annotation.tsv`, consequence vocabulary, annotation QC metrics) and the
  `run_manifest.json` status fields;
- `cli/README.md`: CLI command contract;
- `gui/README.md`: GUI behaviour and deployment plan.
