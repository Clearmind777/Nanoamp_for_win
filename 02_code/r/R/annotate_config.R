# ---------------------------------------------------------------------------
# Annotation configuration, provider preflight and reference resolution
#
# Two coordinate routes share one downstream pipeline:
#
#   route "cds"     user supplies CDS start/end on the amplicon reference.
#                   Needs no reference files and no network: this is the
#                   offline fallback (and the only route that works air-gapped).
#
#   route "genome"  the program locates the amplicon in GRCh38 itself and takes
#                   the transcript structure from Ensembl REST. This is the
#                   default; the user prepares nothing.
#
# Network policy (explicit by request):
#   * a preflight probe runs before any annotation work;
#   * if the reference cannot be reached, annotation aborts with a clear message
#     and a non-zero exit code -- it never silently degrades to "no annotation";
#   * the message names the concrete fallback (route "cds", or --no-cache /
#     network/proxy checks).
# ---------------------------------------------------------------------------

.annotation_config_default <- function() {
  list(
    name = "default",
    route = "cds",
    cds = list(start = NA_integer_, end = NA_integer_, strand = "+", frame = 0L,
               boundaries = "inclusive"),
    genetic_code = "Standard",
    transcript_id = NULL,
    transcript_all = FALSE,
    notes = NULL
  )
}

#' Read and validate an annotation configuration (JSON)
annotation_config_read <- function(path) {
  if (is.null(path) || is.na(path) || !nzchar(path)) {
    stop("annotation: no config path supplied", call. = FALSE)
  }
  if (!file.exists(path)) {
    stop(sprintf("Annotation config not found: %s", path), call. = FALSE)
  }
  raw <- tryCatch(jsonlite::fromJSON(path, simplifyVector = FALSE),
                  error = function(e) {
                    stop(sprintf("Annotation config is not valid JSON: %s\n  %s",
                                 path, conditionMessage(e)), call. = FALSE)
                  })
  cfg <- .annotation_config_default()

  cfg$name <- as.character(raw$name %||% basename(path))
  route <- as.character(raw$route %||% raw$assembly %||% NA_character_)
  if (is.na(route) || !nzchar(route)) {
    # Infer: an explicit cds block implies route "cds", otherwise genome.
    route <- if (!is.null(raw$cds)) "cds" else "genome"
  }
  if (identical(route, "amplicon")) route <- "cds"   # a previous scheme's name
  if (identical(route, "transcript")) route <- "genome"
  if (!route %in% c("cds", "genome")) {
    stop(sprintf("Annotation config: unknown route '%s' (expected 'cds' or 'genome')", route),
         call. = FALSE)
  }
  cfg$route <- route

  if (!is.null(raw$cds)) {
    cfg$cds$start <- as.integer(raw$cds$start %||% NA_integer_)
    cfg$cds$end <- as.integer(raw$cds$end %||% NA_integer_)
    cfg$cds$strand <- as.character(raw$cds$strand %||% "+")
    cfg$cds$frame <- as.integer(raw$cds$frame %||% 0L)
    cfg$cds$boundaries <- as.character(raw$cds$boundaries %||% "inclusive")
  }
  if (!cfg$cds$strand %in% c("+", "-")) {
    stop("Annotation config: cds.strand must be '+' or '-'", call. = FALSE)
  }
  if (!cfg$cds$frame %in% c(0L, 1L, 2L)) {
    stop("Annotation config: cds.frame must be 0, 1 or 2", call. = FALSE)
  }
  if (!cfg$cds$boundaries %in% c("inclusive", "half_open")) {
    stop("Annotation config: cds.boundaries must be 'inclusive' or 'half_open'",
         call. = FALSE)
  }

  cfg$genetic_code <- as.character(raw$genetic_code %||% "Standard")
  cfg$genetic_code_vector <- annotation_genetic_code(cfg$genetic_code)

  if (!is.null(raw$transcript_id)) cfg$transcript_id <- as.character(raw$transcript_id)
  if (isTRUE(raw$transcript_all)) cfg$transcript_all <- TRUE
  if (!is.null(raw$notes)) cfg$notes <- as.character(raw$notes)

  if (identical(cfg$route, "cds")) {
    if (is.na(cfg$cds$start)) {
      stop(paste0(
        "Annotation config: route 'cds' requires cds.start (1-based position of the\n",
        "  CDS start on the amplicon reference). cds.end is optional (defaults to the\n",
        "  end of the reference)."
      ), call. = FALSE)
    }
  }
  cfg
}

