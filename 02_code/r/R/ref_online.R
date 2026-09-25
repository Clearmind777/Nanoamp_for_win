# ---------------------------------------------------------------------------
# Reference resolution layer (annotation, v1)
#
# All reference information is fetched online on demand; the user never
# provides a GTF or a genome FASTA. Only GENCODE/Ensembl-system sources are
# used, so transcript ids stay in the ENST/ENSG namespace:
#
#   * structure (transcripts, CDS blocks, exons, phases) -> Ensembl REST
#   * sequence (genomic slices, CDS, protein)            -> Ensembl REST
#   * sequence fallback only (never annotation tracks)   -> UCSC API
#
# Every response is cached under the XDG cache directory, because:
#   * it avoids repeating identical requests for nearby samples, and
#   * the same region is requested once per run and then reused.
#
# Hard-won constraints encoded here (measured, see
# 00_materials/optional_function.md sections 2A-2B):
#   * Ensembl region fetches are SILENTLY TRUNCATED: a 500 kb request returned
#     331,965 bp with HTTP 200. So requests are chunked and the returned length
#     is always verified against the requested one.
#   * The content-type query parameter is mandatory; without it the API
#     answers HTTP 415.
# ---------------------------------------------------------------------------

.ensembl_base <- "https://rest.ensembl.org"
.ucsc_base <- "https://api.genome.ucsc.edu"

# Maximum span for a single sequence request. Measured safe at 200 kb; 100 kb
# leaves a 2x margin for the truncation behaviour described above.
.annotation_chunk_bp <- 100000L

# Cache keys snap to this grid so that neighbouring samples share entries.
.annotation_grid_bp <- 10000L

annotation_cache_dir <- function() {
  env <- Sys.getenv("NANOAMP_CACHE_DIR", unset = "")
  if (nzchar(env)) {
    return(normalizePath(env, mustWork = FALSE))
  }
  xdg <- Sys.getenv("XDG_CACHE_HOME", unset = "")
  if (nzchar(xdg)) {
    return(file.path(xdg, "nanoamp", "ref"))
  }
  if (.Platform$OS.type == "windows") {
    # Windows has no XDG convention and path.expand("~") resolves into
    # Documents, where a hidden cache directory would be out of place. Use the
    # per-user application data directory the installer already owns, and fall
    # back to %TEMP% if it is not set.
    local <- Sys.getenv("LOCALAPPDATA", unset = "")
    if (nzchar(local)) {
      return(file.path(local, "nanoamp", "cache", "ref"))
    }
    tmp <- Sys.getenv("TEMP", unset = "")
    if (nzchar(tmp)) {
      return(file.path(tmp, "nanoamp", "ref"))
    }
  }
  file.path(path.expand("~"), ".cache", "nanoamp", "ref")
}

# --no-cache means "do not read or write the cache for this run"; it must not
# delete anything. The cache directory is also used by concurrent runs, so
# wiping it here would destroy another run's data (upstream behaviour fixed).
.annotation_cache_enabled <- function() {
  v <- Sys.getenv("NANOAMP_NO_CACHE", unset = "")
  !(nzchar(v) && tolower(v) %in% c("1", "true", "yes", "on"))
}

annotation_cache_clear <- function() {
  d <- annotation_cache_dir()
  if (dir.exists(d)) unlink(d, recursive = TRUE, force = TRUE)
  invisible(d)
}

# Size of the cache in bytes (0 when it does not exist); the GUI shows this.
annotation_cache_size <- function() {
  annotation_cache_info()$size
}

#' Cache directory, size and file count in one call
#'
#' `nanoamp cache` and the GUI's cache panel both need all three, and listing the
#' directory once is cheaper than three separate walks.
annotation_cache_info <- function() {
  d <- annotation_cache_dir()
  if (!dir.exists(d)) {
    return(list(dir = d, size = 0, files = 0L))
  }
  files <- list.files(d, recursive = TRUE, full.names = TRUE, all.files = TRUE)
  files <- files[file.exists(files) & !dir.exists(files)]
  if (length(files) == 0) {
    return(list(dir = d, size = 0, files = 0L))
  }
  list(dir = d, size = sum(file.info(files)$size, na.rm = TRUE),
       files = length(files))
}

.annotation_cache_path <- function(kind, key, ext) {
  sub <- file.path(annotation_cache_dir(), kind)
  ensure_dir(sub)
  file.path(sub, paste0(key, ext))
}

# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Throttling and response cache
#
# Ensembl rate-limits clients and answers "curl exit 56" (connection reset)
# once a burst is too fast, so requests are serialised with a minimum interval.
# Every response is also cached by URL, which both removes repeat traffic and
# makes a rerun of the same sample essentially offline.
# ---------------------------------------------------------------------------
.annotation_min_interval <- 1.1    # seconds between requests; Ensembl resets
                                   # connections (curl exit 56) on faster bursts
.annotation_last_request <- new.env(parent = emptyenv())

.annotation_throttle <- function() {
  last <- .annotation_last_request$t
  if (!is.null(last)) {
    wait <- .annotation_min_interval - (as.numeric(Sys.time()) - last)
    if (wait > 0) Sys.sleep(wait)
  }
  .annotation_last_request$t <- as.numeric(Sys.time())
}

.annotation_url_key <- function(url, params) {
  q <- if (length(params) > 0) {
    paste(sprintf("%s=%s", names(params), vapply(params, as.character, character(1))),
          collapse = "&")
  } else {
    ""
  }
  raw <- paste0(url, "?", q)
  # short, filesystem-safe, collision-resistant
  key <- paste0(sprintf("%08x", abs(sum(utf8ToInt(substr(raw, 1, 200))))) , "_",
                gsub("[^A-Za-z0-9]", "", substr(digest_like(raw), 1, 16)))
  key
}

digest_like <- function(x) {
  # base R has no hash; build a stable digest from the characters.
  v <- utf8ToInt(x)
  h <- 5381
  for (b in v) h <- (h * 33 + b) %% 2147483647
  sprintf("%08x%08x", h, length(v))
}

#' Which HTTP client will be used: "curl" or "r"
#'
#' Windows 10 1803+ ships curl.exe, but slim or older images may not have it.
#' `Sys.which("curl")` also finds the copy in the Windows system directory no
#' matter what PATH says, so this cannot be simulated by editing PATH - the
#' decision is exposed here so it can be tested directly.
annotation_http_client <- function() {
  if (nzchar(Sys.which("curl"))) "curl" else "r"
}

.http_get_once <- function(url, params = list(), dest = NULL, timeout = 60L) {
  # Split the query off the URL: R's system2() runs through a shell, so an
  # unquoted '&' in the URL would be read as a background operator and the
  # request would be silently truncated (which is exactly how Ensembl started
  # answering with its HTML error page). Passing the query with
  # -G --data-urlencode keeps every parameter out of the shell's way.
  qpos <- regexpr("?", url, fixed = TRUE)
  base <- if (qpos > 0) substr(url, 1, qpos - 1L) else url
  if (qpos > 0) {
    qs <- substr(url, qpos + 1L, nchar(url))
    extra <- strsplit(qs, "&", fixed = TRUE)[[1]]
    for (kv in extra) {
      if (!nzchar(kv)) next
      eq <- regexpr("=", kv, fixed = TRUE)
      key <- if (eq > 0) substr(kv, 1, eq - 1L) else kv
      val <- if (eq > 0) substr(kv, eq + 1L, nchar(kv)) else ""
      params[[key]] <- val
    }
  }

  curl_bin <- Sys.which("curl")
  if (!nzchar(curl_bin)) {
    # Windows 10 1803+ ships curl.exe, but slim or older images may not have
    # it. Fall back to R's own HTTP client instead of failing the run: the
    # contract is unchanged (errors propagate, nothing is silently skipped).
    return(.http_get_r(base, params = params, dest = dest, timeout = timeout))
  }
  args <- c("-sSL", "--fail", "--max-time", as.character(timeout))
  if (length(params) > 0) {
    args <- c(args, "-G")
    for (nm in names(params)) {
      args <- c(args, "--data-urlencode", paste0(nm, "=", params[[nm]]))
    }
  }
  if (is.null(dest)) {
    # The body is written to a file and read back, *not* captured with
    # `stdout = TRUE`: R inserts line breaks into very long captured lines
    # (measured: a 39,893-character Ensembl JSON line came back as 39,897
    # characters on 5 lines, splitting tokens such as "GRCh38" and
    # "havana_tagene"), which corrupts every large single-line response - and
    # Ensembl answers with exactly one long line.
    tmp <- tempfile(fileext = ".body")
    on.exit(unlink(tmp), add = TRUE)
    status <- suppressWarnings(
      system2(curl_bin, c(args, "-o", tmp, base), stdout = FALSE, stderr = FALSE)
    )
    if (!identical(as.integer(status), 0L) || !file.exists(tmp)) {
      stop(sprintf("HTTP request failed (curl exit %s): %s", status, base), call. = FALSE)
    }
    return(paste(readLines(tmp, warn = FALSE), collapse = "\n"))
  }
  status <- suppressWarnings(system2(curl_bin, c(args, "-o", dest, base),
                                     stdout = FALSE, stderr = FALSE))
  if (!identical(as.integer(status), 0L) || !file.exists(dest)) {
    stop(sprintf("HTTP request failed (curl exit %s): %s", status, base), call. = FALSE)
  }
  invisible(dest)
}

