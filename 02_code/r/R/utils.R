# ---------------------------------------------------------------------------
# General utility functions
# ---------------------------------------------------------------------------

`%||%` <- function(x, y) {
  if (is.null(x) || length(x) == 0 || (length(x) == 1 && is.na(x))) y else x
}

#' nanoamp version
#'
#' @return A version string.
#' @export
nanoamp_version <- function() "0.1.0"

# ---------------------------------------------------------------------------
# Run state and error classification (P0-7)
#
# A run that fails must still leave a machine-readable record of *what kind* of
# failure it was. The GUI picks its "what do I do now" hint from `error_class`,
# and a pipeline can branch on it without parsing a message.
# ---------------------------------------------------------------------------

.nanoamp_state <- new.env(parent = emptyenv())
.nanoamp_state$log_path <- NA_character_

# Is there a per-run log file? Set by run_haplotype_analysis() so that a failed
# run's console output survives the terminal (and the GUI window) being closed.
log_set_file <- function(path) {
  .nanoamp_state$log_path <- if (is.null(path) || length(path) != 1L ||
                                 is.na(path) || !nzchar(path)) {
    NA_character_
  } else {
    as.character(path)
  }
  invisible(.nanoamp_state$log_path)
}

log_current_path <- function() .nanoamp_state$log_path

#' Signal a nanoamp error with a machine-readable class
#'
#' @param message Error message.
#' @param class One of `"input"`, `"environment"`, `"network"`, `"internal"`.
#'   `"internal"` means "a bug or a failed self-check in nanoamp itself".
#' @param call Include the call in the condition.
#'
#' @return Never returns; signals a condition of class `nanoamp_<class>`.
nanoamp_abort <- function(message, class = c("internal", "input", "environment", "network"),
                          call = FALSE) {
  class <- match.arg(class)
  stop(structure(
    class = c(paste0("nanoamp_", class), "nanoamp_error", "error", "condition"),
    list(message = as.character(message)[1],
         call = if (isTRUE(call)) sys.call(-1L) else NULL)
  ))
}

# Classify anything that reaches the top of a run. Explicit classes win; the
# message heuristics only exist for errors raised by base R or by a dependency
# (file(), curl, system2, ...), which cannot know about our vocabulary.
error_class_of <- function(e) {
  cls <- class(e)
  for (k in c("input", "environment", "network", "internal")) {
    if (paste0("nanoamp_", k) %in% cls) return(k)
  }
  msg <- tolower(paste(conditionMessage(e), collapse = " "))
  patterns <- list(
    network = c("could not resolve", "connection", "timed out", "timeout",
                "curl", "http", "ssl", "tls", "proxy", "ensembl",
                "network is unreachable", "no internet"),
    environment = c("missing r packages", "external tool", "permission denied",
                    "cannot create", "could not create", "no space left",
                    "read-only file system", "cannot open the connection for writing",
                    "there is no package called", "unable to load shared object"),
    input = c("no such file", "cannot open", "cannot read", "not found",
              "malformed", "invalid", "must be", "must contain", "not a multiple of",
              "empty file", "no reads", "truncated", "unexpected character",
              "does not exist", "unsupported")
  )
  for (k in names(patterns)) {
    if (any(vapply(patterns[[k]], function(p) grepl(p, msg, fixed = TRUE),
                   logical(1)))) {
      return(k)
    }
  }
  "internal"
}

log_msg <- function(level, ...) {
  msg <- paste0(...)
  line <- sprintf("[%s] %-5s %s", format(Sys.time(), "%Y-%m-%d %H:%M:%S"), level, msg)
  cat(line, "\n", sep = "")
  utils::flush.console()
  path <- .nanoamp_state$log_path
  if (length(path) == 1L && !is.na(path) && nzchar(path)) {
    # Best effort: a run must not fail because its own log went missing.
    try(cat(line, "\n", sep = "", file = path, append = TRUE), silent = TRUE)
  }
  invisible(line)
}

log_info <- function(...) log_msg("INFO", ...)
log_warn <- function(...) log_msg("WARN", ...)
log_error <- function(...) log_msg("ERROR", ...)