#' Resolve a genetic code name or id to the named vector translate() needs
annotation_genetic_code <- function(code) {
  code <- as.character(code %||% "Standard")
  table <- get("GENETIC_CODE_TABLE", envir = asNamespace("Biostrings"))
  idx <- which(tolower(table$name) == tolower(code) |
                 tolower(table$name2) == tolower(code) |
                 as.character(table$id) == code)
  if (length(idx) == 0) {
    stop(sprintf(
      "Annotation config: unknown genetic_code '%s'.\nValid values: %s",
      code, paste(sprintf("%s (id %s)", table$name, table$id), collapse = "; ")
    ), call. = FALSE)
  }
  Biostrings::getGeneticCode(as.character(table$id[idx[1]]))
}

# ---------------------------------------------------------------------------
# Provider preflight
# ---------------------------------------------------------------------------

#' Check that the annotation reference providers are reachable
#'
#' Called once before annotation starts. Returns a list with `ok`, `release`
#' and `problems`. When `ok` is FALSE the caller must stop: annotation results
#' cannot be produced offline, and silently skipping annotation would mislead.
annotation_provider_check <- function(timeout = 20L) {
  problems <- character(0)
  release <- NA_character_
  tryCatch({
    release <- annotation_ensembl_release()
  }, error = function(e) {
    problems <<- c(problems, sprintf("Ensembl REST unreachable (%s)", conditionMessage(e)))
  })
  if (length(problems) == 0) {
    probe_ok <- tryCatch({
      annotation_region("19", 58285652L, 58285751L)
      TRUE
    }, error = function(e) {
      problems <<- c(problems, sprintf("Ensembl sequence endpoint failed (%s)", conditionMessage(e)))
      FALSE
    })
  }
  list(ok = length(problems) == 0, release = release, problems = problems)
}

#' Abort annotation with an actionable message when the network is unusable
annotation_require_provider <- function(timeout = 20L) {
  chk <- annotation_provider_check(timeout = timeout)
  if (isTRUE(chk$ok)) return(chk)
  stop(paste0(
    "Cannot annotate: the reference providers are not reachable.\n",
    "  ", paste(chk$problems, collapse = "\n  "), "\n\n",
    "Annotation needs online access to Ensembl (structure and sequence).\n",
    "What you can do:\n",
    "  1. check network / proxy / DNS, then retry;\n",
    "  2. retry with --no-cache in case a half-written cache entry is in the way;\n",
    "  3. inspect the cache with --clear-cache and retry on a clean cache;\n",
    "  4. if this machine has no internet access, use route \"cds\" instead:\n",
    "     a config with a cds block needs no reference files and no network\n",
    "     (see configs/example_cds.json).\n",
    "Annotation is NOT skipped silently: no annotation columns are produced and\n",
    "the run exits with an error so the missing annotation cannot go unnoticed."
  ), call. = FALSE)
}

# ---------------------------------------------------------------------------
# Amplicon localisation
# ---------------------------------------------------------------------------

