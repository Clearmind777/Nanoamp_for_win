#!/usr/bin/env Rscript
# ---------------------------------------------------------------------------
# 基于 ln_test_data 的功能测试：三种模式 × self/wt 参考
# 结果写入 tmp/test_results/r/test_run_1/
# ---------------------------------------------------------------------------

suppressPackageStartupMessages({
  library(data.table)
  library(Biostrings)
  library(Rsamtools)
  library(ShortRead)
  library(optparse)
  library(nanoamp)
})

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

script_arg <- grep("^--file=", commandArgs(FALSE), value = TRUE)
script_path <- if (length(script_arg)) sub("^--file=", "", script_arg[1]) else NA_character_
start_dir <- if (!is.na(script_path)) dirname(script_path) else getwd()
project_root <- find_project_root(start_dir)

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) y else x
}

opt <- optparse::parse_args(optparse::OptionParser(option_list = list(
  make_option(c("--outdir"), type = "character", default = "tmp/test_results/r/test_run_1"),
  make_option(c("--modes"), type = "character", default = "A,B,C"),
  make_option(c("--datasets"), type = "character", default = "TSM20260826,ZNF8,nano_seq"),
  make_option(c("--samples"), type = "character", default = NULL,
              help = "可选，逗号分隔的样本名过滤器"),
  make_option(c("--top-n"), type = "integer", default = 20),
  make_option(c("--threads"), type = "integer", default = 4),
  make_option(c("--min-freq"), type = "double", default = 0.02),
  make_option(c("--identity-cutoff"), type = "double", default = 0.99)
)))

ln_root <- file.path(project_root, "01_data", "ln_test_data")
manifest_path <- file.path(ln_root, "manifest.tsv")
if (!file.exists(manifest_path)) {
  stop("请先运行 02_code/r/inst/scripts/prepare_test_data.R", call. = FALSE)
}
manifest <- data.table::fread(manifest_path, sep = "\t", header = TRUE)

modes <- strsplit(opt$modes, ",", fixed = TRUE)[[1]]
datasets <- strsplit(opt$datasets, ",", fixed = TRUE)[[1]]
sample_filter <- if (is.null(opt$samples)) NULL else strsplit(opt$samples, ",", fixed = TRUE)[[1]]

targets <- unique(manifest[dataset %in% datasets, .(dataset, sample)])
if (!is.null(sample_filter)) targets <- targets[sample %in% sample_filter]
data.table::setorder(targets, dataset, sample)

out_root <- file.path(project_root, opt$outdir)
dir.create(out_root, recursive = TRUE, showWarnings = FALSE)

get_role <- function(dataset_name, sample_name, role_name, cluster_num = NULL) {
  q <- manifest[dataset == dataset_name & sample == sample_name & role == role_name]
  if (!is.null(cluster_num)) q <- q[cluster == cluster_num]
  if (nrow(q) == 0) return(NULL)
  file.path(project_root, q$link_path[1])
}

read_top1 <- function(haplo_path) {
  if (!file.exists(haplo_path)) return(list(proportion = NA_real_, variants = NA_character_))
  h <- tryCatch(data.table::fread(haplo_path, sep = "\t", header = TRUE), error = function(e) NULL)
  if (is.null(h) || nrow(h) == 0) return(list(proportion = NA_real_, variants = NA_character_))
  list(
    proportion = if ("proportion" %in% names(h)) h$proportion[1] else NA_real_,
    variants = if ("variants" %in% names(h)) h$variants[1] else NA_character_
  )
}

normalize_allele <- function(x) {
  x <- as.character(x)
  x[is.na(x)] <- ""
  x <- toupper(x)
  x[x == "-"] <- ""
  x
}

classify_variant <- function(ref, alt) {
  ifelse(nchar(ref) == 1 & nchar(alt) == 1, "snv",
         ifelse(nchar(ref) > 0 & !nzchar(alt), "del", "ins"))
}

