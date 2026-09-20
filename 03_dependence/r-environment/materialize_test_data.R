# Materialize 01_data/ln_test_data on platforms without symlink support.
#
# `prepare_test_data.R` creates real symlinks. On Windows, Git and R can only
# create symlinks when Developer Mode (or SeCreateSymbolicLinkPrivilege) is
# enabled. Without it:
#   * `git checkout` writes the link target as a tiny text file, and
#   * `file.symlink()` returns FALSE without creating anything,
# so every ln_test_data file becomes a ~100 byte text stub containing a path,
# and any analysis that reads them fails.
#
# This script repairs that state: for every row of manifest.tsv whose
# link_path is missing or is a stub, it copies the real target file instead.
# Real symlinks are left untouched, so running this on Linux is a no-op.
#
# Usage:
#   Rscript 03_dependence/r-environment/materialize_test_data.R

find_repo_root <- function(start = getwd()) {
  p <- normalizePath(start, mustWork = FALSE)
  repeat {
    if (dir.exists(file.path(p, "01_data")) &&
        dir.exists(file.path(p, "02_code"))) {
      return(p)
    }
    parent <- dirname(p)
    if (identical(parent, p)) break
    p <- parent
  }
  normalizePath(start, mustWork = FALSE)
}

root <- Sys.getenv("NANOAMP_REPO", unset = "")
if (!nzchar(root)) root <- find_repo_root()

manifest_path <- file.path(root, "01_data", "ln_test_data", "manifest.tsv")
if (!file.exists(manifest_path)) {
  stop("manifest not found: ", manifest_path,
       "\nRun 02_code/r/inst/scripts/prepare_test_data.R first.", call. = FALSE)
}

m <- utils::read.delim(manifest_path, stringsAsFactors = FALSE,
                       colClasses = "character")
cat("repo    :", root, "\n")
cat("manifest:", nrow(m), "rows\n\n")

target_of <- function(link) {
  normalizePath(file.path(root, link), mustWork = FALSE)
}

copied <- 0L
ok <- 0L
skipped_symlink <- 0L
missing <- character(0)

for (i in seq_len(nrow(m))) {
  link_abs <- target_of(m$link_path[i])
  target_abs <- target_of(m$target_path[i])

  if (!file.exists(target_abs)) {
    missing <- c(missing, m$target_path[i])
    next
  }

  if (nzchar(Sys.readlink(link_abs))) {
    skipped_symlink <- skipped_symlink + 1L   # genuine symlink: leave alone
    ok <- ok + 1L
    next
  }

  dir.create(dirname(link_abs), recursive = TRUE, showWarnings = FALSE)

  # A stub is any existing file that is not the real target content.
  stub <- file.exists(link_abs) &&
    !identical(tools::md5sum(link_abs)[[1]], tools::md5sum(target_abs)[[1]])

  if (stub || !file.exists(link_abs)) {
    if (stub) unlink(link_abs, force = TRUE)
    if (isTRUE(file.copy(target_abs, link_abs, overwrite = TRUE))) {
      copied <- copied + 1L
      ok <- ok + 1L
    } else {
      warning("copy failed: ", m$link_path[i], call. = FALSE)
    }
  } else {
    ok <- ok + 1L
  }
}

cat("materialized (copied) :", copied, "\n")
cat("left as real symlink  :", skipped_symlink, "\n")
cat("verified present      :", ok, "/", nrow(m), "\n")
if (length(missing)) {
  cat("MISSING TARGETS       :", length(missing), "\n")
  cat(paste0("  ", missing), sep = "\n")
  quit(status = 1)
}

# Final integrity check: every link_path must have the target's content.
bad <- character(0)
for (i in seq_len(nrow(m))) {
  link_abs <- target_of(m$link_path[i])
  target_abs <- target_of(m$target_path[i])
  if (!file.exists(link_abs)) { bad <- c(bad, m$link_path[i]); next }
  if (!identical(tools::md5sum(link_abs)[[1]], tools::md5sum(target_abs)[[1]])) {
    bad <- c(bad, m$link_path[i])
  }
}
if (length(bad)) {
  cat("\nCONTENT MISMATCH for", length(bad), "paths:\n")
  cat(paste0("  ", head(bad, 20)), sep = "\n")
  quit(status = 1)
}

cat("\nALL ln_test_data LINKS RESOLVE TO THE CORRECT CONTENT\n")