#' Locate an amplicon reference sequence in GRCh38
#'
#' A whole-genome exact scan is not practical over the REST API (downloading
#' every chromosome takes far too long), so the search is tiered:
#'
#'   1. a panel of known targets for the datasets in this repository;
#'   2. the remaining chromosomes, scanned window by window, with progress.
#'
#' Tiers stop at the first hit. A hit must be unique inside its window; an
#' ambiguous window is reported instead of picking one of the matches.
#'
#' @param ref_seq the amplicon reference (character, upper case)
#' @param panel optional data.table(chrom, start, end, label) to search first
#' @return list(chrom, start, end, strand, identity, n_mismatch, method)
annotation_locate_amplicon <- function(ref_seq, panel = annotation_known_panel(),
                                       window_bp = 2000000L, verbose = TRUE) {
  ref_seq <- toupper(gsub("[^ACGTNacgtn]", "", ref_seq))
  if (!nzchar(ref_seq)) stop("annotation: empty reference sequence", call. = FALSE)
  rc <- as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(ref_seq)))
  probes <- .annotation_location_probes(ref_seq)

  search_span <- function(chrom, start, end, label = NULL) {
    seq <- tryCatch(annotation_region(chrom, start, end)$sequence, error = function(e) NULL)
    if (is.null(seq)) return(NULL)
    .annotation_search_seq(chrom, seq, ref_seq, rc, probes, start - 1L,
                           "chromosome_window", label)
  }

  if (!is.null(panel) && nrow(panel) > 0) {
    for (i in seq_len(nrow(panel))) {
      res <- search_span(panel$chrom[i], panel$start[i], panel$end[i], panel$label[i])
      if (!is.null(res)) {
        if (verbose) {
          log_info(sprintf("annotation: amplicon located via gene panel (%s) at %s:%d-%d (%s)",
                           panel$label[i], res$chrom, res$start, res$end, res$strand))
        }
        return(res)
      }
    }
    if (verbose) log_info("annotation: gene panel had no hit; scanning chromosomes")
  }

  chroms <- annotation_default_chroms()
  lengths <- vapply(chroms, function(ch) {
    tryCatch(annotation_chromosome_length(ch), error = function(e) NA_integer_)
  }, integer(1))
  # Small chromosomes first: they cost least and are scanned for completeness.
  for (i in order(lengths, na.last = TRUE)) {
    chrom <- chroms[i]
    if (is.na(lengths[i])) next
    seq <- tryCatch(annotation_chromosome_sequence(chrom, verbose = verbose),
                    error = function(e) NULL)
    if (is.null(seq)) next
    res <- .annotation_search_seq(chrom, seq, ref_seq, rc, probes, 1L, "chromosome_scan")
    if (!is.null(res)) {
      if (verbose) {
        log_info(sprintf("annotation: amplicon located at %s:%d-%d (%s, identity %.4f)",
                         res$chrom, res$start, res$end, res$strand, res$identity))
      }
      return(res)
    }
  }
  stop(paste0(
    "annotation: could not locate the amplicon reference in GRCh38.\n",
    "  Searched the known-target panel and every chromosome.\n",
    "  The reference is probably not a plain GRCh38 fragment (for example a\n",
    "  plasmid construct or a heavily edited consensus).\n",
    "  Use route \"cds\" and give cds.start / cds.end explicitly instead."
  ), call. = FALSE)
}

#' Known targets of the datasets shipped with this repository
#'
#' First search tier only, to keep routine runs fast. Every entry is a region
#' whose coordinates were confirmed against Ensembl; an entry that misses simply
#' falls through to the chromosome scan, so the panel can never change
#' correctness -- only speed.
annotation_known_panel <- function() {
  data.table::data.table(
    label = "ZNF8",
    chrom = "19",
    start = 58278949L,
    end   = 58302791L
  )
}

