# Build a self-contained, offline-installable bundle of every upstream
# artifact nanoamp needs, so a machine with NO network can be provisioned.
#
# Usage:
#   Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R [destdir]
#   default destdir: <repo>/dist
#
# What goes in:
#   1. the R Windows installer
#   2. every R package binary (CRAN + Bioconductor), recursively resolved,
#      saved as .zip plus a PACKAGES index so a local repo install works
#   3. the MSYS2 portable base tarball, to rebuild minimap2 from source
#   4. the minimap2 source tarball
#   5. SOURCES.tsv + SHA256SUMS.txt
#
# dist/ is git-ignored: the bundle is several hundred MB and does not belong
# in version control. See README.md in this directory for the reasoning.

args <- commandArgs(trailingOnly = TRUE)

find_repo_root <- function(start = getwd()) {
  p <- normalizePath(start, mustWork = FALSE)
  repeat {
    if (dir.exists(file.path(p, "01_data")) &&
        dir.exists(file.path(p, "02_code"))) return(p)
    parent <- dirname(p)
    if (identical(parent, p)) break
    p <- parent
  }
  normalizePath(start, mustWork = FALSE)
}

root <- find_repo_root()
dest <- if (length(args) >= 1) args[1] else file.path(root, "dist")
dest <- normalizePath(dest, mustWork = FALSE)
# The zip files must sit in a CRAN-style layout, otherwise install.packages()
# looks for <repo>/bin/windows/contrib/<rver>/PACKAGES and fails.
rver <- paste(R.version$major, sub("\\..*", "", R.version$minor), sep = ".")
pkg_root <- file.path(dest, "r-packages")
pkg_dir <- file.path(pkg_root, "bin", "windows", "contrib", rver)
msys_dir <- file.path(dest, "msys2")
src_dir <- file.path(dest, "src")
for (d in c(dest, pkg_dir, msys_dir, src_dir)) {
  dir.create(d, showWarnings = FALSE, recursive = TRUE)
}

CRAN <- "https://mirrors.tuna.tsinghua.edu.cn/CRAN/"
BIOC <- "https://bioconductor.org/"
MSYS <- "https://mirrors.tuna.tsinghua.edu.cn/msys2"

R_VERSION <- "4.6.1"
R_URL <- sprintf("%sbin/windows/base/R-%s-win.exe", CRAN, R_VERSION)
MSYS_TARBALL <- "msys2-base-x86_64-20250830.tar.zst"
MINIMAP2_URL <- "https://codeload.github.com/lh3/minimap2/tar.gz/refs/tags/v2.31"

options(repos = c(CRAN = CRAN), BioC_mirror = BIOC,
        download.file.method = "libcurl", timeout = 3600)

cat("destination:", dest, "\n")
cat("R          :", R.version.string, "\n\n")

## helpers ------------------------------------------------------------------
# A preallocated collector with an explicit index avoids <<- scoping games.
REC <- vector("list", 1024L)
N <- 0L

sha256 <- function(path) {
  if (.Platform$OS.type == "windows") {
    out <- suppressWarnings(system2(
      "powershell",
      c("-NoProfile", "-NonInteractive", "-Command",
        sprintf("(Get-FileHash -LiteralPath '%s' -Algorithm SHA256).Hash",
                gsub("'", "''", path))),
      stdout = TRUE, stderr = FALSE))
    h <- trimws(out)
    h <- h[grepl("^[0-9A-Fa-f]{64}$", h)]
    if (length(h)) return(tolower(h[1]))
  } else {
    out <- suppressWarnings(system2("sha256sum", shQuote(path), stdout = TRUE))
    if (length(out)) {
      h <- strsplit(trimws(out[1]), "\\s+")[[1]][1]
      if (grepl("^[0-9A-Fa-f]{64}$", h)) return(tolower(h))
    }
  }
  NA_character_
}

remember <- function(kind, path, url) {
  N <<- N + 1L
  REC[[N]] <<- data.frame(
    kind = kind,
    file = basename(path),
    mb = round(file.info(path)$size / 1048576, 2),
    sha256 = sha256(path),
    url = url,
    stringsAsFactors = FALSE
  )
  invisible(NULL)
}

