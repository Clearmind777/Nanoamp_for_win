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
              "--annotation-proteins", "--annotation-detail")
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