#' Download a whole chromosome, assembled from cached region chunks
#'
#' The REST API is the only structured source available (GENCODE ships plain
#' gzip GTF without a tabix index, so a GTF cannot be queried by region), and it
#' has no "search this sequence" endpoint. Scanning therefore means downloading
#' sequence -- but each chunk is cached, so the first scan is the only expensive
#' one and later runs read from disk.
annotation_chromosome_sequence <- function(chrom, verbose = TRUE) {
  len <- annotation_chromosome_length(chrom)
  key <- annotation_region_cache_key(chrom, 1L, len, 1L)
  cache <- .annotation_cache_path("chromosomes", key, ".txt")
  if (file.exists(cache)) {
    seq <- toupper(gsub("[^ACGTNacgtn]", "", paste(readLines(cache, warn = FALSE)[-1], collapse = "")))
    if (nchar(seq) == len) return(seq)
  }
  chunk <- 1000000L
  pieces <- character(0)
  pos <- 1L
  reported <- 0L
  while (pos <= len) {
    stop_at <- min(pos + chunk - 1L, len)
    pieces <- c(pieces, annotation_region(chrom, pos, stop_at)$sequence)
    if (verbose) {
      pct <- floor(100 * stop_at / len)
      if (pct >= reported + 10L) {
        reported <- pct
        log_info(sprintf("annotation: fetching chromosome %s ... %d%%", chrom, pct))
      }
    }
    pos <- stop_at + 1L
  }
  seq <- paste0(pieces, collapse = "")
  ensure_dir(dirname(cache))
  writeLines(c(paste0(">", chrom, ":1-", len), seq), cache)
  seq
}

annotation_default_chroms <- function() {
  c(as.character(1:22), "X", "Y", "MT")
}

# Probes: try the full sequence, then several 60-mers spread across it, so an
# edited middle does not prevent localisation and an edited end is skipped.
.annotation_location_probes <- function(ref_seq, probe_len = 60L) {
  n <- nchar(ref_seq)
  if (n <= probe_len) return(ref_seq)
  starts <- unique(c(1L,
                     seq(1L, max(1L, n - probe_len + 1L), by = max(1L, (n - probe_len) %/% 8L)),
                     max(1L, n - probe_len + 1L)))
  probes <- vapply(starts, function(s) substr(ref_seq, s, min(s + probe_len - 1L, n)), character(1))
  unique(c(ref_seq, probes[nchar(probes) >= 30L]))
}

# Fetch a window and look for the probe. Only exact matches are used for
# scanning; alignment is reserved for confirming a candidate hit.
.annotation_scan_chrom <- function(chrom, probe, window_bp) {
  chr_len <- annotation_chromosome_length(chrom)
  step <- window_bp
  pos <- 1L
  hits <- list()
  while (pos <= chr_len) {
    stop_at <- min(pos + step - 1L, chr_len)
    seq <- tryCatch(annotation_region(chrom, pos, stop_at)$sequence,
                    error = function(e) NULL)
    if (is.null(seq)) return(NULL)
    m <- gregexpr(probe, seq, fixed = TRUE)[[1]]
    if (m[1] != -1L) {
      for (off in m) {
        hits[[length(hits) + 1L]] <- list(chrom = chrom, pos = pos + off - 1L,
                                          probe_len = nchar(probe))
      }
      if (length(hits) > 1L) {
        stop(sprintf(
          paste0("annotation: the amplicon probe matches %d places on chromosome %s.\n",
                 "  Ambiguous localisation; refusing to guess. Use route \"cds\" with\n",
                 "  explicit cds.start / cds.end."),
          length(hits), chrom
        ), call. = FALSE)
      }
    }
    if (length(hits) == 1L) return(hits[[1]])
    pos <- stop_at + 1L
  }
  if (length(hits) == 1L) hits[[1]] else NULL
}

# Confirm a probe hit by aligning the whole reference around it.
#' Longest common prefix of two strings
.lcp_len <- function(a, b) {
  n <- min(nchar(a), nchar(b))
  if (n == 0L) return(0L)
  i <- 0L
  while (i < n && substr(a, i + 1L, i + 1L) == substr(b, i + 1L, i + 1L)) i <- i + 1L
  i
}

