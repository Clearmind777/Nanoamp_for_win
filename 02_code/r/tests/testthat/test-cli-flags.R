# CLI contract tests that need no network, no aligner and no analysis run.

test_that("abbreviated long flags are rejected with the real flag suggested", {
  opts <- nanoamp:::cli_call_options()
  # the real flags pass
  expect_silent(nanoamp:::cli_check_flags(
    c("--reads", "r.fastq", "--reference", "ref.fa", "--outdir", "out",
      "--annotate-config", "cfg.json", "--no-cache"), opts))
  # abbreviations are rejected, and the message names the implemented flag
  err <- tryCatch(nanoamp:::cli_check_flags(c("--annotate", "cfg.json"), opts),
                  error = function(e) conditionMessage(e))
  expect_match(err, "--annotate-config")
  expect_match(err, "Abbreviations are not accepted")
  # a legacy flag that is not a prefix of anything still gets an explanation
  err2 <- tryCatch(nanoamp:::cli_check_flags(c("--ensembl-release", "116"), opts),
                   error = function(e) conditionMessage(e))
  expect_match(err2, "run_manifest.json")
  # values that merely start with "--" are not mistaken for flags
  expect_silent(nanoamp:::cli_check_flags(
    c("--ref-label", "--weird-label-value"), opts))
})

test_that("the annotation flags exist on both call and batch", {
  wanted <- c("--annotate-config", "--transcript", "--list-transcripts",
              "--clear-cache", "--no-cache", "--cache-dir",
              "--annotation-proteins", "--annotation-detail", "--strict")
  expect_true(all(wanted %in% nanoamp:::cli_long_flags(nanoamp:::cli_call_options())))
  expect_true(all(wanted %in% nanoamp:::cli_long_flags(nanoamp:::cli_batch_options())))
})

test_that("--no-cache bypasses the cache instead of deleting it", {
  td <- withr::local_tempdir()
  withr::local_envvar(NANOAMP_CACHE_DIR = td, NANOAMP_NO_CACHE = NA)
  dir.create(file.path(td, "http"))
  writeLines("cached response", file.path(td, "http", "x.txt"))
  opt <- list(`no-cache` = TRUE, `cache-dir` = NULL)
  nanoamp:::cli_apply_no_cache(opt)
  expect_equal(Sys.getenv("NANOAMP_NO_CACHE"), "1")
  # the cached file is still there: --no-cache must not wipe a shared cache
  expect_true(file.exists(file.path(td, "http", "x.txt")))
  expect_false(nanoamp:::`.annotation_cache_enabled`())
  Sys.unsetenv("NANOAMP_NO_CACHE")
  expect_true(nanoamp:::`.annotation_cache_enabled`())
})

test_that("--cache-dir is exported to the annotation layer", {
  td <- withr::local_tempdir()
  withr::local_envvar(NANOAMP_CACHE_DIR = NA)
  nanoamp:::cli_apply_cache_dir(list(`cache-dir` = td))
  expect_equal(normalizePath(Sys.getenv("NANOAMP_CACHE_DIR"), mustWork = FALSE),
               normalizePath(td, mustWork = FALSE))
  expect_equal(normalizePath(nanoamp:::annotation_cache_dir(), mustWork = FALSE),
               normalizePath(td, mustWork = FALSE))
})

test_that("--list-transcripts without a config builds a genome-route config", {
  td <- withr::local_tempdir()
  opt <- list(`list-transcripts` = TRUE, `annotate-config` = NULL, transcript = NULL)
  path <- nanoamp:::cli_annotation_config(opt, td)
  expect_true(file.exists(path))
  cfg <- jsonlite::fromJSON(path)
  expect_equal(cfg$route, "genome")
})

test_that("a missing annotation config is reported clearly", {
  opt <- list(`list-transcripts` = FALSE, `annotate-config` = "does-not-exist.json",
              transcript = NULL)
  expect_error(nanoamp:::cli_annotation_config(opt, tempdir()),
               "Annotation config not found")
})

test_that("--transcript overwrites the config without editing the file", {
  td <- withr::local_tempdir()
  cfg <- file.path(td, "cfg.json")
  writeLines('{"name":"t","route":"genome","genetic_code":"Standard"}', cfg)
  opt <- list(`list-transcripts` = FALSE, `annotate-config` = cfg, transcript = "all")
  out <- nanoamp:::cli_annotation_config(opt, td)
  expect_false(identical(out, cfg))
  expect_true(jsonlite::fromJSON(out)$transcript_all)
  opt2 <- list(`list-transcripts` = FALSE, `annotate-config` = cfg,
               transcript = "ENST00000621650")
  out2 <- nanoamp:::cli_annotation_config(opt2, td)
  parsed <- jsonlite::fromJSON(out2)
  expect_equal(parsed$transcript_id, "ENST00000621650")
  expect_false(isTRUE(parsed$transcript_all))
})

# ---------------------------------------------------------------------------
# P0-7: structured status / error_class in run_manifest.json
# ---------------------------------------------------------------------------