ensure_dir <- function(path) {
  if (!dir.exists(path)) {
    dir.create(path, recursive = TRUE, showWarnings = FALSE)
    if (!dir.exists(path)) {
      nanoamp_abort(sprintf(
        "Could not create the output directory: %s\nCheck that the path is writable and the disk is not full.",
        path
      ), class = "environment")
    }
  }
  normalizePath(path, mustWork = TRUE)
}

safe_div <- function(a, b) ifelse(b == 0, NA_real_, a / b)

reverse_complement <- function(x) {
  as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(x)))
}

require_packages <- function(pkgs, strict = TRUE) {
  missing <- pkgs[!vapply(pkgs, requireNamespace, logical(1), quietly = TRUE)]
  if (length(missing) > 0) {
    msg <- paste0(
      "Missing R packages: ", paste(missing, collapse = ", "),
      ". Please install them, for example BiocManager::install(c(",
      paste(sprintf('"%s"', missing), collapse = ", "), "))"
    )
    if (strict) stop(msg, call. = FALSE)
    log_warn(msg)
  }
  invisible(missing)
}

nanoamp_platform <- function() {
  sys <- tolower(Sys.info()[["sysname"]])
  os <- switch(sys, linux = "linux", windows = "windows", darwin = "macos", sys)
  arch <- tolower(R.version$arch)
  arch <- if (grepl("aarch64|arm64", arch)) {
    "arm64"
  } else if (grepl("x86_64|amd64", arch)) {
    "x86_64"
  } else {
    arch
  }
  paste(os, arch, sep = "-")
}

find_dependence_dir <- function(start = getwd()) {
  p <- normalizePath(start, mustWork = FALSE)
  repeat {
    candidate <- file.path(p, "03_dependence")
    if (dir.exists(candidate)) return(normalizePath(candidate, mustWork = TRUE))
    parent <- dirname(p)
    if (identical(parent, p)) break
    p <- parent
  }
  installed <- system.file("dependence", package = "nanoamp")
  if (nzchar(installed) && dir.exists(installed)) {
    return(normalizePath(installed, mustWork = TRUE))
  }
  NULL
}

nanoamp_dependence_dir <- function() {
  env <- Sys.getenv("NANOAMP_DEPENDENCE_DIR", unset = "")
  if (nzchar(env) && dir.exists(env)) return(normalizePath(env, mustWork = TRUE))
  find_dependence_dir()
}

nanoamp_tool_path <- function(tool, required = TRUE) {
  exe <- if (.Platform$OS.type == "windows" && !grepl("\\.exe$", tool)) {
    paste0(tool, ".exe")
  } else {
    tool
  }
  env_name <- paste0("NANOAMP_", toupper(gsub("[^A-Za-z0-9]", "_", tool)))
  env <- Sys.getenv(env_name, unset = "")
  if (nzchar(env) && file.exists(env)) return(normalizePath(env, mustWork = TRUE))

  dep <- nanoamp_dependence_dir()
  if (!is.null(dep)) {
    candidate <- file.path(dep, nanoamp_platform(), "bin", exe)
    if (file.exists(candidate)) return(normalizePath(candidate, mustWork = TRUE))
  }
  path <- Sys.which(tool)
  if (nzchar(path)) return(unname(path))
  if (required) {
    stop(sprintf(
      paste0(
        "External tool '%s' not found.\n",
        "Searched: %s and PATH.\n",
        "Put the binary in 03_dependence/%s/bin/ or set %s."
      ),
      tool,
      if (is.null(dep)) "<no 03_dependence directory>" else file.path(dep, nanoamp_platform(), "bin"),
      nanoamp_platform(),
      env_name
    ), call. = FALSE)
  }
  NULL
}

nanoamp_tool_version <- function(tool, path = NULL) {
  path <- path %||% nanoamp_tool_path(tool, required = FALSE)
  if (is.null(path)) return(NA_character_)
  out <- tryCatch(
    system2(path, "--version", stdout = TRUE, stderr = TRUE),
    error = function(e) character(0)
  )
  if (length(out) == 0) return(NA_character_)
  trimws(out[1])
}

