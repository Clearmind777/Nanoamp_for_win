project_root_test_root <- function() {
  normalizePath(testthat::test_path("..", "..", "..", ".."), mustWork = FALSE)
}

test_that("cs tag 可解析为 SNV / 插入 / 缺失", {
  v <- cs_to_variants(":5*ac:3+ag:2-tt", ref_start = 10)
  expect_equal(nrow(v), 3)
  expect_equal(v$type, c("snv", "ins", "del"))
  expect_equal(v$pos, c(15L, 18L, 21L))
  expect_equal(v$ref, c("A", "", "TT"))
  expect_equal(v$alt, c("C", "AG", ""))
})

test_that("apply_variants 正确应用 SNV / 插入 / 缺失", {
  ref <- "ACGTACGT"
  expect_equal(
    apply_variants(ref, data.table::data.table(type = "snv", pos = 3L, ref = "G", alt = "T")),
    "ACTTACGT"
  )
  expect_equal(
    apply_variants(ref, data.table::data.table(type = "ins", pos = 3L, ref = "", alt = "AA")),
    "ACGAATACGT"
  )
  expect_equal(
    apply_variants(ref, data.table::data.table(type = "del", pos = 3L, ref = "GT", alt = "")),
    "ACACGT"
  )
})

test_that("signature 与 ops 可往返", {
  sig <- "snv|3|G|T;del|5|AC|"
  ops <- signature_to_ops(sig)
  expect_equal(nrow(ops), 2)
  expect_equal(ops$type, c("snv", "del"))
})

test_that("方案 C 能识别正链和反链精确匹配", {
  td <- tempfile("nanoamp_c_"); dir.create(td)
  ref <- "ACGTAGCTTAAG"
  seqs <- c(ref, reverse_complement(ref), "ACGTACGTACGA", ref)
  fq <- file.path(td, "reads.fastq")
  ref_fa <- file.path(td, "ref.fa")
  write_test_fastq(seqs, fq)
  write_test_ref(ref, ref_fa)
  res <- run_mode_c(fq, ref_fa, file.path(td, "out"), top_n = 5)
  expect_equal(res$qc$n_exact_forward, 2)
  expect_equal(res$qc$n_exact_reverse, 1)
  expect_equal(res$qc$n_exact_either, 3)
})

test_that("方案 A 能在合成数据中恢复参考与突变单倍型", {
  skip_if_not(
    !is.null(nanoamp_tool_path("minimap2", required = FALSE)),
    "minimap2 not available"
  )
  td <- tempfile("nanoamp_a_"); dir.create(td)
  ref <- make_random_seq(300, seed = 11)
  mut <- ref
  substr(mut, 100, 100) <- ifelse(substr(mut, 100, 100) == "A", "T", "A")
  seqs <- c(rep(ref, 6), rep(mut, 4))
  fq <- file.path(td, "reads.fastq")
  ref_fa <- file.path(td, "ref.fa")
  write_test_fastq(seqs, fq)
  write_test_ref(ref, ref_fa)
  res <- run_mode_a(
    fq, ref_fa, file.path(td, "out"),
    top_n = 5, min_reads = 2, min_freq = 0.2, min_identity = 0.9
  )
  expect_equal(nrow(res$haplotypes), 2)
  expect_true(any(res$haplotypes$is_reference))
  expect_true(any(grepl("100", res$haplotypes$variants)))
  expect_equal(sum(res$haplotypes$count), 10)
  expect_equal(sum(res$haplotypes$proportion), 1, tolerance = 1e-8)
})

test_that("方案 B 能对合成数据产生簇并计数", {
  skip_if_not(
    !is.null(nanoamp_tool_path("minimap2", required = FALSE)),
    "minimap2 not available"
  )
  td <- tempfile("nanoamp_b_"); dir.create(td)
  ref <- make_random_seq(300, seed = 22)
  mut <- ref
  substr(mut, 120, 120) <- ifelse(substr(mut, 120, 120) == "A", "T", "A")
  seqs <- c(rep(ref, 8), rep(mut, 5))
  fq <- file.path(td, "reads.fastq")
  ref_fa <- file.path(td, "ref.fa")
  write_test_fastq(seqs, fq)
  write_test_ref(ref, ref_fa)
  res <- run_mode_b(
    fq, ref_fa, file.path(td, "out"),
    top_n = 5, identity_cutoff = 0.95, min_cluster_reads = 2,
    min_identity = 0.9, consensus_method = "decipher", max_msa_seqs = 20
  )
  expect_true(nrow(res$haplotypes) >= 1)
  expect_equal(sum(res$haplotypes$count), 13)
  expect_true(all(nchar(res$haplotypes$consensus) > 0))
  if (requireNamespace("DECIPHER", quietly = TRUE)) {
    expect_true(grepl("^DECIPHER", res$qc$clustering_method))
    expect_equal(res$qc$consensus_method, "decipher")
  }
})

test_that("比对不受路径中的空格影响", {
  skip_if_not(
    !is.null(nanoamp_tool_path("minimap2", required = FALSE)),
    "minimap2 not available"
  )
  # align_reads() builds a minimap2 command line through system2(), which quotes
  # `command` but pastes `args` verbatim. normalizePath() expands an 8.3 short
  # path (C:\Users\JALENZ~1) into the long form (C:/Users/jalen zhong), so on
  # many machines R's own tempdir already contains a space: without shQuote()
  # the path was split into extra argv entries and minimap2 exited 1 with
  # "failed to open file 'C:\Users\jalen'". This test uses a path that contains
  # a space on purpose and must keep passing.
  td <- file.path(tempfile("nanoamp space "), "reads with space")
  dir.create(td, recursive = TRUE, showWarnings = FALSE)
  ref <- make_random_seq(300, seed = 33)
  fq <- file.path(td, "reads.fastq")
  ref_fa <- file.path(td, "ref.fa")
  write_test_fastq(rep(ref, 4), fq)
  write_test_ref(ref, ref_fa)

  expect_true(grepl(" ", normalizePath(td, winslash = "/")))

  res <- run_mode_a(
    fq, ref_fa, file.path(td, "out"),
    top_n = 5, min_reads = 2, min_freq = 0.2, min_identity = 0.9
  )
  expect_equal(nrow(res$haplotypes), 1)
  expect_true(res$haplotypes$is_reference[1])
  expect_equal(res$qc$n_reads_used, 4)
})

test_that("ln_test_data manifest 指向存在的软链接", {
  manifest_path <- file.path(project_root_test_root(), "01_data", "ln_test_data", "manifest.tsv")
  skip_if_not(file.exists(manifest_path), "ln_test_data 尚未生成")
  m <- data.table::fread(manifest_path, sep = "\t", header = TRUE)
  expect_true(all(c("link_path", "target_path") %in% names(m)))
  expect_false(any(is.na(m$link_path)))
  expect_true(all(file.exists(file.path(project_root_test_root(), m$link_path))))
})
