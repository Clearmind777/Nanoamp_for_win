# ---------------------------------------------------------------------------
# Command line interface
# ---------------------------------------------------------------------------

cli_usage <- function() {
  cat(
    "nanoamp - nanopore amplicon haplotype analysis\n\n",
    "Usage:\n",
    "  nanoamp call   --reads <fastq> --reference <fasta> --outdir <dir> [--mode A|B|C]\n",
    "  nanoamp batch  --sample-sheet <tsv> --outdir <dir> [--mode A|B|C]\n",
    "  nanoamp doctor [--check-online]\n",
    "  nanoamp cache  [--cache-dir <dir>] [--clear]\n",
    "  nanoamp help\n\n",
    "Functional annotation (optional):\n",
    "  --annotate-config <config.json>   enable annotation (\"route\": genome | cds)\n",
    "  --transcript <ENST...|all>        restrict the annotation to a transcript\n",
    "  --list-transcripts                list the amplicon's transcripts and exit\n",
    "  --annotation-proteins             also write reference/alternate proteins\n",
    "  --annotation-detail               also write variants_annotation.tsv\n",
    "  --cache-dir <dir>                 where reference slices are cached\n",
    "  --no-cache                        ignore the cache for this run\n",
    "  --clear-cache                     empty the cache and exit\n",
    "  --strict                          fail (non-zero) if annotation skipped transcripts\n\n",
    "Alignment and thresholds:\n",
    "  --aligner minimap2|r            --threads <n>\n",
    "  --min-reads <n>                 --min-freq <p>        --min-identity <p>\n",
    "  --min-ref-coverage <p>          --top-n <n>           --no-intermediates\n\n",
    "Examples:\n",
    "  nanoamp call --reads sample.fastq --reference target.fa --mode A --top-n 20 --outdir out\n",
    "  nanoamp call --reads s.fastq --reference a.fa --outdir out \\\n",
    "      --annotate-config configs/example_cds.json --annotation-detail\n",
    "  nanoamp doctor --check-online\n",
    "  nanoamp cache --clear\n",
    sep = ""
  )
}

cli_call_options <- function() {
  list(
    optparse::make_option(c("--reads"), type = "character", help = "Input FASTQ"),
    optparse::make_option(c("--reference"), type = "character", help = "Target sequence FASTA"),
    optparse::make_option(c("--outdir"), type = "character", help = "Output directory"),
    optparse::make_option(c("--mode"), type = "character", default = "A",
                          help = "A reference-guided, B de novo, C exact [default A]"),
    optparse::make_option(c("--top-n"), type = "integer", default = 20,
                          help = "Number of top haplotypes to report [default 20]"),
    optparse::make_option(c("--min-reads"), type = "integer", default = 3,
                          help = "Minimum supporting reads per variant [default 3]"),
    optparse::make_option(c("--min-freq"), type = "double", default = 0.02,
                          help = "Minimum variant frequency [default 0.02]"),
    optparse::make_option(c("--min-identity"), type = "double", default = 0.90,
                          help = "Minimum read identity [default 0.90]"),
    optparse::make_option(c("--min-ref-coverage"), type = "double", default = 0.90,
                          help = "Minimum fraction of the reference covered by a read [default 0.90]"),
    optparse::make_option(c("--identity-cutoff"), type = "double", default = 0.99,
                          help = "Mode B clustering identity cutoff [default 0.99]"),
    optparse::make_option(c("--min-cluster-reads"), type = "integer", default = 2,
                          help = "Mode B minimum cluster size [default 2]"),
    optparse::make_option(c("--consensus-method"), type = "character", default = "decipher",
                          help = "Mode B consensus method: decipher or medoid"),
    optparse::make_option(c("--aligner"), type = "character", default = "minimap2",
                          help = "Alignment backend: minimap2 or r"),
    optparse::make_option(c("--threads"), type = "integer", default = 4,
                          help = "Number of threads [default 4]"),
    optparse::make_option(c("--ref-label"), type = "character", default = NULL,
                          help = "Reference label used in outputs"),
    optparse::make_option(c("--no-intermediates"), action = "store_true", default = FALSE,
                          help = "Do not keep BAM and other intermediate files"),
    optparse::make_option(c("--annotate-config"), type = "character", default = NULL,
                          help = "Functional annotation config (JSON); enables annotation"),
    optparse::make_option(c("--transcript"), type = "character", default = NULL,
                          help = "Transcript id to annotate, or 'all' for every overlapping transcript"),
    optparse::make_option(c("--list-transcripts"), action = "store_true", default = FALSE,
                          help = "List candidate transcripts for the amplicon and exit"),
    optparse::make_option(c("--clear-cache"), action = "store_true", default = FALSE,
                          help = "Clear the annotation reference cache and exit"),
    optparse::make_option(c("--no-cache"), action = "store_true", default = FALSE,
                          help = "Ignore cached reference slices and re-fetch them"),
    optparse::make_option(c("--cache-dir"), type = "character", default = NULL,
                          help = "Annotation reference cache directory [default: per-user cache]"),
    optparse::make_option(c("--annotation-proteins"), action = "store_true", default = FALSE,
                          help = "Include reference and alternate protein sequences in annotation.tsv"),
    optparse::make_option(c("--annotation-detail"), action = "store_true", default = FALSE,
                          help = "Also write variants_annotation.tsv with per-variant consequences"),
    optparse::make_option(c("--strict"), action = "store_true", default = FALSE,
                          help = "Fail with a non-zero status if annotation had to skip transcripts")
  )
}