check_external_tool <- function(tool) {
  path <- nanoamp_tool_path(tool, required = FALSE)
  if (is.null(path)) {
    nanoamp_tool_path(tool, required = TRUE)
  }
  path
}

write_tsv <- function(df, path) {
  # Defence in depth for a machine-read TSV: fwrite(quote = FALSE) writes a
  # character value verbatim, so a field containing a tab or a newline splits
  # the row and silently corrupts the file for every reader (this really
  # happened upstream: a DECIPHER message captured into qc.tsv broke the file,
  # and data.table::fread then "stopped early" without an error). Fields are
  # collapsed to a single line; no output here relies on embedded newlines.
  df <- data.table::as.data.table(df)
  if (length(df) > 0L) {
    df <- data.table::copy(df)
    for (j in seq_along(df)) {
      if (is.character(df[[j]])) {
        # gsub() passes NA through unchanged, so missing values stay missing.
        df[[j]] <- gsub("[\r\n\t]+", " ", df[[j]])
      }
    }
  }
  data.table::fwrite(df, path, sep = "\t", quote = FALSE, na = "")
}

write_json <- function(x, path) {
  jsonlite::write_json(x, path, pretty = TRUE, auto_unbox = TRUE, null = "null")
}

safe_md5 <- function(path) {
  if (!file.exists(path)) return(NA_character_)
  unname(tools::md5sum(path))
}

format_op <- function(type, pos, ref, alt) {
  out <- character(length(pos))
  for (i in seq_along(pos)) {
    out[i] <- switch(
      type[i],
      snv = sprintf("%d%s>%s", pos[i], ref[i], alt[i]),
      ins = sprintf("%dins%s", pos[i], alt[i]),
      del = sprintf("%ddel%s", pos[i], ref[i]),
      delregion = sprintf("%ddel%s", pos[i], ref[i]),
      sprintf("%s%d%s>%s", type[i], pos[i], ref[i], alt[i])
    )
  }
  out
}

homopolymer_run <- function(ref_seq, pos) {
  L <- nchar(ref_seq)
  if (is.na(pos) || pos < 1 || pos > L) return(0L)
  base <- substr(ref_seq, pos, pos)
  if (!base %in% c("A", "C", "G", "T")) return(0L)
  i <- pos
  while (i > 1 && substr(ref_seq, i - 1, i - 1) == base) i <- i - 1
  j <- pos
  while (j < L && substr(ref_seq, j + 1, j + 1) == base) j <- j + 1
  as.integer(j - i + 1)
}

variant_homopolymer_run <- function(ref_seq, type, pos, ref) {
  L <- nchar(ref_seq)
  p <- as.integer(pos)
  if (type == "ins") {
    return(max(homopolymer_run(ref_seq, p), homopolymer_run(ref_seq, min(p + 1L, L))))
  }
  if (type %in% c("del", "delregion")) {
    span <- max(nchar(ref), 1L)
    positions <- seq.int(max(1L, p), min(L, p + span))
    return(max(vapply(positions, function(x) homopolymer_run(ref_seq, x), integer(1))))
  }
  homopolymer_run(ref_seq, p)
}

seq_context <- function(ref_seq, pos, ref, alt, width = 10) {
  L <- nchar(ref_seq)
  p <- max(1L, min(as.integer(pos), L))
  left <- substr(ref_seq, max(1L, p - width), p)
  right <- substr(ref_seq, min(L, p + 1L), min(L, p + width))
  ref_disp <- if (nzchar(ref)) ref else "-"
  alt_disp <- if (nzchar(alt)) alt else "-"
  paste0(left, "[", ref_disp, "/", alt_disp, "]", right)
}

default_params <- function() {
  list(
    top_n = 20L,
    min_reads = 3L,
    min_freq = 0.02,
    min_identity = 0.90,
    min_ref_coverage = 0.90,
    homopolymer = 4L,
    strand_bias = 0.90,
    identity_cutoff = 0.99,
    min_cluster_reads = 2L,
    max_msa_seqs = 100L,
    consensus_method = "decipher",
    aligner = "minimap2",
    threads = 4L,
    keep_intermediates = TRUE
  )
}
