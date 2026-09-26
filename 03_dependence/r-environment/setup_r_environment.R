# nanoamp R dependency setup for Windows (no conda, no WSL)
#
# Installs every R dependency of the nanoamp package into a dedicated,
# repository-independent library so the git working tree stays clean.
#
# Usage:
#   Rscript 03_dependence/r-environment/setup_r_environment.R
#
# Environment variables:
#   NANOAMP_R_LIB   library directory (default: D:/tools/R/lib)
#   NANOAMP_CRAN    CRAN mirror      (default: TUNA)
#   NANOAMP_BIOC    Bioconductor mirror (default: bioconductor.org)
#
# Why these defaults:
#   * CRAN is taken from the TUNA mirror; it is by far the fastest reachable
#     mirror from this network (~3 MB/s vs ~50 KB/s for CRAN's own host).
#   * Bioconductor is taken from the canonical bioconductor.org host because
#     the TUNA bioconductor path returns a stub, not a package index.
#   * download.file method "libcurl" is set explicitly: the Windows "wininet"
#     fallback fails here with "connection reset".

LIB <- Sys.getenv("NANOAMP_R_LIB", unset = "D:/tools/R/lib")
CRAN <- Sys.getenv("NANOAMP_CRAN",
                   unset = "https://mirrors.tuna.tsinghua.edu.cn/CRAN/")
BIOC <- Sys.getenv("NANOAMP_BIOC", unset = "https://bioconductor.org")

dir.create(LIB, showWarnings = FALSE, recursive = TRUE)
.libPaths(c(LIB, .libPaths()))

options(
  repos = c(CRAN = CRAN),
  BioC_mirror = BIOC,
  download.file.method = "libcurl",
  Ncpus = max(1L, parallel::detectCores() - 1L),
  timeout = 3600
)

cat("R          :", R.version.string, "\n")
cat("library    :", LIB, "\n")
cat("CRAN       :", getOption("repos")[["CRAN"]], "\n")
cat("BioC mirror:", getOption("BioC_mirror"), "\n")
cat("Ncpus      :", getOption("Ncpus"), "\n\n")

has <- function(p) requireNamespace(p, quietly = TRUE)
ver <- function(p) tryCatch(as.character(utils::packageVersion(p)),
                            error = function(e) NA_character_)

install_cran <- function(pkgs) {
  todo <- pkgs[!vapply(pkgs, has, logical(1))]
  if (length(todo)) {
    cat("[CRAN] installing:", paste(todo, collapse = ", "), "\n")
    utils::install.packages(todo, lib = LIB, quiet = FALSE)
  }
  for (p in pkgs) {
    if (has(p)) cat(sprintf("[ok]      %-14s %s\n", p, ver(p)))
    else cat(sprintf("[MISSING] %s\n", p))
  }
}

install_bioc <- function(pkgs) {
  todo <- pkgs[!vapply(pkgs, has, logical(1))]
  if (length(todo)) {
    cat("[Bioc] installing:", paste(todo, collapse = ", "), "\n")
    BiocManager::install(todo, lib = LIB, ask = FALSE, update = FALSE)
  }
  for (p in pkgs) {
    if (has(p)) cat(sprintf("[ok]      %-14s %s\n", p, ver(p)))
    else cat(sprintf("[MISSING] %s\n", p))
  }
}

## 1. bootstrap + CRAN ------------------------------------------------------
install_cran(c(
  "BiocManager", "data.table", "jsonlite", "optparse", "readxl",
  "testthat", "pkgload"
))

## 2. Bioconductor ----------------------------------------------------------
if (has("BiocManager")) {
  cat("\nBiocManager version:", as.character(BiocManager::version()), "\n\n")
  # ShortRead is deliberately absent: nanoamp reads FASTQ itself (R/io.R), and
  # ShortRead unconditionally imports pwalign, which would make an optional
  # provider a hard requirement of every installation.
  install_bioc(c("Biostrings", "IRanges", "Rsamtools"))
}

## 3. optional --------------------------------------------------------------
# shiny + DT       : GUI
# DECIPHER         : Mode B de novo clustering
# pwalign          : pairwise alignment provider on Bioconductor >= 3.19
install_cran(c("shiny", "DT"))
if (has("BiocManager")) install_bioc(c("DECIPHER", "pwalign"))

## 4. summary ---------------------------------------------------------------
# ShortRead is not listed: nanoamp does not use it (see section 2). A machine that
# has it installed from an earlier setup is fine, it is simply not required.
cat("\n=== summary ===\n")
for (p in c("BiocManager", "data.table", "jsonlite", "optparse", "readxl",
            "testthat", "pkgload", "Biostrings", "IRanges", "Rsamtools",
            "shiny", "DT", "DECIPHER", "pwalign")) {
  v <- ver(p)
  cat(sprintf("%-14s %s\n", p, ifelse(is.na(v), "<MISSING>", v)))
}