# Fallback HTTP client used when the curl binary is unavailable. R's own
# libcurl binding is enough for these small JSON/FASTA responses.
.http_get_r <- function(base, params = list(), dest = NULL, timeout = 60L) {
  query <- ""
  if (length(params) > 0) {
    enc <- vapply(names(params), function(nm) {
      paste0(utils::URLencode(nm, reserved = TRUE), "=",
             utils::URLencode(as.character(params[[nm]]), reserved = TRUE))
    }, character(1))
    query <- paste0("?", paste(enc, collapse = "&"))
  }
  full <- paste0(base, query)
  target <- if (is.null(dest)) tempfile(fileext = ".txt") else dest
  old_timeout <- getOption("timeout")
  on.exit(options(timeout = old_timeout), add = TRUE)
  options(timeout = max(as.numeric(timeout), 60))
  tryCatch(
    utils::download.file(full, target, quiet = TRUE, mode = "wb"),
    error = function(e) {
      stop(sprintf("HTTP request failed (R client): %s\n  url: %s",
                   conditionMessage(e), base), call. = FALSE)
    }
  )
  if (is.null(dest)) {
    txt <- paste(readLines(target, warn = FALSE), collapse = "\n")
    unlink(target)
    return(txt)
  }
  invisible(dest)
}

#' HTTP GET with retries
#'
#' Ensembl intermittently answers 5xx or times out (measured during
#' development: a 503 and a curl exit 28 within a few minutes of each other),
#' so transient failures are retried with a short backoff before giving up.
#' A permanent failure still surfaces as an error, because annotation must not
#' be skipped silently.
.http_get <- function(url, params = list(), dest = NULL, timeout = 60L,
                      retries = 5L, quiet = FALSE, use_cache = TRUE) {
  cache_path <- NULL
  if (use_cache && is.null(dest) && .annotation_cache_enabled()) {
    cache_path <- .annotation_cache_path(
      "http", .annotation_url_key(url, params), ".txt"
    )
    if (file.exists(cache_path)) {
      txt <- paste(readLines(cache_path, warn = FALSE), collapse = "\n")
      if (nzchar(trimws(txt))) return(txt)
      # A truncated/empty entry (killed run, disk error) must not make every
      # later run fail: drop it and fetch again.
      log_warn("annotation: dropping an empty cache entry ", basename(cache_path))
      unlink(cache_path, force = TRUE)
    }
  }
  last <- NULL
  for (attempt in seq_len(retries)) {
    .annotation_throttle()
    res <- tryCatch(
      .http_get_once(url, params = params, dest = dest, timeout = timeout),
      error = function(e) {
        last <<- conditionMessage(e)
        NULL
      }
    )
    if (!is.null(res)) {
      if (!is.null(cache_path) && is.character(res)) writeLines(res, cache_path)
      return(res)
    }
    if (attempt < retries) {
      # Back off harder on connection resets, which are how Ensembl throttles.
      # Connection resets are Ensembl's throttling signal: back off harder.
      wait <- if (grepl("(56|28)", last)) min(2^attempt, 20) + 3 else min(2^attempt, 10)
      if (!quiet) {
        log_warn(sprintf("annotation: request failed (%s); retry %d/%d in %.1fs",
                         last, as.integer(attempt), as.integer(retries - 1L),
                         as.numeric(wait)))
      }
      Sys.sleep(wait)
    }
  }
  stop(sprintf("HTTP request failed after %d attempts: %s\n  last error: %s",
               retries, url, last), call. = FALSE)
}

# ---------------------------------------------------------------------------
# Ensembl REST
# ---------------------------------------------------------------------------