#' Exact-match anchor between a reference and a genomic window
#'
#' A company consensus often matches the genome only over part of its length,
#' and it can also contain a longer internal repeat. The anchor is therefore
#' chosen in two phases:
#'
#'   1. a leading anchor: the longest run starting at the reference's 5' end,
#'      which is the most reliable part and gives the correct start coordinate;
#'   2. an internal anchor: the longest run anywhere, used only when the 5' end
#'      does not match at all.
#'
#' Returns the run length, the offset inside the reference and the offset inside
#' the genomic window (both 1-based; 0 means "no anchor").
.annotation_anchor <- function(ref_seq, seq) {
  extend <- function(off, m, len) {
    while (off + len - 1L <= nchar(ref_seq) && m + len - 1L <= nchar(seq) &&
           substr(ref_seq, off + len - 1L, off + len - 1L) ==
             substr(seq, m + len - 1L, m + len - 1L)) {
      len <- len + 1L
    }
    len - 1L
  }

  # Phase 1: leading anchor. Take progressively shorter prefixes so a partial
  # 5' match is still found even when the full prefix does not occur verbatim.
  n <- nchar(ref_seq)
  for (plen in seq(min(120L, n), 25L, by = -5L)) {
    m <- as.integer(regexpr(substr(ref_seq, 1L, plen), seq, fixed = TRUE))
    if (m > 0L) {
      len <- extend(1L, m, plen + 1L)
      return(list(len = len, ref_off = 1L, seq_off = m))
    }
  }

  # Phase 2: internal anchor.
  best <- list(len = 0L, ref_off = 0L, seq_off = 0L)
  for (off in seq(2L, max(2L, n - 24L), by = 5L)) {
    probe <- substr(ref_seq, off, min(off + 59L, n))
    if (nchar(probe) < 25L) next
    m <- as.integer(regexpr(probe, seq, fixed = TRUE))
    if (m < 0L) next
    len <- extend(off, m, nchar(probe) + 1L)
    if (len > best$len) best <- list(len = len, ref_off = off, seq_off = m)
  }
  best
}

.annotation_confirm_hit <- function(chrom, probe_pos, ref_seq, probe) {
  probe_off <- regexpr(probe, ref_seq, fixed = TRUE)
  if (probe_off < 0) return(NULL)
  n <- nchar(ref_seq)
  flank <- 200L
  start <- max(1L, probe_pos - (probe_off - 1L) - flank)
  end <- start + n + 2L * flank - 1L
  seq <- tryCatch(annotation_region(chrom, start, end)$sequence, error = function(e) NULL)
  if (is.null(seq)) return(NULL)
  # The start coordinate is always derived from the anchor, never from the
  # alignment endpoints: a partial or repetitive match would shift it.
  anc <- .annotation_anchor(ref_seq, seq)
  if (anc$len >= 40L) {
    gs <- start + anc$seq_off - 1L - (anc$ref_off - 1L)
    full <- anc$len == n
    return(list(chrom = chrom, start = gs, end = gs + n - 1L, strand = "+",
                identity = round(anc$len / n, 4), n_mismatch = n - anc$len,
                anchor_len = anc$len, anchor_coverage = round(anc$len / n, 4),
                method = if (full) "exact_match" else "exact_anchor",
                window_bp = nchar(seq)))
  }
  # Minus strand: the reference is the reverse complement of the genomic strand.
  rc_seq <- as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(seq)))
  anc_rc <- .annotation_anchor(ref_seq, rc_seq)
  if (anc_rc$len >= 40L) {
    # position of the anchor inside the forward window, then flipped
    rc_off <- anc_rc$seq_off
    gs <- start + (nchar(seq) - (rc_off + anc_rc$len - 1L) - 1L) - (anc_rc$ref_off - 1L)
    full <- anc_rc$len == n
    return(list(chrom = chrom, start = gs, end = gs + n - 1L, strand = "-",
                identity = round(anc_rc$len / n, 4), n_mismatch = n - anc_rc$len,
                anchor_len = anc_rc$len,
                anchor_coverage = round(anc_rc$len / n, 4),
                method = if (full) "exact_match_reverse" else "exact_anchor_reverse",
                window_bp = nchar(seq)))
  }
  # fall back to local alignment for edited references
  aln <- tryCatch(
    pa_pairwise_alignment(Biostrings::DNAString(ref_seq), Biostrings::DNAString(seq),
                          type = "local", gapOpening = 8, gapExtension = 2),
    error = function(e) NULL
  )
  if (is.null(aln)) return(NULL)
  pid <- pa_pid(aln)
  if (!is.finite(pid) || pid < 0.8) return(NULL)
  s0 <- pa_start(pa_subject(aln)); s1 <- pa_end(pa_subject(aln))
  n_mm <- pa_nmismatch(aln) + pa_nindel(aln)
  list(chrom = chrom, start = start + s0 - 1L, end = start + s1 - 1L, strand = "+",
       identity = round(pid, 4), n_mismatch = as.integer(n_mm), window_bp = nchar(seq))
}

