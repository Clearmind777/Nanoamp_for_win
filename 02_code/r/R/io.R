# ---------------------------------------------------------------------------
# FASTA / FASTQ / table input and output
# ---------------------------------------------------------------------------

# Detecting gzip by content as well as by extension keeps a mislabelled file
# from being read as text.
fastq_connection <- function(path, mode = "rt") {
  by_extension <- grepl("\\.gz$", path, ignore.case = TRUE)
  by_magic <- FALSE
  if (!by_extension && file.exists(path)) {
    probe <- file(path, "rb")
    on.exit(close(probe), add = TRUE)
    by_magic <- identical(readBin(probe, "raw", 2L), as.raw(c(0x1f, 0x8b)))
  }
  if (by_extension || by_magic) gzfile(path, mode) else file(path, mode)
}

# Minimal FASTQ reader used instead of ShortRead::readFastq().
#
# Reading FASTQ directly is what lets nanoamp drop the ShortRead dependency:
# ShortRead unconditionally imports pwalign, so requiring it forced every
# installation to provide pairwiseAlignment() even though only aligner = "r" and
# the Mode B consensus annotation ever use it.
#
# The format assumed is the one every modern basecaller and the company
# deliverables use: four lines per record, one sequence line per record. Files
# that violate it are rejected loudly rather than silently mis-parsed.
# The quality string is returned for each read at its true length.
read_fastq_records <- function(path, block = 20000L) {
  # file() and gzfile() already return an open connection
  con <- fastq_connection(path)
  on.exit(close(con), add = TRUE)
  ids <- character(0); seqs <- character(0); quals <- character(0)
  repeat {
    lines <- readLines(con, n = 4L * block, warn = FALSE)
    n <- length(lines)
    if (n == 0L) break
    if (n %% 4L != 0L) {
      stop(sprintf(
        "Malformed FASTQ (%d lines is not a multiple of 4): %s", n, path
      ), call. = FALSE)
    }
    idx <- seq.int(1L, n, by = 4L)
    if (!all(startsWith(lines[idx], "@")) || !all(startsWith(lines[idx + 2L], "+"))) {
      stop(sprintf(
        paste0(
          "Malformed FASTQ (expected a '@' header and a '+' separator every ",
          "fourth line; wrapped records are not supported): %s"
        ),
        path
      ), call. = FALSE)
    }
    ids <- c(ids, lines[idx])
    seqs <- c(seqs, lines[idx + 1L])
    quals <- c(quals, lines[idx + 3L])
    if (n < 4L * block) break
  }
  list(id = ids, sequence = seqs, quality = quals)
}

read_fastq <- function(path) {
  if (!file.exists(path)) stop(sprintf("FASTQ file not found: %s", path), call. = FALSE)
  r <- read_fastq_records(path)
  if (length(r$id) == 0L) {
    return(data.table::data.table(
      read_id = character(0), sequence = character(0), quality = character(0)
    ))
  }
  data.table::data.table(
    # the leading '@' is not part of the read id (same as ShortRead::id())
    read_id = sub("^@", "", r$id),
    sequence = toupper(r$sequence),
    quality = r$quality
  )
}

count_fastq_reads <- function(path, block = 20000L) {
  if (!file.exists(path)) stop(sprintf("FASTQ file not found: %s", path), call. = FALSE)
  con <- fastq_connection(path)
  on.exit(close(con), add = TRUE)
  n_records <- 0L
  repeat {
    lines <- readLines(con, n = 4L * block, warn = FALSE)
    n <- length(lines)
    if (n == 0L) break
    if (n %% 4L != 0L) {
      stop(sprintf(
        "Malformed FASTQ (%d lines is not a multiple of 4): %s", n, path
      ), call. = FALSE)
    }
    n_records <- n_records + n %/% 4L
    if (n < 4L * block) break
  }
  as.integer(n_records)
}

read_reference <- function(path) {
  if (!file.exists(path)) stop(sprintf("Reference sequence not found: %s", path), call. = FALSE)
  x <- Biostrings::readDNAStringSet(path)
  if (length(x) == 0) stop(sprintf("Reference sequence is empty: %s", path), call. = FALSE)
  seq <- toupper(as.character(x[[1]]))
  list(
    name = names(x)[1] %||% "reference",
    sequence = seq,
    length = nchar(seq),
    path = normalizePath(path, mustWork = TRUE),
    md5 = safe_md5(path)
  )
}

write_fasta <- function(sequences, path) {
  if (length(sequences) == 0) {
    file.create(path)
    return(invisible(path))
  }
  x <- Biostrings::DNAStringSet(toupper(sequences))
  names(x) <- names(sequences)
  Biostrings::writeXStringSet(x, path)
  invisible(path)
}

read_company_variants <- function(path) {
  if (is.null(path) || is.na(path) || !file.exists(path)) return(NULL)
  df <- tryCatch(
    readxl::read_excel(path, sheet = 1),
    error = function(e) {
      log_warn("Could not read company variant table ", path, ": ", conditionMessage(e))
      NULL
    }
  )
  if (is.null(df) || nrow(df) == 0) return(NULL)
  df <- as.data.frame(df, stringsAsFactors = FALSE)
  pick <- function(candidates) {
    hit <- intersect(candidates, colnames(df))
    if (length(hit) == 0) return(rep(NA, nrow(df)))
    df[[hit[1]]]
  }
  out <- data.table::data.table(
    company_pos = suppressWarnings(as.integer(
      pick(c("\u7a81\u53d8\u78b1\u57fa\u4f4d\u7f6e", "Pos", "position"))
    )),
    company_ref = as.character(pick(c("\u8f93\u51fa\u78b1\u57fa", "Ref", "ref"))),
    company_alt = as.character(pick(c("\u53d8\u5f02\u78b1\u57fa", "Alt", "alt"))),
    company_type = as.character(pick(c("\u53d8\u5f02\u7c7b\u578b", "type"))),
    company_freq = suppressWarnings(as.numeric(
      pick(c("\u53d8\u5f02\u6bd4\u4f8b(%)", "Freq", "freq"))
    ))
  )
  out[]
}