.ensembl_json <- function(path, cache_key = NULL) {
  cache <- if (is.null(cache_key) || !.annotation_cache_enabled()) NULL else
    .annotation_cache_path("json", cache_key, ".json")
  parse <- function(txt) {
    tryCatch(jsonlite::fromJSON(txt, simplifyVector = FALSE),
             error = function(e) NULL)
  }
  if (!is.null(cache) && file.exists(cache)) {
    parsed <- parse(readLines(cache, warn = FALSE))
    if (!is.null(parsed)) return(parsed)
    # A corrupted cache entry (killed run, disk error, partial write) must not
    # poison every later run: drop it and fetch the answer again.
    log_warn("annotation: dropping an unreadable cache entry ", basename(cache))
    unlink(cache, force = TRUE)
  }
  # Callers may use the documented ';' separator; normalise it to '&'.
  path <- sub(";content-type=", "&content-type=", path, fixed = TRUE)
  if (!grepl("content-type", path, fixed = TRUE)) {
    path <- paste0(path, if (grepl("?", path, fixed = TRUE)) "&" else "?",
                   "content-type=application/json")
  }
  url <- paste0(.ensembl_base, path)
  txt <- .http_get(url)
  parsed <- parse(txt)
  if (is.null(parsed)) {
    # The body came from the HTTP cache and is not valid JSON. Drop that entry
    # and fetch once more ignoring the cache, instead of failing the run.
    http_cache <- .annotation_cache_path("http", .annotation_url_key(url, list()), ".txt")
    log_warn("annotation: dropping an unreadable HTTP cache entry and refetching")
    unlink(http_cache, force = TRUE)
    txt <- .http_get(url, use_cache = FALSE)
    parsed <- parse(txt)
  }
  if (is.null(parsed)) {
    nanoamp_abort(sprintf(
      "Ensembl returned a response that is not valid JSON: %s", url
    ), class = "network")
  }
  if (!is.null(cache)) writeLines(txt, cache)
  parsed
}

#' Ensembl release currently served by the REST API
annotation_ensembl_release <- function() {
  info <- .ensembl_json("/info/software", cache_key = NULL)
  as.character(info$release %||% NA_character_)
}

#' Transcripts overlapping a genomic interval (GENCODE/Ensembl id system)
#'
#' @param chrom chromosome name without the `chr` prefix, e.g. `"19"`
#' @param start,end 1-based inclusive interval
annotation_overlapping_transcripts <- function(chrom, start, end) {
  key <- sprintf("overlap_%s_%d-%d", chrom, start, end)
  feat <- .ensembl_json(
    sprintf("/overlap/region/human/%s:%d-%d?feature=transcript", chrom, start, end),
    cache_key = key
  )
  if (length(feat) == 0) return(annotation_empty_transcripts())
  rows <- lapply(feat, function(x) {
    tags <- unlist(x$tag %||% character(0), use.names = FALSE)
    data.table::data.table(
      transcript_id = as.character(x$id %||% NA_character_),
      transcript_name = as.character(x$external_name %||% NA_character_),
      gene_id = as.character(x$Parent %||% NA_character_),
      biotype = as.character(x$biotype %||% NA_character_),
      chrom = as.character(x$seq_region_name %||% chrom),
      start = as.integer(x$start %||% NA_integer_),
      end = as.integer(x$end %||% NA_integer_),
      strand = as.integer(x$strand %||% NA_integer_),
      assembly = as.character(x$assembly_name %||% NA_character_),
      is_canonical = as.logical(x$is_canonical %||% FALSE),
      is_mane = "MANE_Select" %in% tags,
      tags = paste(tags, collapse = ","),
      tsl = as.character(x$transcript_support_level %||% NA_character_),
      ccds = as.character(x$ccdsid %||% NA_character_)
    )
  })
  out <- data.table::rbindlist(rows, use.names = TRUE)
  data.table::setorder(out, -is_mane, -is_canonical, transcript_id)
  out[]
}

annotation_empty_transcripts <- function() {
  data.table::data.table(
    transcript_id = character(0), transcript_name = character(0), gene_id = character(0),
    biotype = character(0), chrom = character(0), start = integer(0), end = integer(0),
    strand = integer(0), assembly = character(0), is_canonical = logical(0),
    is_mane = logical(0), tags = character(0), tsl = character(0), ccds = character(0)
  )
}

