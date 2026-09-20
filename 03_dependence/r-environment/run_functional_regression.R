# Wrapper around the package's functional regression script.
#
# The package script (02_code/r/inst/scripts/run_functional_tests.R) calls
# library() on its dependencies directly, so it needs the dedicated library
# on .libPaths() *before* it starts. This wrapper takes care of that and
# forwards every argument.
#
# Usage:
#   Rscript 03_dependence/r-environment/run_functional_regression.R \
#     --outdir tmp/test_results/r/test_run_win --modes A,B,C --threads 4
#
# Environment variables:
#   NANOAMP_R_LIB   library directory (default: D:/tools/R/lib)

LIB <- Sys.getenv("NANOAMP_R_LIB", unset = "D:/tools/R/lib")
if (dir.exists(LIB)) .libPaths(c(LIB, .libPaths()))

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

root <- find_repo_root()
script <- file.path(root, "02_code", "r", "inst", "scripts",
                    "run_functional_tests.R")
if (!file.exists(script)) stop("functional test script not found: ", script)

args <- commandArgs(trailingOnly = TRUE)
cat("repo    :", root, "\n")
cat("library :", paste(.libPaths(), collapse = " | "), "\n")
cat("script  :", script, "\n")
cat("args    :", paste(args, collapse = " "), "\n\n")

# The package script calls library() on its dependencies directly, so the
# dedicated library must be visible to the child process. --vanilla would skip
# Rprofile.site and hide it, so pass the library through R_LIBS instead and
# launch with --no-save --no-restore.
old <- Sys.getenv("R_LIBS", unset = NA)
Sys.setenv(R_LIBS = paste(.libPaths(), collapse = .Platform$path.sep))
on.exit(if (is.na(old)) Sys.unsetenv("R_LIBS") else Sys.setenv(R_LIBS = old), add = TRUE)

status <- system2(
  file.path(R.home("bin"), "Rscript"),
  c("--no-save", "--no-restore", shQuote(script), args)
)
quit(status = status)