cli_batch_options <- function() {
  list(
    optparse::make_option(c("--sample-sheet"), type = "character"),
    optparse::make_option(c("--outdir"), type = "character"),
    optparse::make_option(c("--mode"), type = "character", default = "A"),
    optparse::make_option(c("--top-n"), type = "integer", default = 20),
    optparse::make_option(c("--threads"), type = "integer", default = 4),
    optparse::make_option(c("--min-reads"), type = "integer", default = 3),
    optparse::make_option(c("--min-freq"), type = "double", default = 0.02),
    optparse::make_option(c("--min-identity"), type = "double", default = 0.90),
    optparse::make_option(c("--min-ref-coverage"), type = "double", default = 0.90),
    optparse::make_option(c("--identity-cutoff"), type = "double", default = 0.99),
    optparse::make_option(c("--min-cluster-reads"), type = "integer", default = 2),
    optparse::make_option(c("--consensus-method"), type = "character", default = "decipher"),
    optparse::make_option(c("--aligner"), type = "character", default = "minimap2"),
    optparse::make_option(c("--no-intermediates"), action = "store_true", default = FALSE),
    optparse::make_option(c("--annotate-config"), type = "character", default = NULL),
    optparse::make_option(c("--transcript"), type = "character", default = NULL),
    optparse::make_option(c("--list-transcripts"), action = "store_true", default = FALSE),
    optparse::make_option(c("--clear-cache"), action = "store_true", default = FALSE),
    optparse::make_option(c("--no-cache"), action = "store_true", default = FALSE),
    optparse::make_option(c("--cache-dir"), type = "character", default = NULL),
    optparse::make_option(c("--annotation-proteins"), action = "store_true", default = FALSE),
    optparse::make_option(c("--annotation-detail"), action = "store_true", default = FALSE),
    optparse::make_option(c("--strict"), action = "store_true", default = FALSE)
  )
}

# --cache-dir is the CLI counterpart of the NANOAMP_CACHE_DIR environment
# variable that annotation_cache_dir() reads; set it before anything touches
# the cache (the --clear-cache / --no-cache paths below included).
cli_apply_cache_dir <- function(opt) {
  d <- opt$`cache-dir`
  if (!is.null(d) && length(d) == 1L && !is.na(d) && nzchar(d)) {
    Sys.setenv(NANOAMP_CACHE_DIR = d)
  }
  invisible(TRUE)
}

# `--no-cache` means "bypass the cache for this run" (annotate.R honours
# NANOAMP_NO_CACHE). It must NOT delete anything: the cache directory is shared
# with other runs and with later samples.
cli_apply_no_cache <- function(opt) {
  if (isTRUE(opt$`no-cache`)) Sys.setenv(NANOAMP_NO_CACHE = "1")
  invisible(TRUE)
}

# ---------------------------------------------------------------------------
# Long-flag validation
#
# optparse (via getopt) accepts unambiguous abbreviations, so `--annotate`
# silently binds to `--annotate-config` and `--ref` to `--ref-label`, which
# turns a typo into a confusing "config not found" error. Abbreviations are
# rejected up front and the real flag is suggested.
# ---------------------------------------------------------------------------