#' CDS blocks (chrom, start, end, strand, phase) for one transcript
annotation_cds_blocks <- function(transcript_id) {
  feat <- .ensembl_json(
    sprintf("/overlap/id/%s?feature=cds", transcript_id),
    cache_key = sprintf("cds_%s", transcript_id)
  )
  if (length(feat) == 0) return(annotation_empty_blocks())
  rows <- lapply(feat, function(x) data.table::data.table(
    chrom = as.character(x$seq_region_name),
    start = as.integer(x$start),
    end = as.integer(x$end),
    strand = as.integer(x$strand),
    phase = as.integer(x$phase),
    protein_id = as.character(x$id %||% NA_character_)
  ))
  out <- data.table::rbindlist(rows, use.names = TRUE)
  data.table::setorder(out, start)
  out[]
}

#' Exon blocks for one transcript
annotation_exon_blocks <- function(transcript_id) {
  feat <- .ensembl_json(
    sprintf("/overlap/id/%s?feature=exon", transcript_id),
    cache_key = sprintf("exon_%s", transcript_id)
  )
  if (length(feat) == 0) return(annotation_empty_blocks())
  rows <- lapply(feat, function(x) data.table::data.table(
    chrom = as.character(x$seq_region_name),
    start = as.integer(x$start),
    end = as.integer(x$end),
    strand = as.integer(x$strand),
    phase = NA_integer_,
    protein_id = as.character(x$id %||% NA_character_)
  ))
  out <- data.table::rbindlist(rows, use.names = TRUE)
  data.table::setorder(out, start)
  out[]
}

annotation_empty_blocks <- function() {
  data.table::data.table(
    chrom = character(0), start = integer(0), end = integer(0),
    strand = integer(0), phase = integer(0), protein_id = character(0)
  )
}

#' Reference CDS sequence for a transcript, as served by Ensembl
annotation_cds_sequence <- function(transcript_id, retries = 5L) {
  annotation_sequence_id(transcript_id, "cds", retries = retries)
}

#' Reference protein sequence for a transcript, as served by Ensembl
annotation_protein_sequence <- function(transcript_id, retries = 5L) {
  annotation_sequence_id(transcript_id, "protein", retries = retries)
}

annotation_sequence_id <- function(transcript_id, type, retries = 5L) {
  cache <- .annotation_cache_path(
    "sequences", sprintf("%s.%s", transcript_id, type), ".txt"
  )
  if (file.exists(cache)) return(.read_sequence_file(cache))
  url <- sprintf("%s/sequence/id/%s?type=%s&content-type=text/plain",
                 .ensembl_base, transcript_id, type)
  txt <- .http_get(url, retries = retries)
  writeLines(txt, cache)
  .read_sequence_file(cache)
}

.read_sequence_file <- function(path) {
  lines <- readLines(path, warn = FALSE)
  toupper(gsub("[^A-Za-z*]", "", paste(lines, collapse = "")))
}

# ---------------------------------------------------------------------------
# Genomic sequence, with chunking and length verification
# ---------------------------------------------------------------------------

#' Fetch a genomic slice, chunked, with the returned length verified.
#'
#' Returns a list with `sequence` (character) and `assembly` (from the FASTA
#' header). Errors out if the server returns a different span than requested:
#' Ensembl truncates large requests silently, so trusting the response without
#' this check would corrupt every downstream coordinate.
annotation_region <- function(chrom, start, end, strand = 1L) {
  if (end < start) stop("annotation_region: end < start", call. = FALSE)
  span <- end - start + 1L
  if (span <= .annotation_chunk_bp) {
    return(annotation_region_chunk(chrom, start, end, strand))
  }
  pieces <- list()
  pos <- start
  while (pos <= end) {
    stop_at <- min(pos + .annotation_chunk_bp - 1L, end)
    pieces[[length(pieces) + 1L]] <- annotation_region_chunk(chrom, pos, stop_at, strand)
    pos <- stop_at + 1L
  }
  seqs <- vapply(pieces, function(p) p$sequence, character(1))
  list(sequence = paste0(seqs, collapse = ""), assembly = pieces[[1]]$assembly)
}