dl <- function(url, out) {
  if (file.exists(out) && file.info(out)$size > 0) {
    cat(sprintf("  cached  %-48s\n", basename(out)))
    return(TRUE)
  }
  cat(sprintf("  fetch   %-48s\n", basename(out)))
  ok <- tryCatch({
    utils::download.file(url, out, quiet = TRUE, mode = "wb")
    TRUE
  }, error = function(e) {
    cat("    FAILED:", conditionMessage(e), "\n")
    FALSE
  })
  if (ok && file.exists(out) && file.info(out)$size > 0) {
    TRUE
  } else {
    if (file.exists(out)) unlink(out)
    FALSE
  }
}

## 1. R installer -----------------------------------------------------------
cat("== 1. R installer ==\n")
r_exe <- file.path(dest, sprintf("R-%s-win.exe", R_VERSION))
if (dl(R_URL, r_exe)) remember("r-installer", r_exe, R_URL)

## 2. R packages (binary, recursive) ---------------------------------------
cat("\n== 2. R package binaries ==\n")

want <- c("BiocManager", "data.table", "jsonlite", "optparse", "readxl",
          "testthat", "pkgload", "Biostrings", "IRanges", "Rsamtools",
          "ShortRead", "pwalign", "DECIPHER", "shiny", "DT")

rver <- paste(R.version$major, sub("\\..*", "", R.version$minor), sep = ".")
bioc_ver <- tryCatch(as.character(BiocManager::version()), error = function(e) NA)
if (is.na(bioc_ver)) bioc_ver <- "3.23"

plan <- list(
  list(url = sprintf("%sbin/windows/contrib/%s", CRAN, rver),
       type = "win.binary", label = "CRAN"),
  list(url = sprintf("%spackages/%s/bioc/bin/windows/contrib/%s",
                     BIOC, bioc_ver, rver),
       type = "win.binary", label = "Bioconductor")
)

# Recursively expand Depends/Imports/LinkingTo from a repository index.
deps_of <- function(ap, pkgs) {
  dep <- unlist(strsplit(
    paste(ap[pkgs, c("Depends", "Imports", "LinkingTo")], collapse = ","), ","))
  dep <- trimws(gsub("\\(.*?\\)", "", dep))
  dep <- dep[!is.na(dep) & nzchar(dep)]
  dep <- dep[!dep %in% c("R", "base", "NA")]
  unique(dep)
}

have <- character(0)
for (pl in plan) {
  ap <- tryCatch(available.packages(contriburl = pl$url, type = pl$type),
                 error = function(e) NULL)
  if (is.null(ap)) {
    cat("  [", pl$label, "] index unavailable:", pl$url, "\n", sep = "")
    next
  }
  cat(sprintf("  [%s] index rows: %d\n", pl$label, nrow(ap)))

  queue <- setdiff(want, have)
  guard <- 0L
  while (length(queue) && guard < 500L) {
    guard <- guard + 1L
    p <- queue[1]
    queue <- queue[-1]
    if (p %in% have) next
    if (!p %in% rownames(ap)) next        # not served by this repository

    # CRAN's index fills in the repo-relative "File" URL. Bioconductor's
    # PACKAGES leaves File empty (NA), so the file name has to be built from
    # package + version: <Base>/<pkg>_<version>.zip
    rel <- ap[p, "File"]
    if (is.na(rel) || !nzchar(rel)) {
      ver <- ap[p, "Version"]
      if (is.na(ver) || !nzchar(ver) || grepl("[^0-9.\\-]", ver)) next
      rel <- sprintf("%s_%s.zip", p, ver)
    }
    fn <- basename(rel)
    out <- file.path(pkg_dir, fn)
    url <- paste0(sub("/+$", "", pl$url), "/", rel)
    if (dl(url, out)) remember("r-package", out, url)
    have <- c(have, p)
    queue <- unique(c(queue, setdiff(deps_of(ap, p), c(have, queue))))
  }
}

missing_pkgs <- setdiff(want, have)
cat("  resolved:", length(have), "packages\n")
if (length(missing_pkgs)) {
  cat("  NOT RESOLVED:", paste(missing_pkgs, collapse = ", "), "\n")
}