cli_long_flags <- function(options) {
  out <- tryCatch(
    vapply(options, function(o) {
      # optparse changed its slot names between generations; accept both.
      for (nm in c("long_name", "long_flag")) {
        if (nm %in% methods::slotNames(o)) {
          v <- methods::slot(o, nm)
          if (length(v) == 1L && !is.na(v) && nzchar(v)) return(as.character(v))
        }
      }
      NA_character_
    }, character(1), USE.NAMES = FALSE),
    error = function(e) character(0)
  )
  sort(unique(out[!is.na(out) & nzchar(out)]))
}

cli_legacy_flag_hint <- function(name) {
  switch(
    name,
    "--annotate" = paste0(
      " Functional annotation is enabled with --annotate-config <config.json>;\n",
      "  the route comes from the config file's \"route\" field."),
    "--annotation-route" = paste0(
      " There is no --annotation-route: put \"route\": \"genome\" or \"cds\"\n",
      "  inside the config file."),
    "--ensembl-release" = paste0(
      " Not implemented in v0.1.0: read annotation.ensembl_release from\n",
      "  run_manifest.json instead."),
    "--ref" = paste0(
      " Use --reference <fasta> for the input, or --ref-label <label> for the\n",
      "  label written to the outputs."),
    ""
  )
}

cli_check_flags <- function(args, options) {
  known <- cli_long_flags(options)
  if (length(known) == 0L) return(invisible(TRUE))  # introspection unavailable
  for (a in args) {
    if (!grepl("^--", a)) next
    name <- sub("=.*$", "", a)
    if (name %in% known || identical(name, "--help")) next
    near <- known[startsWith(known, name)]
    hint <- cli_legacy_flag_hint(name)
    # A flag worth explaining even though it is not a prefix of any real option
    # (--annotation-route, --ensembl-release) must be caught here too: the
    # message below is the only place that explains what to use instead.
    if (length(near) == 0L && !nzchar(hint)) next
    if (length(near) > 0L) {
      stop(sprintf(
        "Unknown option '%s'.%s\nClosest implemented option(s): %s\nAbbreviations are not accepted.",
        name, hint, paste(near, collapse = ", ")
      ), call. = FALSE)
    }
    stop(sprintf(
      "Unknown option '%s'.%s\nSee --help for the implemented options.",
      name, hint
    ), call. = FALSE)
  }
  invisible(TRUE)
}

cli_cmd_call <- function(args) {
  options <- cli_call_options()
  cli_check_flags(args, options)
  opt <- optparse::parse_args(
    optparse::OptionParser(option_list = options), args = args
  )
  cli_apply_cache_dir(opt)
  cli_apply_no_cache(opt)
  # `--clear-cache` is a cache operation, not an analysis: it must work on its
  # own (the GUI calls "nanoamp call --clear-cache" to empty the cache), so it is
  # handled before the input arguments are required.
  if (isTRUE(opt$`clear-cache`)) {
    d <- annotation_cache_clear()
    cat("Cleared annotation cache:", d, "\n")
    return(invisible(TRUE))
  }
  if (is.null(opt$reads) || is.null(opt$reference) || is.null(opt$outdir)) {
    cli_usage()
    stop("call requires --reads, --reference and --outdir", call. = FALSE)
  }
  config_path <- cli_annotation_config(opt, opt$outdir)
  res <- run_haplotype_analysis(
    reads = opt$reads, reference = opt$reference, outdir = opt$outdir,
    mode = opt$mode, top_n = opt$`top-n`,
    min_reads = opt$`min-reads`, min_freq = opt$`min-freq`,
    min_identity = opt$`min-identity`,
    min_ref_coverage = opt$`min-ref-coverage`,
    identity_cutoff = opt$`identity-cutoff`,
    min_cluster_reads = opt$`min-cluster-reads`,
    consensus_method = opt$`consensus-method`,
    aligner = opt$aligner,
    threads = opt$threads,
    keep_intermediates = !isTRUE(opt$`no-intermediates`),
    ref_label = opt$`ref-label`,
    annotation = config_path,
    list_transcripts = isTRUE(opt$`list-transcripts`),
    annotation_proteins = isTRUE(opt$`annotation-proteins`),
    annotation_detail = isTRUE(opt$`annotation-detail`),
    strict = isTRUE(opt$strict)
  )
  cli_strict_check(res)
  invisible(TRUE)
}