test_that("errors are classified into the four documented classes", {
  expect_equal(nanoamp:::error_class_of(
    structure(class = c("nanoamp_network", "nanoamp_error", "error", "condition"),
              list(message = "x"))), "network")
  # base-R errors carry no class, so the message decides
  expect_equal(nanoamp:::error_class_of(
    simpleError("cannot open file 'nope.fastq': No such file or directory")), "input")
  expect_equal(nanoamp:::error_class_of(
    simpleError("Could not create the output directory: Z:\\x")), "environment")
  expect_equal(nanoamp:::error_class_of(
    simpleError("could not resolve host: rest.ensembl.org")), "network")
  # anything unrecognised must not be blamed on the user's input
  expect_equal(nanoamp:::error_class_of(simpleError("subscript out of bounds")),
               "internal")
  e <- tryCatch(nanoamp:::nanoamp_abort("bad config", class = "input"),
                error = function(e) e)
  expect_s3_class(e, "nanoamp_input")
  expect_equal(nanoamp:::error_class_of(e), "input")
})

test_that("a failed run still writes a readable run_manifest.json", {
  td <- withr::local_tempdir()
  out <- file.path(td, "out")
  expect_error(
    nanoamp:::run_haplotype_analysis(
      reads = file.path(td, "missing.fastq"),
      reference = file.path(td, "missing.fa"),
      outdir = out, mode = "A", aligner = "r"
    ),
    "missing|No such file|cannot"
  )
  manifest <- file.path(out, "run_manifest.json")
  expect_true(file.exists(manifest))
  info <- jsonlite::fromJSON(manifest)
  expect_equal(info$status, "failed")
  expect_equal(info$error_class, "input")
  expect_true(nzchar(info$error_message))
  expect_true(file.exists(file.path(out, "nanoamp.log")))
  expect_equal(normalizePath(info$log_path, mustWork = FALSE),
               normalizePath(file.path(out, "nanoamp.log"), mustWork = FALSE))
})

test_that("a completed run records status=done and its log file", {
  R <- paste(rep(c("ACGT", "TTGC", "GGCA"), length.out = 60), collapse = "")
  td <- withr::local_tempdir()
  fa <- file.path(td, "ref.fa")
  writeLines(c(">r", R), fa)
  reads <- file.path(td, "reads.fastq")
  writeLines(c("@r1", R, "+", strrep("I", nchar(R))), reads)
  out <- file.path(td, "out")
  nanoamp:::run_haplotype_analysis(reads = reads, reference = fa, outdir = out,
                                   mode = "C", aligner = "r")
  info <- jsonlite::fromJSON(file.path(out, "run_manifest.json"))
  expect_equal(info$status, "done")
  expect_null(info$error_class)
  expect_true(file.exists(file.path(out, "nanoamp.log")))
})

test_that("--strict turns a skipped annotation into a failure, and is off by default", {
  R <- paste(rep(c("ACGT", "TTGC", "GGCA"), length.out = 60), collapse = "")
  td <- withr::local_tempdir()
  fa <- file.path(td, "ref.fa"); writeLines(c(">r", R), fa)
  reads <- file.path(td, "reads.fastq")
  writeLines(c("@r1", R, "+", strrep("I", nchar(R))), reads)
  # A CDS whose length is not a multiple of three: the transcript is skipped.
  nanoamp:::write_json(list(
    name = "bad", route = "cds",
    cds = list(start = 1, end = nchar(R) - 1L, strand = "+", frame = 0L,
               boundaries = "inclusive"),
    genetic_code = "Standard"
  ), file.path(td, "bad.json"))

  lenient <- file.path(td, "lenient")
  res <- nanoamp:::run_haplotype_analysis(
    reads = reads, reference = fa, outdir = lenient, mode = "A", aligner = "r",
    annotation = file.path(td, "bad.json")
  )
  expect_null(res$strict_failure)
  expect_equal(jsonlite::fromJSON(file.path(lenient, "run_manifest.json"))$status, "done")
  qc <- data.table::fread(file.path(lenient, "qc.tsv"))
  expect_equal(qc[metric == "annotation_available"]$value, "FALSE")
  expect_match(qc[metric == "annotation_skip_reason"]$value, "multiple of 3")

  strict <- file.path(td, "strict")
  res2 <- nanoamp:::run_haplotype_analysis(
    reads = reads, reference = fa, outdir = strict, mode = "A", aligner = "r",
    annotation = file.path(td, "bad.json"), strict = TRUE
  )
  expect_true(nzchar(res2$strict_failure))
  info <- jsonlite::fromJSON(file.path(strict, "run_manifest.json"))
  expect_equal(info$status, "failed")
  expect_equal(info$error_class, "input")
  expect_match(info$error_message, "multiple of 3")
  # the CLI turns that into a non-zero exit instead of a silent success
  expect_error(nanoamp:::cli_strict_check(res2), "--strict")
  expect_silent(nanoamp:::cli_strict_check(res))
})