## 2b. completeness check ---------------------------------------------------
# Verify the bundle satisfies the *entire* recursive closure, not just the
# top-level set. A gap here only shows up much later, as
# ".onLoad failed ... there is no package called 'generics'".
collector <- file.path(tempdir(), "bundle_closure")
unlink(collector, recursive = TRUE)
dir.create(collector, recursive = TRUE, showWarnings = FALSE)
file.copy(list.files(pkg_dir, pattern = "\\.zip$", full.names = TRUE),
          collector, overwrite = TRUE)
if (length(list.files(pkg_dir, pattern = "\\.zip$"))) {
  tools::write_PACKAGES(collector, type = "win.binary")
  base_pkgs <- rownames(installed.packages(priority = c("base", "recommended")))
  repo_ap <- available.packages(contriburl = paste0("file:///", collector),
                                type = "win.binary")
  closure <- unique(unlist(tools::package_dependencies(
    rownames(repo_ap), db = repo_ap, which = c("Depends", "Imports", "LinkingTo"),
    recursive = TRUE)))
  closure <- union(closure, rownames(repo_ap))
  closure <- setdiff(closure, base_pkgs)
  gap <- setdiff(closure, rownames(repo_ap))

  gap <- setdiff(closure, rownames(repo_ap))
  cat("  closure:", length(closure), "packages; gap:", length(gap),
      if (length(gap)) paste0(" (", paste(gap, collapse = ", "), ")") else "", "\n")

  # Fetch transitively until the closure closes. New packages bring their own
  # dependencies (e.g. futile.logger -> lambda.r, futile.options), so one pass
  # is not enough.
  rounds <- 0L
  while (length(gap) && rounds < 20L) {
    rounds <- rounds + 1L
    fetched <- 0L
    for (pl in plan) {
      ap2 <- tryCatch(available.packages(contriburl = pl$url, type = pl$type),
                      error = function(e) NULL)
      if (is.null(ap2)) next
      for (p in intersect(gap, rownames(ap2))) {
        rel <- ap2[p, "File"]
        if (is.na(rel) || !nzchar(rel)) {
          ver <- ap2[p, "Version"]
          if (is.na(ver) || grepl("[^0-9.\\-]", ver)) next
          rel <- sprintf("%s_%s.zip", p, ver)
        }
        out <- file.path(pkg_dir, basename(rel))
        url <- paste0(sub("/+$", "", pl$url), "/", rel)
        if (dl(url, out)) { remember("r-package", out, url); fetched <- fetched + 1L }
      }
    }
    unlink(collector, recursive = TRUE)
    dir.create(collector, recursive = TRUE, showWarnings = FALSE)
    file.copy(list.files(pkg_dir, pattern = "\\.zip$", full.names = TRUE),
              collector, overwrite = TRUE)
    tools::write_PACKAGES(collector, type = "win.binary")
    repo_ap <- available.packages(contriburl = paste0("file:///", collector),
                                  type = "win.binary")
    closure <- unique(unlist(tools::package_dependencies(
      rownames(repo_ap), db = repo_ap,
      which = c("Depends", "Imports", "LinkingTo"), recursive = TRUE)))
    closure <- union(closure, rownames(repo_ap))
    new_gap <- setdiff(setdiff(closure, base_pkgs), rownames(repo_ap))
    if (!length(new_gap)) { gap <- new_gap; break }
    if (identical(sort(new_gap), sort(gap)) && fetched == 0L) { gap <- new_gap; break }
    gap <- new_gap
  }
  cat("  closure after", rounds, "fill round(s):",
      length(closure), "packages,",
      if (length(gap)) paste("STILL MISSING:", paste(gap, collapse = ", ")) else "complete",
      "\n")
  unlink(collector, recursive = TRUE)
}

