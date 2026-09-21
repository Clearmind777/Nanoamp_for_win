# ---------------------------------------------------------------------------
# RStudio 交互版：修改 CONFIG 后直接运行整个脚本
# 打开 02_code/r/nanoamp.Rproj；脚本会自动向上寻找项目根目录
# ---------------------------------------------------------------------------

find_project_root <- function(start = getwd()) {
  p <- normalizePath(start, mustWork = FALSE)
  repeat {
    if (dir.exists(file.path(p, "01_data")) || dir.exists(file.path(p, ".git"))) return(p)
    parent <- dirname(p)
    if (identical(parent, p)) break
    p <- parent
  }
  normalizePath(start, mustWork = FALSE)
}

project_root <- find_project_root()

CONFIG <- list(
  reads = file.path(project_root, "01_data/TSM20260826/E4-3/reads.fastq"),
  reference = file.path(project_root, "01_data/TSM20260826/E4-3/reference.self.fa"),
  mode = "A",
  outdir = file.path(project_root, "tmp/test_results/r/rstudio_demo/mode_A_self"),
  top_n = 20L,
  min_reads = 3L,
  min_freq = 0.02,
  min_identity = 0.90,
  identity_cutoff = 0.99,
  min_cluster_reads = 2L,
  consensus_method = "decipher",
  threads = 4L
)

if (!requireNamespace("nanoamp", quietly = TRUE)) {
  stop("The nanoamp R package is not installed. Run: R CMD INSTALL 02_code/r",
       call. = FALSE)
}
suppressPackageStartupMessages(library(nanoamp))

if (!file.exists(CONFIG$reads)) {
  stop(paste0(
    "找不到输入文件: ", CONFIG$reads,
    "\n01_data/<dataset>/<sample>/ 里应当直接有 reads.fastq 与 reference.self.fa",
    "（原文件名见该样本目录的 meta.tsv）"
  ), call. = FALSE)
}

res <- run_haplotype_analysis(
  reads = CONFIG$reads,
  reference = CONFIG$reference,
  outdir = CONFIG$outdir,
  mode = CONFIG$mode,
  top_n = CONFIG$top_n,
  min_reads = CONFIG$min_reads,
  min_freq = CONFIG$min_freq,
  min_identity = CONFIG$min_identity,
  identity_cutoff = CONFIG$identity_cutoff,
  min_cluster_reads = CONFIG$min_cluster_reads,
  consensus_method = CONFIG$consensus_method,
  threads = CONFIG$threads
)

cat("\n=== 运行完成 ===\n")
cat("输出目录:", normalizePath(CONFIG$outdir, mustWork = FALSE), "\n\n")
cat("QC:\n"); print(res$qc)
cat("\n单倍型（前 10 条）:\n")
print(utils::head(res$haplotypes, 10))
