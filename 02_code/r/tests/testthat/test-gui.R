test_that("GUI server runs a Mode C analysis", {
  skip_if_not_installed("shiny")
  repo_root <- normalizePath(testthat::test_path("..", "..", "..", ".."), mustWork = FALSE)
  reads <- file.path(repo_root, "01_data", "TSM20260826", "E4-3", "reads.fastq")
  ref <- file.path(repo_root, "01_data", "TSM20260826", "E4-3", "reference.self.fa")
  skip_if_not(file.exists(reads) && file.exists(ref), "E4-3 sample not available")

  outdir <- file.path(tempdir(), "nanoamp_gui_test")
  unlink(outdir, recursive = TRUE)

  suppressWarnings(
    shiny::testServer(nanoamp:::nanoamp_gui_server, {
      session$setInputs(
        reads = list(datapath = reads, name = "reads.fastq"),
        reference = list(datapath = ref, name = "reference.fa"),
        outdir = outdir, mode = "C", top_n = 5,
        min_reads = 3, min_freq = 0.02, min_identity = 0.9,
        identity_cutoff = 0.99, min_cluster_reads = 2,
        consensus_method = "decipher", threads = 2, keep_intermediates = FALSE
      )
      session$setInputs(run = 1)
      expect_match(output$status, "Analysis complete")
    })
  )

  expect_true(file.exists(file.path(outdir, "haplotypes.tsv")))
  expect_true(file.exists(file.path(outdir, "variants.tsv")))
  expect_true(file.exists(file.path(outdir, "qc.tsv")))
})