# `--strict`: annotation that had to skip transcripts is a failure for a
# pipeline, even though the sequence analysis itself succeeded. The run has
# already recorded `status = "failed"` and the reason in run_manifest.json, so
# this only turns it into a non-zero exit code (1, like every other failure: the
# GUI and the launcher only know 0 and 1).
cli_strict_check <- function(res) {
  problem <- res$strict_failure
  if (is.null(problem)) return(invisible(TRUE))
  stop(sprintf(
    paste0(
      "Annotation was incomplete and --strict was given:\n  %s\n",
      "See qc.tsv (annotation_skip_reason) and run_manifest.json ",
      "(annotation.skipped_transcripts).\n",
      "Drop --strict to treat this as a recorded degradation instead."
    ), problem
  ), call. = FALSE)
}

cli_cmd_batch <- function(args) {
  options <- cli_batch_options()
  cli_check_flags(args, options)
  opt <- optparse::parse_args(
    optparse::OptionParser(option_list = options), args = args
  )
  cli_apply_cache_dir(opt)
  cli_apply_no_cache(opt)
  # Same as `call`: emptying the cache works without a sample sheet.
  if (isTRUE(opt$`clear-cache`)) {
    d <- annotation_cache_clear()
    cat("Cleared annotation cache:", d, "\n")
    return(invisible(TRUE))
  }
  if (is.null(opt$`sample-sheet`) || is.null(opt$outdir)) {
    cli_usage()
    stop("batch requires --sample-sheet and --outdir", call. = FALSE)
  }
  # Resolve the annotation config once for the whole batch (upstream accepted
  # these flags here but never forwarded them, so `batch --annotate-config`
  # silently did nothing).
  config_path <- cli_annotation_config(opt, opt$outdir)
  sheet <- data.table::fread(opt$`sample-sheet`, sep = "\t", header = TRUE)
  needed <- c("sample", "reads", "reference")
  if (!all(needed %in% names(sheet))) {
    stop(sprintf("sample-sheet must contain columns: %s", paste(needed, collapse = ", ")),
         call. = FALSE)
  }
  summary_rows <- list()
  for (i in seq_len(nrow(sheet))) {
    outdir <- file.path(opt$outdir, sheet$sample[i])
    status <- "ok"
    err <- ""
    tryCatch({
      res_i <- run_haplotype_analysis(
        reads = sheet$reads[i], reference = sheet$reference[i], outdir = outdir,
        mode = opt$mode, top_n = opt$`top-n`, threads = opt$threads,
        min_reads = opt$`min-reads`, min_freq = opt$`min-freq`,
        min_identity = opt$`min-identity`,
        min_ref_coverage = opt$`min-ref-coverage`,
        identity_cutoff = opt$`identity-cutoff`,
        min_cluster_reads = opt$`min-cluster-reads`,
        consensus_method = opt$`consensus-method`,
        aligner = opt$aligner,
        keep_intermediates = !isTRUE(opt$`no-intermediates`),
        ref_label = if ("ref_label" %in% names(sheet)) sheet$ref_label[i] else NULL,
        annotation = config_path,
        list_transcripts = isTRUE(opt$`list-transcripts`),
        annotation_proteins = isTRUE(opt$`annotation-proteins`),
        annotation_detail = isTRUE(opt$`annotation-detail`),
        strict = isTRUE(opt$strict)
      )
      # Under --strict a degraded annotation is this sample's failure; the row
      # in batch_summary.tsv then says error, like any other failed sample.
      cli_strict_check(res_i)
      TRUE
    }, error = function(e) {
      status <<- "error"
      err <<- conditionMessage(e)
      # A failed sample can still leave an empty directory behind, because the
      # analysis creates its outdir before it opens the input files. A tree of
      # empty directories makes a batch look like it half-succeeded, so remove
      # it -- but only if it is empty, so partial results are never destroyed.
      if (dir.exists(outdir)) {
        leftover <- list.files(outdir, all.files = TRUE, no.. = TRUE)
        if (!length(leftover)) unlink(outdir, recursive = TRUE, force = TRUE)
      }
      FALSE
    })
    summary_rows[[i]] <- data.table::data.table(
      sample = sheet$sample[i], mode = opt$mode, outdir = outdir,
      status = status, error = err
    )
  }
  out <- data.table::rbindlist(summary_rows, use.names = TRUE)
  dir.create(opt$outdir, recursive = TRUE, showWarnings = FALSE)
  # write_tsv() (not fwrite directly): `error` holds conditionMessage(), which
  # is usually multi-line here, and a raw newline would split the row.
  write_tsv(out, file.path(opt$outdir, "batch_summary.tsv"))
  print(out)
  invisible(out)
}

