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

test_that("01_data 的每个样本目录都自带规范化文件与 meta.tsv", {
  data_root <- file.path(project_root_test_root(), "01_data")
  # 在 R CMD check 里测试跑在 <pkg>.Rcheck/tests 下，仓库的 01_data 不在
  # 相对位置上（同时也避免把 40 MB 数据打进 check 目录），此时跳过。
  skip_if_not(dir.exists(data_root), "01_data not available (e.g. under R CMD check)")
  meta_files <- list.files(data_root, pattern = "^meta.tsv$", recursive = TRUE,
                           full.names = TRUE)
  expect_gt(length(meta_files), 0)

  check <- vapply(meta_files, function(path) {
    sample_dir <- dirname(path)
    m <- data.table::fread(path, sep = "\t", header = TRUE, colClasses = "character")
    if (!all(c("dataset", "sample", "role", "file", "source_file") %in% names(m))) {
      return(FALSE)
    }
    # 规范化的文件必须真的在样本目录里，且每个样本都能直接拿去分析
    all(file.exists(file.path(sample_dir, m$file))) &&
      file.exists(file.path(sample_dir, "reads.fastq")) &&
      file.exists(file.path(sample_dir, "reference.self.fa"))
  }, logical(1))
  expect_true(all(check))
  # 32 个样本来自 3 个数据集（SD 批次不属于链接层，没有 meta.tsv）
  expect_equal(length(unique(basename(dirname(dirname(meta_files))))), 3)
})