#' One chunk of genomic sequence; the span must be <= .annotation_chunk_bp
annotation_region_chunk <- function(chrom, start, end, strand = 1L) {
  use_cache <- .annotation_cache_enabled()
  key <- annotation_region_cache_key(chrom, start, end, strand)
  cache <- .annotation_cache_path("regions", key, ".txt")
  if (use_cache && file.exists(cache)) {
    parsed <- .read_region_cache(cache)
    if (!is.null(parsed) && nchar(parsed$sequence) == end - start + 1L) {
      return(parsed)
    }
  }
  url <- sprintf(
    "%s/sequence/region/human/%s:%d..%d:%d?content-type=text/x-fasta",
    .ensembl_base, chrom, start, end, strand
  )
  txt <- tryCatch(.http_get(url), error = function(e) NULL)
  parsed <- if (is.null(txt)) NULL else .parse_region_fasta(txt)
  if (is.null(parsed) || nchar(parsed$sequence) != end - start + 1L) {
    # Fall back to the UCSC sequence endpoint (sequence only, never annotation).
    alt <- .ucsc_region(chrom, start, end, strand)
    if (!is.null(alt) && nchar(alt) == end - start + 1L) {
      parsed <- list(sequence = alt, assembly = "hg38(ucsc)")
    }
  }
  if (is.null(parsed)) {
    stop(sprintf("Could not fetch region %s:%d-%d from Ensembl or UCSC", chrom, start, end),
         call. = FALSE)
  }
  got <- nchar(parsed$sequence)
  if (got != end - start + 1L) {
    stop(sprintf(
      paste0(
        "Region fetch was truncated: requested %s:%d-%d (%d bp) but received %d bp.\n",
        "Ensembl truncates large spans silently; the request was chunked to %d bp ",
        "and still came back short. Reduce the span or check the coordinates."
      ),
      chrom, start, end, end - start + 1L, got, .annotation_chunk_bp
    ), call. = FALSE)
  }
  if (use_cache) {
    writeLines(c(paste0(">", chrom, ":", start, "-", end, ":", strand), parsed$sequence), cache)
  }
  parsed
}

annotation_region_cache_key <- function(chrom, start, end, strand = 1L) {
  grid <- .annotation_grid_bp
  g0 <- floor((start - 1L) / grid) * grid + 1L
  g1 <- ceiling(end / grid) * grid
  sprintf("GRCh38_%s_%d-%d_s%d", chrom, g0, g1, strand)
}

.parse_region_fasta <- function(txt) {
  lines <- strsplit(txt, "\n", fixed = TRUE)[[1]]
  lines <- lines[nzchar(lines)]
  if (length(lines) == 0) return(NULL)
  header <- if (startsWith(lines[1], ">")) lines[1] else ""
  body <- if (nzchar(header)) lines[-1] else lines
  seq <- toupper(gsub("[^ACGTNacgtn]", "", paste(body, collapse = "")))
  assembly <- NA_character_
  if (nzchar(header)) {
    parts <- strsplit(sub("^>", "", header), ":", fixed = TRUE)[[1]]
    if (length(parts) >= 2) assembly <- parts[2]
  }
  list(sequence = seq, assembly = assembly)
}

.read_region_cache <- function(path) {
  lines <- readLines(path, warn = FALSE)
  lines <- lines[nzchar(lines)]
  if (length(lines) < 2) return(NULL)
  header <- lines[1]
  seq <- toupper(gsub("[^ACGTNacgtn]", "", paste(lines[-1], collapse = "")))
  parts <- strsplit(sub("^>", "", header), ":", fixed = TRUE)[[1]]
  list(sequence = seq, assembly = if (length(parts) >= 2) parts[2] else NA_character_)
}

.ucsc_region <- function(chrom, start, end, strand = 1L) {
  # UCSC is 0-based half-open and wants the chr prefix.
  chr <- if (startsWith(chrom, "chr")) chrom else paste0("chr", chrom)
  url <- sprintf("%s/getData/sequence?genome=hg38&chrom=%s&start=%d&end=%d",
                 .ucsc_base, chr, start - 1L, end)
  txt <- tryCatch(.http_get(url), error = function(e) NULL)
  if (is.null(txt)) return(NULL)
  parsed <- tryCatch(jsonlite::fromJSON(txt, simplifyVector = FALSE), error = function(e) NULL)
  seq <- parsed$dna %||% NULL
  if (is.null(seq)) return(NULL)
  seq <- toupper(gsub("[^ACGTNacgtn]", "", seq))
  if (strand < 0) seq <- as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(seq)))
  seq
}
