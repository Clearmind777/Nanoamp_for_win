test_that("tool resolver reports a usable platform", {
  expect_match(nanoamp_platform(), "^(linux|windows|macos)-")
})

test_that("tool resolver can find minimap2 when available", {
  path <- nanoamp_tool_path("minimap2", required = FALSE)
  if (!is.null(path)) {
    expect_true(file.exists(path))
  } else {
    succeed("minimap2 is not available on this platform")
  }
})

test_that("R-native aligner runs on a small synthetic dataset", {
  skip_if_not_installed("Biostrings")
  td <- tempfile("nanoamp_r_aligner_")
  dir.create(td)
  ref <- make_random_seq(300, seed = 42)
  mut <- ref
  substr(mut, 150, 150) <- ifelse(substr(mut, 150, 150) == "A", "T", "A")
  seqs <- c(rep(ref, 6), rep(mut, 4))
  fq <- file.path(td, "reads.fastq")
  ref_fa <- file.path(td, "ref.fa")
  write_test_fastq(seqs, fq)
  write_test_ref(ref, ref_fa)

  res <- run_mode_a(
    fq, ref_fa, file.path(td, "out"),
    top_n = 5, min_reads = 2, min_freq = 0.2,
    min_identity = 0.8, aligner = "r"
  )
  expect_true(nrow(res$haplotypes) >= 1)
  expect_equal(sum(res$haplotypes$count), 10)
})

test_that("the R aligner reports the coverage a read really has (L13)", {
  skip_if_not_installed("Biostrings")
  # The backend used to claim every read spans the whole reference, so a read
  # covering only half the amplicon passed --min-ref-coverage 0.99 and was
  # counted as the reference haplotype.
  ref <- make_random_seq(200, seed = 3)
  half <- substr(ref, 1, 100)
  td <- tempfile("nanoamp_r_coverage_"); dir.create(td)
  fa <- file.path(td, "ref.fa"); write_test_ref(ref, fa)
  reads <- file.path(td, "reads.fastq")
  write_test_fastq(rep(half, 5), reads)

  prep <- nanoamp:::prepare_alignment_data(reads, fa, file.path(td, "prep"),
                                           aligner = "r", threads = 1L)
  aln <- prep$aln
  expect_equal(nrow(aln), 5L)
  expect_true(all(aln$ref_span == 100L))
  expect_true(all(abs(aln$ref_cov - 0.5) < 1e-9))
  expect_equal(aln$ref_end, rep(100L, 5))

  # ... and the coverage filter therefore rejects them at the default threshold.
  expect_error(
    run_mode_a(reads, fa, file.path(td, "out_strict"), aligner = "r"),
    "no reads left after filtering"
  )
  # With a threshold that allows half coverage the run proceeds and reports it.
  res <- run_mode_a(reads, fa, file.path(td, "out_lenient"), aligner = "r",
                    min_ref_coverage = 0.4, min_identity = 0.8)
  expect_equal(res$qc$n_reads_used, 5L)
  expect_equal(res$qc$mean_coverage, 2.5)          # 5 reads x 100 bp / 200 bp

  # A full-length read still counts as full coverage.
  full_reads <- file.path(td, "full.fastq")
  write_test_fastq(rep(ref, 3), full_reads)
  prep2 <- nanoamp:::prepare_alignment_data(full_reads, fa, file.path(td, "prep2"),
                                            aligner = "r", threads = 1L)
  expect_true(all(prep2$aln$ref_span == 200L))
  expect_true(all(prep2$aln$ref_cov == 1))
})

test_that("Mode B clustering is reproducible and does not disturb the caller's RNG", {
  skip_if_not_installed("DECIPHER")
  # DECIPHER::Clusterize is stochastic: with identical input it returned
  # different cluster sizes on consecutive calls (measured 38/38/35 for the same
  # reads, and the same happens for the synthetic fixture below), so every
  # Mode B result used to be unreproducible and functional-regression baselines
  # could not be compared.
  template <- make_random_seq(1000, seed = 7)
  b <- strsplit(template, "")[[1]]
  set.seed(3)
  seqs <- c(
    rep(paste(b[1:1000], collapse = ""), 200),
    vapply(seq_len(300), function(i) {
      n <- sample(500:1000, 1)
      start <- sample(1:(length(b) - n + 1), 1)
      x <- b[start:(start + n - 1)]
      for (j in sample(seq_along(x), sample(8:20, 1))) {
        x[j] <- sample(setdiff(c("A", "C", "G", "T"), x[j]), 1)
      }
      paste(x, collapse = "")
    }, character(1))
  )

  set.seed(1)
  a1 <- nanoamp:::cluster_sequences(seqs, identity_cutoff = 0.99, threads = 1L)
  set.seed(999)
  a2 <- nanoamp:::cluster_sequences(seqs, identity_cutoff = 0.99, threads = 1L)
  # Same clusters no matter what the caller's RNG stream was doing.
  expect_equal(a1$cluster, a2$cluster)
  expect_gt(length(unique(a1$cluster)), 1L)

  # The package must not reset the session's random stream.
  set.seed(5)
  before <- .Random.seed
  nanoamp:::cluster_sequences(seqs, identity_cutoff = 0.99, threads = 1L)
  expect_identical(.Random.seed, before)
})
