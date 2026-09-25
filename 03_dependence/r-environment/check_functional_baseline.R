# Compare a functional-regression run against the archived baseline.
#
# The baseline is a small, committed snapshot of a known-good run over the real
# datasets in 01_data/ (see 03_dependence/baselines/functional/README.md). This
# script is what `make functional-test` uses to turn "the regression ran" into
# "the regression produced the same answer as before".
#
# Usage:
#   Rscript 03_dependence/r-environment/check_functional_baseline.R \
#     --current tmp/test_results/r/test_run_win
#   Rscript 03_dependence/r-environment/check_functional_baseline.R \
#     --current tmp/test_results/r/test_run_win --write-baseline
#
# Exit status: 0 = identical (within tolerance), 1 = differences, 2 = usage error.

suppressPackageStartupMessages(library(data.table))

# Columns compared numerically (floating point) and exactly (everything else).
.identity_cols <- c("status", "top1_variants", "n_reads_total", "n_reads_used",
                    "n_our_variants", "n_company_variants_ge5", "n_overlap",
                    "overlap_keys")
.numeric_cols <- c("mapping_rate", "mean_identity", "top1_proportion")
.keys <- c("dataset", "sample", "mode", "ref_label")

find_repo_root <- function(start = getwd()) {
  p <- normalizePath(start, mustWork = FALSE)
  repeat {
    if (dir.exists(file.path(p, "01_data")) && dir.exists(file.path(p, "02_code"))) {
      return(p)
    }
    parent <- dirname(p)
    if (identical(parent, p)) break
    p <- parent
  }
  normalizePath(start, mustWork = FALSE)
}

root <- find_repo_root()
baseline_dir <- file.path(root, "03_dependence", "baselines", "functional")

args <- commandArgs(trailingOnly = TRUE)
get_arg <- function(name, default = NULL) {
  hit <- grep(paste0("^--", name, "="), args, value = TRUE)
  if (length(hit) > 0) return(sub(paste0("^--", name, "="), "", hit[1]))
  pos <- match(paste0("--", name), args)
  if (!is.na(pos) && length(args) > pos) return(args[pos + 1L])
  default
}
current <- get_arg("current", "tmp/test_results/r/test_run_win")
tolerance <- as.numeric(get_arg("tolerance", "1e-6"))
write_baseline <- "--write-baseline" %in% args

read_table <- function(dir, file, what) {
  # `dir` is normally repository-relative; an absolute path is accepted too so
  # that two arbitrary runs can be compared without copying them around.
  abs_dir <- if (grepl("^([A-Za-z]:[\\\\/]|[\\\\/])", dir)) dir else file.path(root, dir)
  path <- file.path(abs_dir, file)
  if (!file.exists(path)) {
    stop(sprintf("%s table not found: %s", what, path), call. = FALSE)
  }
  data.table::fread(path, sep = "\t", header = TRUE, na.strings = c("", "NA"),
                    colClasses = "character")
}

if (write_baseline) {
  dir.create(baseline_dir, recursive = TRUE, showWarnings = FALSE)
  for (f in c("comparison.tsv", "summary_by_mode.tsv", "run_index.tsv")) {
    src <- file.path(root, current, f)
    if (!file.exists(src)) stop(sprintf("cannot archive %s: not found", src), call. = FALSE)
    file.copy(src, file.path(baseline_dir, f), overwrite = TRUE)
  }
  cat("Baseline updated from", current, "->", baseline_dir, "\n")
  cat("Review the diff under 03_dependence/baselines/functional/ and commit it.\n")
  quit(status = 0)
}

base <- read_table(baseline_dir, "comparison.tsv", "baseline comparison")
cur <- read_table(current, "comparison.tsv", "current comparison")

needed <- c(.keys, .identity_cols, .numeric_cols)
for (nm in c("baseline", "current")) {
  tab <- if (nm == "baseline") base else cur
  absent <- setdiff(needed, names(tab))
  if (length(absent) > 0) {
    stop(sprintf("%s comparison.tsv is missing column(s): %s",
                 nm, paste(absent, collapse = ", ")), call. = FALSE)
  }
}

missing <- base[!cur, on = .keys]
extra <- cur[!base, on = .keys]
problems <- character(0)
if (nrow(missing) > 0) {
  problems <- c(problems, sprintf("%d run(s) present in the baseline are missing from this run",
                                  nrow(missing)))
}
if (nrow(extra) > 0) {
  problems <- c(problems, sprintf("%d run(s) are new in this run", nrow(extra)))
}

merged <- merge(
  base[, c(.keys, .identity_cols, .numeric_cols), with = FALSE],
  cur[, c(.keys, .identity_cols, .numeric_cols), with = FALSE],
  by = .keys, suffixes = c(".base", ".cur"), all = FALSE
)

report <- list()
for (i in seq_len(nrow(merged))) {
  key <- merged[i, c(.keys), with = FALSE]
  for (col in .identity_cols) {
    b <- merged[[paste0(col, ".base")]][i]
    c <- merged[[paste0(col, ".cur")]][i]
    same <- (is.na(b) && is.na(c)) || identical(as.character(b), as.character(c))
    if (!same) {
      report[[length(report) + 1L]] <- data.table::data.table(
        dataset = key$dataset, sample = key$sample, mode = key$mode,
        ref_label = key$ref_label, column = col,
        baseline = as.character(b), current = as.character(c)
      )
    }
  }
  for (col in .numeric_cols) {
    b <- suppressWarnings(as.numeric(merged[[paste0(col, ".base")]][i]))
    c <- suppressWarnings(as.numeric(merged[[paste0(col, ".cur")]][i]))
    same <- (is.na(b) && is.na(c)) || (!is.na(b) && !is.na(c) && abs(b - c) <= tolerance)
    if (!same) {
      report[[length(report) + 1L]] <- data.table::data.table(
        dataset = key$dataset, sample = key$sample, mode = key$mode,
        ref_label = key$ref_label, column = col,
        baseline = as.character(b), current = as.character(c)
      )
    }
  }
}

cat(sprintf("baseline runs : %d\n", nrow(base)))
cat(sprintf("current runs  : %d\n", nrow(cur)))
cat(sprintf("compared runs : %d\n", nrow(merged)))

# A run that used to be ok and is now an error is the most important change, so
# it is reported first and is never tolerated.
worse <- merged[status.base == "ok" & status.cur != "ok"]
if (nrow(worse) > 0) {
  problems <- c(problems, sprintf("%d run(s) regressed from ok to %s",
                                  nrow(worse), paste(unique(worse$status.cur), collapse = "/")))
}

if (length(report) == 0) {
  if (length(problems) > 0) {
    cat("\n", paste(problems, collapse = "\n"), "\n", sep = "")
    quit(status = 1)
  }
  cat("\nFUNCTIONAL BASELINE MATCHED\n")
  quit(status = 0)
}

diffs <- data.table::rbindlist(report)
cat("\n=== differences vs baseline ===\n")
print(diffs)
if (length(problems) > 0) {
  cat("\n", paste(problems, collapse = "\n"), "\n", sep = "")
}
cat(sprintf("\n%d difference(s) in %d run(s)\n", nrow(diffs), uniqueN(diffs, by = .keys)))
cat("Inspect the runs above; if the change is intended, refresh the baseline with:\n")
cat("  Rscript 03_dependence/r-environment/check_functional_baseline.R \\\n")
cat("    --current ", current, " --write-baseline\n", sep = "")
quit(status = 1)
