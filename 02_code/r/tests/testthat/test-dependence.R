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