cli_cmd_doctor <- function(args) {
  check_online <- "--check-online" %in% args
  cat("nanoamp version:", nanoamp_version(), "\n")
  cat("R version:", R.version.string, "\n")
  cat("Rscript:", file.path(R.home("bin"), "Rscript"), "\n")
  cat("platform:", nanoamp_platform(), "\n")
  dep <- nanoamp_dependence_dir()
  cat("dependence directory:", if (is.null(dep)) "NOT FOUND" else dep, "\n")
  # Hard dependencies first, then the optional ones that gate the R-native
  # backend and Mode B clustering.
  pkgs <- c("Biostrings", "IRanges", "Matrix", "Rsamtools",
            "data.table", "optparse", "jsonlite", "readxl", "DECIPHER", "pwalign")
  for (p in pkgs) cat(sprintf("  %-12s %s\n", p, requireNamespace(p, quietly = TRUE)))
  for (tool in c("minimap2", "samtools")) {
    path <- nanoamp_tool_path(tool, required = FALSE)
    if (is.null(path)) {
      note <- if (identical(tool, "samtools")) {
        "NOT FOUND (optional; Rsamtools is used by default)"
      } else {
        "NOT FOUND (expected at 03_dependence/<os>-<arch>/bin/, or use aligner = \"r\")"
      }
      cat(sprintf("  %-12s %s\n", tool, note))
    } else {
      cat(sprintf("  %-12s %s (%s)\n", tool, path, nanoamp_tool_version(tool, path)))
    }
  }
  # --- functional annotation prerequisites -------------------------------
  # The GUI reads these lines to decide whether the online route is usable and
  # where the cache lives; keep the "<key><spaces><value>" shape stable.
  curl_bin <- Sys.which("curl")
  cat(sprintf("  %-12s %s\n", "curl",
              if (nzchar(curl_bin)) curl_bin else
                "NOT FOUND (online annotation unavailable; the offline cds route still works)"))
  cat(sprintf("  %-12s %s\n", "cache-dir", annotation_cache_dir()))
  cat(sprintf("  %-12s %s\n", "cache-size", format(annotation_cache_size(), scientific = FALSE)))
  cfg_dir <- system.file("configs", package = "nanoamp")
  cat(sprintf("  %-12s %s\n", "configs",
              if (nzchar(cfg_dir) && dir.exists(cfg_dir)) cfg_dir else "NOT FOUND"))
  cat(sprintf("  %-12s %s\n", "annotation",
              if (requireNamespace("Biostrings", quietly = TRUE) &&
                  requireNamespace("jsonlite", quietly = TRUE)) "available" else
                "unavailable (Biostrings/jsonlite missing)"))
  # --check-online is what the GUI's "测试 Ensembl 连接" button runs: it answers
  # the one question a user has when the online route fails, without running an
  # analysis. Unreachable => non-zero exit, so it can be scripted too.
  if (check_online) {
    chk <- cli_online_check()
    if (isTRUE(chk$ok)) {
      cat(sprintf("  %-12s %s\n", "online",
                  sprintf("ok (Ensembl release %s)", chk$release)))
    } else {
      cat(sprintf("  %-12s FAILED: %s\n", "online",
                  paste(chk$problems, collapse = "; ")))
      stop("Online annotation is not usable from this machine.", call. = FALSE)
    }
  }
  invisible(TRUE)
}