add_variant_coords <- function(dt) {
  dt <- dt[!is.na(pos)]
  dt[, type := classify_variant(ref, alt)]
  dt[, istart := pos]
  dt[, iend := ifelse(type == "del", pos + nchar(ref) - 1L, pos)]
  unique(dt[, .(pos, ref, alt, type, istart, iend)])
}

read_our_variants <- function(path) {
  if (!file.exists(path)) return(NULL)
  v <- tryCatch(data.table::fread(path, sep = "\t", header = TRUE), error = function(e) NULL)
  if (is.null(v) || nrow(v) == 0) return(NULL)
  if ("Pos" %in% names(v)) {
    out <- data.table::data.table(
      pos = suppressWarnings(as.integer(v$Pos)),
      ref = normalize_allele(v$Ref),
      alt = normalize_allele(v$Alt)
    )
  } else if ("pos" %in% names(v)) {
    out <- data.table::data.table(
      pos = suppressWarnings(as.integer(v$pos)),
      ref = normalize_allele(v$ref),
      alt = normalize_allele(v$alt)
    )
  } else {
    return(NULL)
  }
  add_variant_coords(out)
}

read_company_variant_dt <- function(path, min_freq = 5) {
  cv <- nanoamp:::read_company_variants(path)
  if (is.null(cv) || nrow(cv) == 0) return(NULL)
  cv <- cv[!is.na(company_pos)]
  if (any(!is.na(cv$company_freq))) cv <- cv[is.na(company_freq) | company_freq >= min_freq]
  if (nrow(cv) == 0) return(NULL)
  add_variant_coords(data.table::data.table(
    pos = cv$company_pos,
    ref = normalize_allele(cv$company_ref),
    alt = normalize_allele(cv$company_alt)
  ))
}

compare_variant_sets <- function(our, comp) {
  if (is.null(comp) || nrow(comp) == 0) {
    return(list(n_company = 0L, n_overlap = 0L, desc = ""))
  }
  if (is.null(our)) our <- data.table::data.table(
    pos = integer(0), ref = character(0), alt = character(0),
    type = character(0), istart = integer(0), iend = integer(0)
  )
  comp_snv <- comp[type == "snv"]
  comp_ind <- comp[type != "snv"]
  our_snv <- our[type == "snv"]
  our_ind <- our[type != "snv"]
  snv_key <- function(x) if (nrow(x) == 0) character(0) else paste(x$pos, x$alt, sep = "|")
  snv_hit <- snv_key(comp_snv) %in% snv_key(our_snv)
  indel_hit <- if (nrow(comp_ind) == 0) logical(0) else vapply(seq_len(nrow(comp_ind)), function(i) {
    any(our_ind$istart - 1L <= comp_ind$pos[i] & our_ind$iend + 1L >= comp_ind$pos[i])
  }, logical(1))
  desc_parts <- c(
    if (any(snv_hit)) paste0("SNV:", paste(comp_snv$pos[snv_hit], collapse = ",")) else NULL,
    if (any(indel_hit)) paste0("Indel:", paste(comp_ind$pos[indel_hit], collapse = ",")) else NULL
  )
  list(
    n_company = nrow(comp),
    n_overlap = sum(snv_hit) + sum(indel_hit),
    desc = paste(desc_parts, collapse = ";")
  )
}

read_qc <- function(path) {
  if (!file.exists(path)) return(list())
  q <- tryCatch(data.table::fread(path, sep = "\t", header = TRUE), error = function(e) NULL)
  if (is.null(q)) return(list())
  stats::setNames(as.list(q$value), q$metric)
}