# Local repository index so the bundle installs with a single call:
#   install.packages(want, repos = "file:///<dest>/r-packages", type = "win.binary")
#
# Two traps to avoid here:
#  * write_PACKAGES(..., addFiles = TRUE) (the default) also writes
#    PACKAGES.gz / PACKAGES.rds, which can go stale and make
#    available.packages() report fewer packages than are on disk. Only the
#    plain PACKAGES index is kept.
#  * If older index files linger in the parent directory, R picks those up
#    instead of the contrib/4.6 one, silently hiding packages. They are
#    removed explicitly.
zips <- list.files(pkg_dir, pattern = "\\.zip$")
if (length(zips)) {
  ok <- tryCatch({
    # Clear stale indexes first (in both the leaf and the repository root, so
    # nothing shadows the one we are about to write), then write a single
    # plain PACKAGES index.
    for (d in c(pkg_dir, pkg_root)) {
      for (f in c("PACKAGES", "PACKAGES.gz", "PACKAGES.rds")) {
        p <- file.path(d, f)
        if (file.exists(p)) unlink(p)
      }
    }
    tools::write_PACKAGES(pkg_dir, type = "win.binary", addFiles = FALSE)
    for (f in c("PACKAGES.gz", "PACKAGES.rds")) {
      p <- file.path(pkg_dir, f)
      if (file.exists(p)) unlink(p)
    }
    TRUE
  }, error = function(e) {
    cat("  write_PACKAGES:", conditionMessage(e), "\n"); FALSE
  })
  cat("  PACKAGES index:", if (ok) "written" else "NOT written",
      sprintf("(%d files)\n", length(zips)))
}

# Final sanity check: every zip must be visible through the generated index.
# NOTE: use the repos= form, not contriburl=. For a local repository root they
# behave differently: contriburl= makes R look for <root>/PACKAGES, while
# repos= correctly resolves <root>/bin/windows/contrib/<rver>/PACKAGES.
if (length(zips)) {
  final_ap <- tryCatch(
    available.packages(repos = paste0("file:///", pkg_root), type = "win.binary"),
    error = function(e) NULL)
  n_visible <- if (is.null(final_ap)) 0L else nrow(final_ap)
  cat(sprintf("  index visible: %d / %d zips\n", n_visible, length(zips)))
  if (n_visible != length(zips)) {
    cat("  WARNING: index is incomplete; available.packages() will miss packages\n")
  }
}

## 3. MSYS2 toolchain (for rebuilding minimap2 offline) --------------------
cat("\n== 3. MSYS2 toolchain ==\n")
u <- sprintf("%s/distrib/x86_64/%s", MSYS, MSYS_TARBALL)
p <- file.path(msys_dir, MSYS_TARBALL)
if (dl(u, p)) remember("msys2-base", p, u)

## 4. minimap2 source ------------------------------------------------------
cat("\n== 4. minimap2 source ==\n")
p <- file.path(src_dir, "minimap2-2.31.tar.gz")
if (dl(MINIMAP2_URL, p)) remember("minimap2-source", p, MINIMAP2_URL)

## 5. manifests ------------------------------------------------------------
cat("\n== 5. manifests ==\n")
rec <- do.call(rbind, REC[seq_len(N)])
utils::write.table(rec, file.path(dest, "SOURCES.tsv"),
                   sep = "\t", quote = FALSE, row.names = FALSE, na = "")

all_files <- list.files(dest, recursive = TRUE, full.names = TRUE)
all_files <- all_files[!file.info(all_files)$isdir]
# exclude the manifests themselves from their own checksum list
all_files <- all_files[!basename(all_files) %in% c("SOURCES.tsv", "SHA256SUMS.txt")]
sums <- vapply(all_files, sha256, character(1))
# Paths in SHA256SUMS.txt must be RELATIVE to the bundle and use forward
# slashes: the Windows verifier joins them onto the bundle directory, and an
# absolute Windows path (with backslashes) would not strip correctly here.
rel <- sub(paste0("^", gsub("\\\\", "/", dest), "/?"), "",
           gsub("\\\\", "/", all_files))
writeLines(sprintf("%s  %s", sums, rel),
           file.path(dest, "SHA256SUMS.txt"))

total <- sum(file.info(all_files)$size, na.rm = TRUE)
cat("\n=== bundle complete ===\n")
cat(sprintf("files      : %d\n", length(all_files)))
cat(sprintf("R packages : %d\n", sum(rec$kind == "r-package")))
cat(sprintf("total size : %.1f MB\n", total / 1048576))
cat(sprintf("location   : %s\n", dest))
cat("\ndist/ is git-ignored. See 03_dependence/offline-bundle/README.md\n")