# Is the online annotation route usable right now? Returns list(ok, release,
# problems) and never throws, so both the CLI and the GUI can report the reason.
cli_online_check <- function(timeout = 20L) {
  if (!requireNamespace("Biostrings", quietly = TRUE) ||
      !requireNamespace("jsonlite", quietly = TRUE)) {
    return(list(ok = FALSE, release = NA_character_,
                problems = "Biostrings/jsonlite missing (the offline cds route still works)"))
  }
  chk <- tryCatch(annotation_provider_check(timeout = timeout),
                  error = function(e) list(ok = FALSE, release = NA_character_,
                                           problems = conditionMessage(e)))
  if (!isTRUE(chk$ok)) {
    chk$problems <- c(chk$problems,
                      "offline route available: --annotate-config with \"route\": \"cds\"")
  }
  chk
}

# Cache inspection for the GUI and for scripts:
#   nanoamp cache                 path, size and file count
#   nanoamp cache --clear         empty it
cli_cache_options <- function() {
  list(
    optparse::make_option(c("--cache-dir"), type = "character", default = NULL,
                          help = "Cache directory [default: per-user cache]"),
    optparse::make_option(c("--clear"), action = "store_true", default = FALSE,
                          help = "Empty the cache and exit")
  )
}

cli_cmd_cache <- function(args) {
  options <- cli_cache_options()
  cli_check_flags(args, options)
  opt <- optparse::parse_args(
    optparse::OptionParser(option_list = options), args = args
  )
  cli_apply_cache_dir(opt)
  info <- annotation_cache_info()
  cat(sprintf("cache-dir   %s\n", info$dir))
  cat(sprintf("cache-size  %s\n", format(info$size, scientific = FALSE)))
  cat(sprintf("cache-files %d\n", info$files))
  if (isTRUE(opt$clear)) {
    d <- annotation_cache_clear()
    cat(sprintf("cleared     %s\n", d))
  }
  invisible(info)
}

#' nanoamp command line interface
#'
#' Run the nanoamp command line interface. This function is used by the
#' installed `nanoamp` executable and can also be called from R.
#'
#' @param args Character vector of command line arguments. Defaults to the
#'   arguments passed to `Rscript`.
#'
#' @return Invisibly returns the result of the selected command.
#' @export
nanoamp_cli <- function(args = commandArgs(trailingOnly = TRUE)) {
  if (length(args) >= 1 && args[1] == "--args") args <- args[-1]
  cmd <- if (length(args) >= 1 && !grepl("^--", args[1])) args[1] else "help"
  rest <- if (length(args) >= 1 && !grepl("^--", args[1])) args[-1] else args
  switch(
    cmd,
    call = cli_cmd_call(rest),
    batch = cli_cmd_batch(rest),
    doctor = cli_cmd_doctor(rest),
    cache = cli_cmd_cache(rest),
    help = cli_usage(),
    cli_usage()
  )
  invisible(NULL)
}

# Resolve the annotation config path for a CLI call.
#
# * --annotate-config gives the path directly; --transcript / --list-transcripts
#   are folded into a copy of that config so the user can override the
#   transcript without editing the file.
# * --list-transcripts with no config still needs a context, so a throwaway
#   genome-route config is written to a temporary file: the point of the flag is
#   to discover which transcripts exist before deciding anything.
# * Without --annotate-config the bundled examples are NOT used implicitly:
#   annotation stays opt-in, exactly as documented.
cli_annotation_config <- function(opt, outdir) {
  list_only <- isTRUE(opt$`list-transcripts`)
  cfg_path <- opt$`annotate-config`
  transcript <- opt$transcript

  if (is.null(cfg_path) || !nzchar(cfg_path)) {
    if (!list_only) return(NULL)
    tmp <- tempfile("nanoamp_annot_", fileext = ".json")
    write_json(
      list(name = "list-transcripts", route = "genome", genetic_code = "Standard"),
      tmp
    )
    cfg_path <- tmp
  } else if (!file.exists(cfg_path)) {
    stop(sprintf("Annotation config not found: %s", cfg_path), call. = FALSE)
  }

  if (is.null(transcript) || !nzchar(transcript)) return(cfg_path)
  cfg <- jsonlite::fromJSON(cfg_path, simplifyVector = FALSE)
  if (identical(tolower(transcript), "all")) {
    cfg$transcript_all <- TRUE
    cfg$transcript_id <- NULL
  } else {
    cfg$transcript_id <- transcript
    cfg$transcript_all <- FALSE
  }
  tmp <- tempfile("nanoamp_annot_", fileext = ".json")
  write_json(cfg, tmp)
  tmp
}