runs <- list()
comparison <- list()
k <- 0L
for (i in seq_len(nrow(targets))) {
  ds <- targets$dataset[i]; sp <- targets$sample[i]
  reads <- get_role(ds, sp, "reads")
  refs <- list(self = get_role(ds, sp, "reference.self"),
               wt = get_role(ds, sp, "reference.wt"))
  refs <- refs[!vapply(refs, is.null, logical(1))]
  for (mode in modes) {
    for (ref_label in names(refs)) {
      k <- k + 1L
      run_dir <- file.path(out_root, ds, sp, paste0("mode_", mode), ref_label)
      dir.create(run_dir, recursive = TRUE, showWarnings = FALSE)
      t0 <- Sys.time()
      status <- "ok"; err <- ""
      res <- tryCatch({
        run_haplotype_analysis(
          reads = reads, reference = refs[[ref_label]], outdir = run_dir,
          mode = mode, top_n = opt$`top-n`, threads = opt$threads,
          min_freq = opt$`min-freq`, identity_cutoff = opt$`identity-cutoff`,
          ref_label = ref_label
        )
        TRUE
      }, error = function(e) {
        status <<- "error"; err <<- conditionMessage(e); FALSE
      })
      elapsed <- round(as.numeric(difftime(Sys.time(), t0, units = "secs")), 2)
      top1 <- read_top1(file.path(run_dir, "haplotypes.tsv"))
      qc <- read_qc(file.path(run_dir, "qc.tsv"))
      our_dt <- read_our_variants(file.path(run_dir, "variants.tsv"))
      comp_dt <- NULL
      if (ref_label == "self") {
        comp_path <- get_role(ds, sp, "variants", cluster_num = 1L)
        if (!is.null(comp_path)) comp_dt <- read_company_variant_dt(comp_path, min_freq = 5)
      }
      cmp <- compare_variant_sets(our_dt, comp_dt)
      runs[[k]] <- data.table::data.table(
        dataset = ds, sample = sp, mode = mode, ref_label = ref_label,
        status = status, elapsed_sec = elapsed, error = err,
        run_dir = sub(paste0("^", project_root, "/?"), "", run_dir)
      )
      comparison[[k]] <- data.table::data.table(
        dataset = ds, sample = sp, mode = mode, ref_label = ref_label,
        status = status,
        n_reads_total = qc$n_reads_total %||% NA,
        n_reads_used = qc$n_reads_used %||% qc$n_reads_total %||% NA,
        mapping_rate = qc$mapping_rate %||% NA,
        mean_identity = qc$mean_identity %||% NA,
        top1_proportion = top1$proportion,
        top1_variants = top1$variants,
        n_our_variants = if (is.null(our_dt)) 0L else nrow(our_dt),
        n_company_variants_ge5 = cmp$n_company,
        n_overlap = cmp$n_overlap,
        overlap_keys = cmp$desc,
        error = err
      )
      nanoamp:::log_info(sprintf("完成 %s/%s mode=%s ref=%s status=%s %.1fs",
                                 ds, sp, mode, ref_label, status, elapsed))
    }
  }
}

run_index <- data.table::rbindlist(runs, use.names = TRUE, fill = TRUE)
comp <- data.table::rbindlist(comparison, use.names = TRUE, fill = TRUE)
comp <- merge(
  comp,
  run_index[, .(dataset, sample, mode, ref_label, elapsed_sec)],
  by = c("dataset", "sample", "mode", "ref_label"), all.x = TRUE
)
data.table::fwrite(run_index, file.path(out_root, "run_index.tsv"), sep = "\t", na = "")
data.table::fwrite(comp, file.path(out_root, "comparison.tsv"), sep = "\t", na = "")

summary_mode <- comp[, .(
  n_runs = .N,
  n_ok = sum(status == "ok"),
  n_error = sum(status == "error"),
  mean_top1_proportion = round(mean(top1_proportion, na.rm = TRUE), 4),
  mean_overlap_rate = round(mean(ifelse(n_company_variants_ge5 > 0,
                                        n_overlap / n_company_variants_ge5, NA_real_), na.rm = TRUE), 4),
  mean_elapsed_sec = round(mean(elapsed_sec, na.rm = TRUE), 2)
), by = mode]
data.table::fwrite(summary_mode, file.path(out_root, "summary_by_mode.tsv"), sep = "\t", na = "")

cat("\n功能测试完成\n")
print(summary_mode)