# These helpers used to call pwalign directly, which contradicted the
# provider abstraction in R/zzz.R: on a machine without pwalign the package
# still loaded, but the genome route failed here instead of using the
# Biostrings provider. Route them through .pa_fn() like everything else.
.pa <- function(fn) .pa_fn(fn)
pa_pid <- function(x) .pa("pid")(x)
pa_start <- function(x) .pa("start")(x)
pa_end <- function(x) .pa("end")(x)
pa_nmismatch <- function(x) as.integer(.pa("nmismatch")(x))
# nindel() returns an InDel S4 object with insertion/deletion slots holding
# per-pattern counts, not a plain number.
pa_nindel <- function(x) {
  ni <- .pa("nindel")(x)
  if (is.numeric(ni)) return(as.integer(sum(ni)))
  sum(as.integer(unlist(lapply(methods::slotNames(ni), function(s) methods::slot(ni, s)))))
}

#' Length of a chromosome in GRCh38, cached
annotation_chromosome_length <- function(chrom) {
  key <- sprintf("chromlen_%s", chrom)
  cache <- .annotation_cache_path("json", key, ".json")
  if (.annotation_cache_enabled() && file.exists(cache)) {
    d <- jsonlite::fromJSON(cache, simplifyVector = FALSE)
    return(as.integer(d$length))
  }
  info <- .ensembl_json(sprintf("/info/assembly/homo_sapiens/%s", chrom), cache_key = NULL)
  len <- as.integer(info$length %||% NA_integer_)
  if (is.na(len)) stop(sprintf("annotation: unknown chromosome '%s'", chrom), call. = FALSE)
  if (.annotation_cache_enabled()) {
    writeLines(jsonlite::toJSON(list(chrom = chrom, length = len), auto_unbox = TRUE), cache)
  }
  len
}

# Search a fetched sequence for the amplicon, either strand.
# Returns coordinates already offset by `offset` (0-based start of `seq`).
.annotation_search_seq <- function(chrom, seq, ref_seq, rc, probes, offset,
                                   method, label = NULL) {
  for (strand in c("+", "-")) {
    q <- if (strand == "+") ref_seq else rc
    m <- gregexpr(q, seq, fixed = TRUE)[[1]]
    if (m[1] == -1L) next
    if (length(m) > 1L) {
      stop(sprintf(
        paste0("annotation: the reference matches %d places in %s.\n",
               "  Ambiguous localisation; refusing to guess.\n",
               "  Give cds.start / cds.end explicitly (route \"cds\") if you know the target."),
        length(m), chrom
      ), call. = FALSE)
    }
    gs <- offset + m - 1L
    return(list(chrom = chrom, start = gs, end = gs + nchar(ref_seq) - 1L,
                strand = strand, identity = 1, n_mismatch = 0L,
                method = if (is.null(label)) method else paste0(method, ":", label),
                window_bp = nchar(seq)))
  }
  # Edited reference: probe + local alignment.
  for (probe in probes) {
    m <- regexpr(probe, seq, fixed = TRUE)
    if (m < 0) next
    res <- .annotation_confirm_hit(chrom, offset + m - 1L, ref_seq, probe)
    if (!is.null(res)) {
      res$method <- if (is.null(label)) method else paste0(method, ":", label)
      return(res)
    }
  }
  NULL
}
