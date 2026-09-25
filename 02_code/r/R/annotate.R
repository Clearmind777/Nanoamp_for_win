# ---------------------------------------------------------------------------
# Functional annotation: localisation, transcript structure, CDS assembly,
# variant classification and haplotype-level protein annotation.
#
# Design notes
#   * The consequence vocabulary is bilingual by request: every row carries an
#     `_en` and a `_zh` column, and the enum used in code stays English.
#   * A genomic amplicon is NOT a transcript slice. It may span exons and
#     introns, so variants are classified by the genomic interval they hit
#     (CDS / UTR / intron / splice region) and the protein is built by
#     assembling the spliced CDS from the reference genome and then applying
#     only the variants that fall inside it.
#   * Consequence rows are produced per haplotype and per selected transcript
#     ("All" selects every overlapping transcript).
# ---------------------------------------------------------------------------

.annotation_consequence <- data.table::data.table(
  consequence_en = c(
    "frameshift", "stop_gained", "stop_lost", "start_lost",
    "inframe_insertion", "inframe_deletion", "missense", "synonymous",
    "splice_donor", "splice_acceptor", "splice_region",
    "5_prime_UTR", "3_prime_UTR", "intron", "outside_cds", "intergenic",
    "cds_boundary_disrupted", "cds_ambiguous_base", "no_variant"
  ),
  consequence_zh = c(
    "\u79fb\u7801", "\u63d0\u524d\u7ec8\u6b62", "\u7ec8\u6b62\u4e22\u5931", "\u8d77\u59cb\u4e22\u5931",
    "\u6574\u7801\u63d2\u5165", "\u6574\u7801\u7f3a\u5931", "\u9519\u4e49", "\u540c\u4e49",
    "\u526a\u63a5\u4f9b\u4f53", "\u526a\u63a5\u53d7\u4f53", "\u526a\u63a5\u533a",
    "5'UTR", "3'UTR", "\u5185\u542b\u5b50", "CDS \u4e4b\u5916", "\u57fa\u56e0\u95f4\u533a",
    "CDS \u8fb9\u754c\u5f02\u5e38", "CDS \u542b\u6b67\u4e49\u78b1\u57fa", "\u65e0\u53d8\u5f02"
  ),
  severity = c(
    100L, 95L, 90L, 88L, 70L, 70L, 60L, 40L,
    85L, 85L, 80L, 20L, 20L, 10L, 5L, 5L, 1L, 1L, 0L
  )
)

consequence_zh <- function(en) {
  out <- .annotation_consequence$consequence_zh[match(en, .annotation_consequence$consequence_en)]
  out[is.na(out)] <- en[is.na(out)]
  out
}

consequence_severity <- function(en) {
  out <- .annotation_consequence$severity[match(en, .annotation_consequence$consequence_en)]
  out[is.na(out)] <- 0L
  as.integer(out)
}

#' Most severe consequence in a set (per the documented priority table)
most_severe_consequence <- function(en) {
  en <- en[!is.na(en)]
  if (length(en) == 0) return(NA_character_)
  en[which.max(consequence_severity(en))]
}

# ---------------------------------------------------------------------------
# Annotation context: one per (mode run, reference)
# ---------------------------------------------------------------------------

#' Build the annotation context for a reference sequence
#'
#' @param ref_seq the amplicon reference sequence (character)
#' @param cfg result of annotation_config_read()
annotation_context <- function(ref_seq, cfg) {
  ref_seq <- toupper(gsub("[^ACGTNacgtn]", "", ref_seq))
  ctx <- list(
    config = cfg,
    ref_seq = ref_seq,
    ref_len = nchar(ref_seq),
    route = cfg$route,
    genomic = NULL,
    candidates = annotation_empty_transcripts()
  )
  if (identical(cfg$route, "genome")) {
    ctx$genomic <- annotation_locate_amplicon(ref_seq)
    # A reference that only partially matches the genome (an edited or
    # chimeric company consensus) cannot support per-base variant coordinates:
    # outside the anchored region we do not know where the reference is.
    cov <- ctx$genomic$anchor_coverage %||% 1
    if (!is.na(cov) && cov < 0.9) {
      stop(sprintf(
        paste0(
          "Annotation: the amplicon reference matches %s only over %.0f%% of its\n",
          "  length (anchor %d bp of %d).\n",
          "  Outside the anchored region the reference's position on the genome is\n",
          "  unknown, so variant coordinates there would be guesses.\n",
          "  Options: use the sample's unedited reference, provide cds.start/cds.end\n",
          "  explicitly (route \"cds\"), or annotate a sample whose reference matches\n",
          "  the genome more fully."
        ),
        ctx$genomic$method, 100 * cov, ctx$genomic$anchor_len, ctx$ref_len
      ), call. = FALSE)
    }
  } else {
    ctx$cds <- .annotation_cds_route_frame(ref_seq, cfg)
  }
  ctx
}

# Route "cds": the CDS is defined directly on the amplicon reference.
.annotation_cds_route_frame <- function(ref_seq, cfg) {
  L <- nchar(ref_seq)
  start <- as.integer(cfg$cds$start)
  end <- cfg$cds$end
  if (is.na(end)) end <- L
  end <- as.integer(end)
  if (identical(cfg$cds$boundaries, "half_open")) end <- end - 1L
  if (start < 1L || end > L || end < start) {
    stop(sprintf(
      paste0("Annotation config: cds.start/cds.end (%d..%d) fall outside the ",
             "reference (length %d)"),
      start, end, L
    ), call. = FALSE)
  }
  list(start = start, end = end, strand = cfg$cds$strand, frame = cfg$cds$frame)
}

# ---------------------------------------------------------------------------
# Transcript structure
# ---------------------------------------------------------------------------

#' Candidate transcripts for the located amplicon (route "genome")
annotation_candidates <- function(ctx, with_cds_overlap = FALSE) {
  g <- ctx$genomic
  if (is.null(g)) return(annotation_empty_transcripts())
  t <- annotation_overlapping_transcripts(g$chrom, g$start, g$end)
  if (nrow(t) == 0) return(t)
  if (!with_cds_overlap) {
    t[, cds_overlap_bp := NA_integer_]
    return(t[])
  }
  # CDS overlap is only computed on request: each transcript costs an extra
  # request, and Ensembl throttles bursts, so the default path stays cheap.
  t[, cds_overlap_bp := vapply(transcript_id, function(id) {
    b <- tryCatch(annotation_cds_blocks(id), error = function(e) annotation_empty_blocks())
    if (nrow(b) == 0) return(0L)
    ov <- pmax(0L, pmin(b$end, g$end) - pmax(b$start, g$start) + 1L)
    as.integer(sum(ov))
  }, integer(1))]
  t[]
}

#' Transcripts selected for annotation
#'
#' Selection comes from the config (`transcript_id` or `transcript_all`). When
#' nothing is selected the caller must ask the user: annotation refuses to pick
#' a transcript on its own.
annotation_select_transcripts <- function(ctx) {
  cfg <- ctx$config
  cand <- ctx$candidates
  if (nrow(cand) == 0) return(cand)
  if (isTRUE(cfg$transcript_all)) return(cand)
  if (!is.null(cfg$transcript_id) && nzchar(cfg$transcript_id)) {
    sel <- cand[transcript_id == cfg$transcript_id]
    if (nrow(sel) == 0) {
      stop(sprintf(
        paste0(
          "Annotation: transcript '%s' does not overlap the amplicon.\n",
          "Overlapping transcripts:\n  %s"
        ),
        cfg$transcript_id,
        paste(sprintf("%s (%s)", cand$transcript_id,
                      ifelse(is.na(cand$transcript_name), "-", cand$transcript_name)),
              collapse = "\n  ")
      ), call. = FALSE)
    }
    return(sel)
  }
  # Default: MANE Select, else Ensembl canonical, else refuse.
  mane <- cand[is_mane == TRUE]
  if (nrow(mane) >= 1) return(mane[1])
  can <- cand[is_canonical == TRUE]
  if (nrow(can) >= 1) return(can[1])
  stop(paste0(
    "Annotation: no transcript selected and this locus has no MANE_Select or\n",
    "canonical transcript to fall back on.\n",
    "Pick one explicitly (CLI --transcript <ENST>, or the TUI transcript list).\n",
    "Candidates:\n  ",
    paste(sprintf("%s%s%s", cand$transcript_id,
                  ifelse(is.na(cand$transcript_name), "", paste0(" ", cand$transcript_name)),
                  ifelse(cand$cds_overlap_bp > 0,
                         sprintf(" (CDS overlap %d bp)", cand$cds_overlap_bp), " (no CDS overlap)")),
          collapse = "\n  ")
  ), call. = FALSE)
}

#' Candidate transcript table as a data.table (the machine-readable form)
#'
#' `--list-transcripts` prints a human table; the GUI needs the same rows as a
#' file it can parse to build a transcript picker, so both come from here.
annotation_candidates_table <- function(ctx) {
  cand <- ctx$candidates
  if (is.null(cand) || nrow(cand) == 0) {
    return(data.table::data.table(
      transcript_id = character(0), name = character(0), biotype = character(0),
      mane = character(0), canonical = character(0), chrom = character(0),
      start = integer(0), end = integer(0), strand = character(0),
      cds_overlap_bp = integer(0)
    ))
  }
  data.table::data.table(
    transcript_id = cand$transcript_id,
    name = ifelse(is.na(cand$transcript_name), "-", cand$transcript_name),
    biotype = cand$biotype,
    mane = ifelse(cand$is_mane, "MANE", ""),
    canonical = ifelse(cand$is_canonical, "canonical", ""),
    chrom = if (is.null(ctx$genomic)) NA_character_ else ctx$genomic$chrom,
    start = if (is.null(ctx$genomic)) NA_integer_ else ctx$genomic$start,
    end = if (is.null(ctx$genomic)) NA_integer_ else ctx$genomic$end,
    strand = if (is.null(ctx$genomic)) NA_character_ else ctx$genomic$strand,
    cds_overlap_bp = cand$cds_overlap_bp
  )
}

#' Print the candidate transcript table (implements --list-transcripts)
annotation_print_candidates <- function(ctx, con = stdout()) {
  cand <- ctx$candidates
  if (nrow(cand) == 0) {
    cat("No transcript overlaps the amplicon.\n", file = con)
    return(invisible(cand))
  }
  out <- data.table::data.table(
    transcript_id = cand$transcript_id,
    name = ifelse(is.na(cand$transcript_name), "-", cand$transcript_name),
    biotype = cand$biotype,
    mane = ifelse(cand$is_mane, "MANE", ""),
    canonical = ifelse(cand$is_canonical, "canonical", ""),
    cds_overlap_bp = cand$cds_overlap_bp
  )
  cat(sprintf("Amplicon: %s:%d-%d (%s)\n",
              ctx$genomic$chrom, ctx$genomic$start, ctx$genomic$end,
              ctx$genomic$strand), file = con)
  cat(sprintf("%d overlapping transcript(s):\n", nrow(out)), file = con)
  print(out, file = con, nrows = nrow(out))
  invisible(cand)
}

#' Structure of one transcript: exon blocks, CDS blocks, assembled ref CDS
#'
#' Important: Ensembl's `overlap/id/<transcript>?feature=cds` returns the CDS
#' blocks of *every* transcript at that locus, not just the requested one (the
#' ZNF8 locus yields six different proteins this way). The blocks are therefore
#' selected by matching their combined length against the authoritative CDS
#' length served by `sequence/id/<transcript>?type=cds`, and the resulting frame
#' is checked again by the V1 protein cross-check. When the length is ambiguous
#' or matches nothing, the transcript is refused rather than guessed.
annotation_transcript_structure <- function(transcript_id) {
  exons <- annotation_exon_blocks(transcript_id)
  all_cds <- annotation_cds_blocks(transcript_id)
  if (nrow(all_cds) == 0) {
    return(list(transcript_id = transcript_id, exons = exons, cds = all_cds,
                cds_seq = NA_character_, ok = FALSE,
                problem = "transcript has no CDS (non-coding)"))
  }
  cds_api <- tryCatch(annotation_cds_sequence(transcript_id), error = function(e) NA_character_)
  if (is.na(cds_api) || !nzchar(cds_api)) {
    return(list(transcript_id = transcript_id, exons = exons, cds = all_cds,
                cds_seq = NA_character_, ok = FALSE,
                problem = "could not fetch the authoritative CDS sequence"))
  }
  want <- nchar(cds_api)
  lens <- all_cds[, .(bp = sum(end - start + 1L)), by = protein_id]
  cand <- lens[bp == want]
  cds <- if (nrow(cand) == 1L) {
    all_cds[protein_id == cand$protein_id[1]]
  } else if (nrow(cand) > 1L) {
    # Several proteins with the identical CDS length: they must agree on
    # coordinates, otherwise we cannot tell them apart.
    if (uniqueN(all_cds[protein_id %in% cand$protein_id, .(start, end)]) ==
        nrow(all_cds[protein_id == cand$protein_id[1]])) {
      all_cds[protein_id == cand$protein_id[1]]
    } else {
      return(list(transcript_id = transcript_id, exons = exons, cds = all_cds,
                  cds_seq = NA_character_, ok = FALSE,
                  problem = sprintf("ambiguous CDS blocks: %d proteins are %d bp long",
                                    nrow(cand), want)))
    }
  } else {
    return(list(transcript_id = transcript_id, exons = exons, cds = all_cds,
                cds_seq = NA_character_, ok = FALSE,
                problem = sprintf(
                  "no CDS block set matches the authoritative length %d bp (candidates: %s)",
                  want, paste(sprintf("%s=%d", lens$protein_id, lens$bp), collapse = ", "))))
  }

  chrom <- cds$chrom[1]
  strand <- cds$strand[1]
  if (uniqueN(cds$chrom) > 1L) {
    return(list(transcript_id = transcript_id, exons = exons, cds = cds,
                cds_seq = NA_character_, ok = FALSE,
                problem = "CDS spans multiple sequences"))
  }
  blocks <- if (strand > 0) cds[order(start)] else cds[order(-start)]
  pieces <- character(nrow(blocks))
  for (i in seq_len(nrow(blocks))) {
    piece <- tryCatch(
      annotation_region(chrom, blocks$start[i], blocks$end[i], strand)$sequence,
      error = function(e) NA_character_
    )
    if (is.na(piece)) {
      return(list(transcript_id = transcript_id, exons = exons, cds = cds,
                  cds_seq = NA_character_, ok = FALSE,
                  problem = "could not fetch CDS block sequence"))
    }
    if (strand < 0) {
      piece <- as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(piece)))
    }
    pieces[i] <- piece
  }
  cds_seq <- paste0(pieces, collapse = "")
  problem <- NA_character_
  if (nchar(cds_seq) != want) {
    problem <- sprintf("assembled CDS is %d bp but Ensembl serves %d bp",
                       nchar(cds_seq), want)
  } else if (!identical(cds_seq, cds_api)) {
    problem <- "assembled CDS differs from the sequence Ensembl serves"
  } else if (nchar(cds_seq) %% 3L != 0L) {
    problem <- sprintf("CDS length %d is not a multiple of 3", nchar(cds_seq))
  } else if (!identical(substr(cds_seq, 1, 3), "ATG")) {
    problem <- sprintf("CDS does not start with ATG (starts with %s)", substr(cds_seq, 1, 3))
  }
  list(transcript_id = transcript_id, exons = exons, cds = cds,
       cds_seq = cds_seq, ok = is.na(problem), problem = problem,
       chrom = chrom, strand = strand)
}

# ---------------------------------------------------------------------------
# V1: reference protein cross-check
# ---------------------------------------------------------------------------

#' Verify our assembled CDS against the protein Ensembl serves (V1)
#'
#' A mismatch means the CDS/phase/strand handling is wrong, which would corrupt
#' every downstream consequence, so the caller must abort rather than warn.
annotation_verify_reference_protein <- function(structure, genetic_code, retries = 5L) {
  if (!isTRUE(structure$ok)) {
    return(list(ok = FALSE, problem = structure$problem))
  }
  official <- tryCatch(
    annotation_protein_sequence(structure$transcript_id, retries = retries),
    error = function(e) NA_character_
  )
  if (is.na(official)) {
    return(list(ok = FALSE, problem = "could not fetch the reference protein"))
  }
  mine <- as.character(Biostrings::translate(
    Biostrings::DNAString(structure$cds_seq), genetic.code = genetic_code
  ))
  mine <- sub("[*]$", "", mine)
  official <- sub("[*]$", "", official)
  if (identical(mine, official)) {
    # `verified` is what run_manifest.json reports: the reference CDS in this
    # structure was translated and matched the authoritative Ensembl protein.
    return(list(ok = TRUE, protein = mine, length_aa = nchar(mine),
                verified = TRUE))
  }
  list(ok = FALSE, problem = sprintf(
    paste0("reference protein mismatch for %s: our translation is %d aa, ",
           "Ensembl serves %d aa"),
    structure$transcript_id, nchar(mine), nchar(official)
  ))
}

# ---------------------------------------------------------------------------
# Applying variants to a reference frame
# ---------------------------------------------------------------------------

#' Apply variant operations to a sequence
#'
#' Operations use the same convention as R/correct.R: `pos` is the reference
#' position the operation is anchored to, `ref` is the reference allele for
#' substitutions and deletions, `alt` is the inserted/substituted sequence.
#' Coordinates are forward-strand; on a minus-strand frame the caller has
#' already reverse-complemented the alleles.
.annotation_apply_ops <- function(seq, ops) {
  if (is.null(ops) || nrow(ops) == 0) return(seq)
  ops <- data.table::as.data.table(ops)
  ops <- ops[order(pos, match(type, c("snv", "del", "ins")))]
  # Malformed operations mean the coordinate mapping upstream is wrong, so
  # report rather than append or truncate silently.
  L <- nchar(seq)
  bad <- which(ops$pos > L & as.character(ops$type) != "ins")
  if (length(bad) > 0) {
    stop(sprintf(
      "annotation: operation position %d is past the end of the %d bp frame",
      ops$pos[bad[1]], L
    ), call. = FALSE)
  }
  over <- which(as.character(ops$type) %in% c("del", "delregion") &
                  (ops$pos + nchar(ops$ref) - 1L) > L)
  if (length(over) > 0) {
    stop(sprintf(
      "annotation: deletion at %d spans past the end of the %d bp frame",
      ops$pos[over[1]], L
    ), call. = FALSE)
  }
  out <- character(0)
  cursor <- 1L
  for (i in seq_len(nrow(ops))) {
    p <- as.integer(ops$pos[i])
    type <- ops$type[i]
    r <- if (is.na(ops$ref[i])) "" else as.character(ops$ref[i])
    a <- if (is.na(ops$alt[i])) "" else as.character(ops$alt[i])
    if (identical(type, "ins")) {
      if (p < 1L) {
        out <- c(out, a)
        next
      }
      if (p >= cursor) out <- c(out, substr(seq, cursor, p))
      out <- c(out, a)
      cursor <- p + 1L
    } else {
      if (p > cursor) out <- c(out, substr(seq, cursor, p - 1L))
      out <- c(out, a)
      cursor <- p + nchar(r)
    }
  }
  if (cursor <= L) out <- c(out, substr(seq, cursor, L))
  paste0(out, collapse = "")
}

# ---------------------------------------------------------------------------
# Variant coordinate mapping
# ---------------------------------------------------------------------------

#' Map amplicon-frame variants onto the genomic frame
#'
#' Works on the reference frame. The amplicon reference is in the reads' own
#' orientation, so on a minus-strand hit its position 1 corresponds to the
#' highest genomic coordinate:
#'
#'   * substitutions and deletions: genome = end - pos + 1
#'   * insertions are anchored between pos-1 and pos, so their genomic anchor is
#'     the base *after* the insertion point: genome = end - pos + 2
#'
#' Alleles are reverse-complemented so that every operation can be applied to
#' forward-strand sequence. Getting this wrong shifts every coordinate by one or
#' flips an allele, which is why the mirror tests in test-annotate.R compare a
#' minus-strand frame against the equivalent plus-strand one.
annotation_variants_to_genomic <- function(ops, genomic) {
  if (is.null(ops) || nrow(ops) == 0) return(ops)
  ops <- data.table::as.data.table(ops)
  minus <- identical(genomic$strand, "-")
  out <- data.table::copy(ops)
  if (!minus) {
    out[, genome_pos := as.integer(pos) + genomic$start - 1L]
    return(out[])
  }
  is_ins <- as.character(out$type) == "ins"
  out[, genome_pos := genomic$end - as.integer(pos) + 1L]
  out[is_ins, genome_pos := genomic$end - as.integer(pos) + 2L]
  # alleles are given on the plus strand of the amplicon; the genomic frame is
  # the opposite strand
  out[, `:=`(ref = .annotation_rc_alleles(ref), alt = .annotation_rc_alleles(alt))]
  out[]
}

#' Reverse-complement a character vector of alleles (NA and "" pass through)
.annotation_rc_alleles <- function(x) {
  x <- as.character(x)
  out <- vapply(x, function(v) {
    if (is.na(v) || !nzchar(v)) return("")
    as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(v)))
  }, character(1))
  out[is.na(x)] <- NA_character_
  out
}

# ---------------------------------------------------------------------------
# CDS selection and variant consequence
# ---------------------------------------------------------------------------

#' Build the CDS frame for a transcript, including which variants land in it
annotation_cds_frame <- function(structure, genomic, ops) {
  cds <- structure$cds
  strand <- structure$strand
  blocks <- if (strand > 0) cds[order(start)] else cds[order(-start)]
  # The spliced CDS was assembled (and V1-verified) when the structure was
  # built, so it is reused here rather than fetched once per haplotype.
  cds_seq <- structure$cds_seq

  # Variants whose anchor lies inside a CDS block, converted to CDS coordinates.
  within <- if (nrow(ops) == 0) ops else ops[
    genome_pos >= min(cds$start) & genome_pos <= max(cds$end)
  ]
  if (nrow(within) > 0) {
    within <- data.table::copy(within)
    within[, cds_pos := vapply(genome_pos, function(gp) {
      for (i in seq_len(nrow(blocks))) {
        # A block always satisfies start <= end on the forward strand, so the
        # containment test is identical for both strands. (An earlier version
        # tested gp <= start && gp >= end for the minus strand, which is never
        # true and silently dropped every variant on that strand.)
        if (gp < blocks$start[i] || gp > blocks$end[i]) next
        before <- if (i > 1L) {
          sum(blocks$end[seq_len(i - 1L)] - blocks$start[seq_len(i - 1L)] + 1L)
        } else {
          0L
        }
        # blocks are already in transcript order: ascending on the plus strand,
        # descending on the minus strand
        offset <- if (strand > 0) gp - blocks$start[i] else blocks$end[i] - gp
        return(as.integer(before + offset + 1L))
      }
      NA_integer_
    }, integer(1))]
  }

  list(cds_seq = cds_seq, ops_in_cds = within, blocks = blocks, strand = strand)
}

#' Translate a CDS sequence with the ambiguity rules from the plan
.annotation_translate <- function(seq, genetic_code) {
  bad <- grepl("[^ACGT]", seq)
  if (bad) {
    return(list(ok = FALSE, protein = NA_character_,
                problem = "CDS contains ambiguous bases (not ACGT)"))
  }
  if (nchar(seq) %% 3L != 0L) {
    return(list(ok = FALSE, protein = NA_character_,
                problem = sprintf("CDS length %d is not a multiple of 3", nchar(seq))))
  }
  list(ok = TRUE,
       protein = as.character(Biostrings::translate(Biostrings::DNAString(seq),
                                                    genetic.code = genetic_code)),
       problem = NA_character_)
}

#' Classify one variant against the transcript structure
annotation_variant_consequence <- function(type, genome_pos, ref, alt, structure,
                                           genetic_code, amp_start, amp_end) {
  cds <- structure$cds
  if (nrow(cds) == 0) return("outside_cds")
  cds_start <- min(cds$start); cds_end <- max(cds$end)
  if (genome_pos < cds_start || genome_pos > cds_end) {
    # inside the amplicon but outside the CDS: UTR or intron
    ex <- structure$exons
    if (nrow(ex) > 0 && any(genome_pos >= ex$start & genome_pos <= ex$end)) {
      return(if (structure$strand > 0) "5_prime_UTR" else "3_prime_UTR")
    }
    return("intron")
  }
  # splice proximity: within 2 bp of a CDS block boundary inside an intron
  if (nrow(cds) > 1) {
    gaps_from <- pmin(abs(genome_pos - cds$start), abs(genome_pos - cds$end))
    if (any(gaps_from > 0 & gaps_from <= 2)) {
      return("splice_region")
    }
  }
  type <- as.character(type)
  if (type %in% c("del", "delregion")) {
    len <- nchar(as.character(ref))
    return(if (len %% 3L == 0L) "inframe_deletion" else "frameshift")
  }
  if (identical(type, "ins")) {
    len <- nchar(as.character(alt))
    return(if (len %% 3L == 0L) "inframe_insertion" else "frameshift")
  }
  # SNV: needs the codon, which the haplotype-level pass computes; here report a
  # placeholder that the caller replaces after translation.
  "coding_snv"
}

# ---------------------------------------------------------------------------
# Haplotype-level annotation
# ---------------------------------------------------------------------------

#' Annotate one haplotype against one transcript
annotation_haplotype_transcript <- function(hap_seq, structure, genomic, ops,
                                            genetic_code, with_proteins = FALSE) {
  frame <- annotation_cds_frame(structure, genomic, ops)
  ref_cds <- frame$cds_seq
  # Variants whose anchor maps outside any CDS block (intron, or the few bases
  # between two blocks) carry no CDS position and are excluded from translation.
  within <- frame$ops_in_cds
  if (!is.null(within) && nrow(within) > 0) {
    within <- within[!is.na(cds_pos)]
  }
  ref_tr <- .annotation_translate(ref_cds, genetic_code)
  empty <- list(
    cds_ok = FALSE, consequence = NA_character_, protein_change = NA_character_,
    ref_protein = NA_character_, alt_protein = NA_character_,
    n_aa_changed = NA_integer_, ref_protein_length = NA_integer_,
    alt_protein_length = NA_integer_, notes = NA_character_
  )
  if (nchar(ref_cds) == 0L) {
    empty$notes <- "reference CDS is empty"
    return(empty)
  }
  if (nchar(ref_cds) %% 3L != 0L) {
    empty$notes <- sprintf("reference CDS length %d is not a multiple of 3", nchar(ref_cds))
    return(empty)
  }
  if (!isTRUE(ref_tr$ok)) {
    empty$notes <- ref_tr$problem
    return(empty)
  }
  if (is.null(within) || nrow(within) == 0) {
    # No variant lands inside the CDS. Two different situations used to be
    # reported as "synonymous", which reads as "there is a coding change but it
    # is silent": an exact reference match (no_variant) and a haplotype whose
    # variants all sit outside the CDS (outside_cds). Both are labelled
    # explicitly now; the translations are identical by construction, so the
    # unchanged protein is still reported.
    ref_p <- sub("[*]$", "", ref_tr$protein)
    return(list(
      cds_ok = TRUE,
      consequence = if (is.null(ops) || nrow(ops) == 0) "no_variant" else "outside_cds",
      protein_change = "p.(=)",
      ref_protein = if (with_proteins) ref_p else NA_character_,
      alt_protein = if (with_proteins) ref_p else NA_character_,
      n_aa_changed = 0L,
      ref_protein_length = nchar(ref_p), alt_protein_length = nchar(ref_p),
      notes = NA_character_
    ))
  }
  # Apply the in-CDS variants to the reference CDS.
  alt_cds <- if (is.null(within) || nrow(within) == 0) {
    ref_cds
  } else {
    .annotation_apply_ops(ref_cds, within[, .(type, pos = cds_pos, ref, alt)])
  }
  # A length change that is not a multiple of three IS a frameshift: it is a
  # real biological consequence, not a technical failure. Only a length change
  # that keeps the frame but still cannot be translated is reported as a
  # boundary problem.
  delta <- nchar(alt_cds) - nchar(ref_cds)
  frameshift <- delta %% 3L != 0L
  alt_tr <- if (frameshift) {
    # Translate up to the last complete codon; the tail is not meaningful.
    usable <- nchar(alt_cds) - (nchar(alt_cds) %% 3L)
    .annotation_translate(substr(alt_cds, 1, usable), genetic_code)
  } else {
    .annotation_translate(alt_cds, genetic_code)
  }
  if (!isTRUE(alt_tr$ok) && !frameshift) {
    empty$notes <- alt_tr$problem
    empty$consequence <- "cds_boundary_disrupted"
    return(empty)
  }
  ref_p <- sub("[*]$", "", ref_tr$protein)
  alt_p_raw <- alt_tr$protein
  alt_p <- sub("[*]$", "", alt_p_raw)
  # ref/alt protein as they come out of translate(), stop codon included
  ref_full <- ref_tr$protein
  alt_full <- if (isTRUE(alt_tr$ok)) alt_tr$protein else ""
  ref_has_stop <- grepl("[*]$", ref_full)
  alt_has_stop <- grepl("[*]$", alt_full)
  # a stop codon before the final one means a premature termination
  premature <- grepl("[*]", substr(alt_full, 1L, max(0L, nchar(alt_full) - 1L)))
  # `premature` is only meaningful when the reference itself terminates
  # normally: a user-supplied CDS that stops before its stop codon would
  # otherwise make every haplotype look like a premature stop.
  consequence <- if (frameshift) {
    "frameshift"
  } else if (ref_has_stop && premature) {
    "stop_gained"
  } else if (ref_has_stop && !alt_has_stop) {
    "stop_lost"
  } else if (identical(ref_p, alt_p)) {
    "synonymous"
  } else if (delta > 0L) {
    "inframe_insertion"
  } else if (delta < 0L) {
    "inframe_deletion"
  } else {
    "missense"
  }
  list(
    cds_ok = TRUE,
    consequence = consequence,
    protein_change = .annotation_protein_change(ref_p, alt_p,
                                                frameshift = frameshift, delta = delta),
    ref_protein = if (with_proteins) ref_p else NA_character_,
    alt_protein = if (with_proteins) alt_p else NA_character_,
    n_aa_changed = .annotation_count_aa_diff(ref_p, alt_p),
    ref_protein_length = nchar(ref_p), alt_protein_length = nchar(alt_p),
    notes = if (frameshift) sprintf("length change %+d bp (not a multiple of 3)", delta) else NA_character_
  )
}

.annotation_count_aa_diff <- function(a, b) {
  x <- strsplit(a, "")[[1]]; y <- strsplit(b, "")[[1]]
  n <- max(length(x), length(y))
  length(x) <- n; length(y) <- n
  sum(xor(is.na(x), is.na(y)) | (!is.na(x) & !is.na(y) & x != y))
}

#' Compact HGVS-style (NOT certified-HGVS) protein change description
.annotation_protein_change <- function(ref_p, alt_p, frameshift = FALSE, delta = 0L) {
  if (identical(ref_p, alt_p)) return("p.(=)")
  x <- strsplit(ref_p, "")[[1]]
  y <- strsplit(alt_p, "")[[1]]
  n <- min(length(x), length(y))
  first <- which(x[seq_len(n)] != y[seq_len(n)])[1]
  if (is.na(first)) first <- n + 1L
  three <- function(a) if (is.na(a)) "Ter" else .aa3(a)
  pos <- if (length(x) == 0L) 1L else min(first, length(x))
  if (frameshift) {
    # the residue change and the new reading frame are what matters here
    return(sprintf("p.%s%dfs", three(x[pos]), pos))
  }
  if (delta > 0L) {
    # delta counts the residues in the alternate protein over the same span,
    # so the inserted residues are the alternate ones from `pos` onwards.
    ins <- paste(vapply(y[seq.int(pos, min(pos + delta - 1L, length(y)))], .aa3,
                        character(1)), collapse = "")
    end <- min(pos + delta - 1L, length(x))
    return(sprintf("p.%s%d_%s%dins%s", three(x[pos]), pos, three(x[end]), end, ins))
  }
  if (delta < 0L) {
    n <- abs(delta)
    del <- paste(vapply(x[seq.int(pos, min(pos + n - 1L, length(x)))], .aa3,
                        character(1)), collapse = "")
    return(sprintf("p.%s%ddel", three(x[pos]), pos))
  }
  sprintf("p.%s%d%s", three(x[pos]), pos, three(y[pos]))
}

.aa3 <- function(a) {
  map <- c(A="Ala", R="Arg", N="Asn", D="Asp", C="Cys", Q="Gln", E="Glu", G="Gly",
           H="His", I="Ile", L="Leu", K="Lys", M="Met", F="Phe", P="Pro", S="Ser",
           T="Thr", W="Trp", Y="Tyr", V="Val", "*"="Ter")
  out <- map[a]
  ifelse(is.na(out), a, unname(out))
}

# ---------------------------------------------------------------------------
# Variant-level detail (--annotation-detail)
# ---------------------------------------------------------------------------

#' Per-variant annotation within a transcript
#'
#' Each variant is described on its own: its consequence, the codon it touches
#' and the amino-acid change it causes. This is deliberately separate from the
#' haplotype-level pass -- the joint consequence of several variants can differ
#' from any single-variant description, which is why the haplotype table remains
#' the primary deliverable.
annotation_variant_detail <- function(ops, structure, genetic_code) {
  if (is.null(ops) || nrow(ops) == 0) return(NULL)
  ops <- data.table::as.data.table(ops)
  blocks <- structure$cds
  if (nrow(blocks) == 0) return(NULL)
  cds_seq <- structure$cds_seq
  cds_lo <- min(blocks$start); cds_hi <- max(blocks$end)
  # relative position of each genomic coordinate inside the spliced CDS
  cds_pos_of <- function(gp) {
    if (gp < cds_lo || gp > cds_hi) return(NA_integer_)
    vapply(gp, function(g) {
      for (i in seq_len(nrow(blocks))) {
        if (g >= blocks$start[i] && g <= blocks$end[i]) {
          before <- sum(pmax(0L, blocks$end[seq_len(i - 1L)] -
                               blocks$start[seq_len(i - 1L)] + 1L))
          return(as.integer(before + (g - blocks$start[i]) + 1L))
        }
      }
      NA_integer_
    }, integer(1))
  }
  rows <- vector("list", nrow(ops))
  for (i in seq_len(nrow(ops))) {
    gp <- as.integer(ops$genome_pos[i])
    type <- as.character(ops$type[i])
    cp <- cds_pos_of(gp)
    con <- "outside_cds"; codon_ref <- NA_character_
    codon_alt <- NA_character_; aa_ref <- NA_character_; aa_alt <- NA_character_
    if (!is.na(cp)) {
      if (type %in% c("del", "delregion")) {
        n <- nchar(as.character(ops$ref[i]))
        con <- if (n %% 3L == 0L) "inframe_deletion" else "frameshift"
      } else if (identical(type, "ins")) {
        n <- nchar(as.character(ops$alt[i]))
        con <- if (n %% 3L == 0L) "inframe_insertion" else "frameshift"
      } else {
        # substitution: apply it alone and read the codon it changes
        op1 <- ops[i, .(type, pos = cp, ref, alt)]
        alt_cds <- .annotation_apply_ops(cds_seq, op1)
        tr_ref <- .annotation_translate(cds_seq, genetic_code)
        tr_alt <- .annotation_translate(
          substr(alt_cds, 1L, nchar(alt_cds) - (nchar(alt_cds) %% 3L)), genetic_code)
        if (isTRUE(tr_ref$ok) && isTRUE(tr_alt$ok)) {
          ci <- (cp - 1L) %/% 3L + 1L
          codon_ref <- substr(cds_seq, (ci - 1L) * 3L + 1L, ci * 3L)
          codon_alt <- substr(alt_cds, (ci - 1L) * 3L + 1L, ci * 3L)
          a0 <- substr(tr_ref$protein, ci, ci)
          a1 <- substr(tr_alt$protein, ci, ci)
          aa_ref <- a0; aa_alt <- a1
          con <- if (identical(a0, a1)) {
            "synonymous"
          } else if (identical(a1, "*")) {
            "stop_gained"
          } else if (identical(a0, "*")) {
            "stop_lost"
          } else {
            "missense"
          }
        }
      }
    }
    rows[[i]] <- data.table::data.table(
      type = type, genome_pos = gp, cds_pos = cp,
      ref = ops$ref[i], alt = ops$alt[i],
      codon_ref = codon_ref, codon_alt = codon_alt,
      aa_ref = aa_ref, aa_alt = aa_alt,
      consequence_en = con, consequence_zh = consequence_zh(con),
      transcript_id = structure$transcript_id
    )
  }
  data.table::rbindlist(rows, use.names = TRUE)
}

# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

#' Run functional annotation for a finished analysis
#'
#' @param ref_seq amplicon reference sequence
#' @param hap haplotype table with `haplotype_id`, `signature` and `count`
#' @param variants variants table (may be NULL)
#' @param outdir output directory; `annotation.tsv` is written there
#' @param cfg annotation config (annotation_config_read())
#' @param list_only when TRUE only the candidate transcript table is printed
#' @return list(available, table, qc, manifest, message)
run_annotation <- function(ref_seq, hap, variants, outdir, cfg,
                           list_only = FALSE, quiet = FALSE,
                           include_proteins = FALSE, include_detail = FALSE) {
  # Provider preflight only for the genome route. Route "cds" is the offline
  # path: it works from an explicit CDS span with translation alone and must not
  # require any network access.
  needs_network <- identical(cfg$route, "genome")
  chk <- if (needs_network) {
    annotation_require_provider()
  } else {
    list(ok = TRUE, release = NA_character_)
  }
  if (needs_network && !quiet) log_info("annotation: Ensembl release ", chk$release)
  # Where the structure/sequence came from. The offline route never touches
  # Ensembl, so it must not be reported as if it did.
  ann_source <- if (needs_network) "ensembl-rest" else "cds-config"

  ctx <- annotation_context(ref_seq, cfg)
  if (identical(cfg$route, "genome")) {
    ctx$candidates <- annotation_candidates(ctx)
  }
  if (isTRUE(list_only)) {
    annotation_print_candidates(ctx)
    # Also write the candidates as a table: the GUI builds its transcript picker
    # from this file, and hand-parsing the printed table would be fragile.
    try(write_tsv(annotation_candidates_table(ctx),
                  file.path(outdir, "transcripts.tsv")), silent = TRUE)
    return(invisible(list(requested = TRUE, available = FALSE, list_only = TRUE,
                          table = NULL, qc = NULL, manifest = NULL,
                          candidates = ctx$candidates)))
  }

  if (identical(cfg$route, "cds")) {
    tsel <- data.table::data.table(
      transcript_id = sprintf("amplicon_cds_%d_%d", ctx$cds$start, ctx$cds$end),
      transcript_name = cfg$name, gene_id = NA_character_,
      biotype = "user_defined", chrom = NA_character_,
      start = NA_integer_, end = NA_integer_,
      strand = if (identical(ctx$cds$strand, "-")) -1L else 1L,
      assembly = NA_character_, is_canonical = FALSE, is_mane = FALSE,
      tags = NA_character_, tsl = NA_character_, ccds = NA_character_,
      cds_overlap_bp = ctx$cds$end - ctx$cds$start + 1L
    )
  } else {
    tsel <- annotation_select_transcripts(ctx)
  }

  genomic <- ctx$genomic
  # The genomic frame is needed to map variants; for route "cds" the frame is
  # the CDS itself.
  frame <- if (is.null(genomic)) {
    list(chrom = NA_character_, start = ctx$cds$start, end = ctx$cds$end,
         strand = ctx$cds$strand, identity = 1, n_mismatch = 0L, method = "cds_config",
         window_bp = ctx$cds$end - ctx$cds$start + 1L)
  } else {
    genomic
  }

  rows <- list()
  detail_rows <- list()
  qc_extra <- list()
  manifest_tr <- list()
  skipped_tr <- list()

  for (ti in seq_len(nrow(tsel))) {
    tid <- tsel$transcript_id[ti]
    structure <- if (identical(cfg$route, "cds")) {
      .annotation_cds_route_structure(tid, ctx$cds, ref_seq)
    } else {
      annotation_transcript_structure(tid)
    }
    if (!isTRUE(structure$ok)) {
      if (!quiet) log_warn("annotation: ", tid, " skipped: ", structure$problem)
      skipped_tr[[length(skipped_tr) + 1L]] <- list(
        transcript_id = tid,
        transcript_name = tsel$transcript_name[ti],
        problem = structure$problem
      )
      next
    }
    # V1: abort rather than emit consequences built on a wrong frame.
    # Route "cds" has no authoritative protein to compare against (that needs
    # Ensembl), so the structural check from the structure step is what guards
    # it, and the run manifest records that V1 was unavailable.
    v1 <- if (needs_network) {
      annotation_verify_reference_protein(structure, cfg$genetic_code_vector)
    } else {
      list(ok = TRUE, length_aa = nchar(structure$cds_seq) %/% 3L,
           protein = NA_character_, verified = FALSE)
    }
    if (!isTRUE(v1$ok)) {
      stop(sprintf(
        paste0(
          "Annotation self-check failed (V1 reference protein cross-check).\n",
          "  %s\n",
          "This means the CDS / phase / strand handling is wrong, so every\n",
          "consequence would be wrong too. Aborting instead of reporting them."
        ), v1$problem
      ), call. = FALSE)
    }
    if (!quiet) {
      # Say only what happened: the offline cds route has no authoritative
      # protein to cross-check against (see `protein_verified` above).
      if (isTRUE(v1$verified)) {
        log_info(sprintf("annotation: %s verified against the Ensembl protein (%d aa)",
                         tid, v1$length_aa))
      } else {
        log_info(sprintf("annotation: %s structure ok (%d aa, no reference protein to cross-check)",
                         tid, v1$length_aa))
      }
    }
    manifest_tr[[length(manifest_tr) + 1L]] <- list(
      transcript_id = tid,
      transcript_name = tsel$transcript_name[ti],
      is_mane = isTRUE(tsel$is_mane[ti]),
      is_canonical = isTRUE(tsel$is_canonical[ti]),
      cds_length = nchar(structure$cds_seq),
      protein_length = v1$length_aa,
      # L10 (Windows fix): upstream hard-codes TRUE here. Route "cds" has no
      # authoritative protein to compare against, so claiming "verified" would
      # be a fabricated statement in a machine-read manifest. Report what the
      # V1 cross-check actually established.
      protein_verified = isTRUE(v1$verified),
      cds_blocks = nrow(structure$cds)
    )

    for (h in seq_len(nrow(hap))) {
      ops <- signature_to_ops(hap$signature[h])
      gops <- if (nrow(ops) == 0) {
        ops
      } else if (identical(cfg$route, "cds")) {
        out <- data.table::copy(ops)[, genome_pos := as.integer(pos)]
        # On the configured minus strand the CDS is the reverse complement of
        # the reference slice, so the alleles have to be flipped with it.
        # Positions stay in amplicon coordinates: annotation_cds_frame()
        # counts from the high end of the block, which IS the transcript 5' end
        # on the minus strand. Upstream left the amplicon letters unchanged, so
        # every minus-strand substitution was compared against the wrong
        # reference base and reported as the wrong consequence.
        if (identical(ctx$cds$strand, "-")) {
          out[, `:=`(ref = .annotation_rc_alleles(ref), alt = .annotation_rc_alleles(alt))]
        }
        out[]
      } else {
        # amplicon-frame -> genomic frame
        annotation_variants_to_genomic(ops, frame)
      }
      res <- annotation_haplotype_transcript(hap$sequence[h], structure, frame,
                                             gops, cfg$genetic_code_vector,
                                             with_proteins = isTRUE(include_proteins))
      con <- if (is.na(res$consequence)) {
        if (nrow(ops) == 0) "no_variant" else "outside_cds"
      } else {
        res$consequence
      }
      if (isTRUE(include_detail) && nrow(gops) > 0) {
        d <- annotation_variant_detail(gops, structure, cfg$genetic_code_vector)
        if (!is.null(d) && nrow(d) > 0) {
          d[, haplotype_id := hap$haplotype_id[h]]
          detail_rows[[length(detail_rows) + 1L]] <- d
        }
      }
      rows[[length(rows) + 1L]] <- data.table::data.table(
        haplotype_id = hap$haplotype_id[h],
        count = hap$count[h],
        proportion = hap$proportion[h],
        transcript_id = tid,
        transcript_name = tsel$transcript_name[ti],
        is_mane = isTRUE(tsel$is_mane[ti]),
        is_canonical = isTRUE(tsel$is_canonical[ti]),
        cds_ok = res$cds_ok,
        ref_protein_length = res$ref_protein_length,
        alt_protein_length = res$alt_protein_length,
        n_aa_changed = res$n_aa_changed,
        protein_change = res$protein_change,
        consequence_en = con,
        consequence_zh = consequence_zh(con),
        variants = hap$variants[h] %||% ".",
        signature = hap$signature[h],
        notes = res$notes
      )
      if (isTRUE(include_proteins)) {
        rows[[length(rows)]][, `:=`(ref_protein = res$ref_protein,
                                    alt_protein = res$alt_protein)]
      }
    }
  }

  # One reason string serves both outcomes: with a partial success it says
  # which transcripts were dropped, with a total failure it explains the run.
  skip_reason <- if (length(skipped_tr) > 0L) {
    paste(vapply(skipped_tr, function(x) {
      sprintf("%s (%s)", x$transcript_id, x$problem)
    }, character(1)), collapse = "; ")
  } else {
    NA_character_
  }

  if (length(rows) == 0) {
    reason <- if (is.na(skip_reason)) {
      "no transcript was selected for this amplicon"
    } else {
      skip_reason
    }
    if (!quiet) log_warn("annotation: nothing was annotated - ", reason)
    # Annotation was explicitly requested, so the run must not *look*
    # annotated. The exit code stays 0 (the sequence analysis itself is fine),
    # but qc.tsv and run_manifest.json record that nothing was produced and why.
    return(invisible(list(
      requested = TRUE, available = FALSE, table = NULL,
      candidates = ctx$candidates,
      qc = list(
        annotation_enabled = TRUE,
        annotation_name = cfg$name,
        annotation_route = cfg$route,
        annotation_source = ann_source,
        ensembl_release = chk$release,
        genetic_code = cfg$genetic_code,
        n_transcripts = nrow(tsel),
        n_transcripts_annotated = 0L,
        n_transcripts_skipped = length(skipped_tr),
        annotation_available = FALSE,
        annotation_skip_reason = reason
      ),
      manifest = list(
        enabled = TRUE,
        available = FALSE,
        source = ann_source,
        ensembl_release = chk$release,
        config_path = cfg$config_path %||% NA_character_,
        config = cfg[c("name", "route", "genetic_code", "transcript_id",
                       "transcript_all")],
        genomic = if (is.null(ctx$genomic)) NULL else
          ctx$genomic[c("chrom", "start", "end", "strand", "identity",
                        "n_mismatch", "method")],
        transcripts = manifest_tr,
        skipped_transcripts = skipped_tr
      )
    )))
  }
  out <- data.table::rbindlist(rows, use.names = TRUE, fill = TRUE)
  # Per haplotype: the worst consequence across the selected transcripts.
  out[, consequence_any_transcript := {
    s <- most_severe_consequence(consequence_en)
    if (is.na(s)) NA_character_ else s
  }, by = haplotype_id]
  out[, consequence_any_transcript_zh := consequence_zh(consequence_any_transcript)]
  # Naming kept explicit for downstream readers.
  data.table::setnames(out, "consequence_en", "consequence_en", skip_absent = TRUE)
  out[, transcript_conflict :=
        uniqueN(consequence_en) > 1L, by = haplotype_id]
  data.table::setorder(out, -count, haplotype_id, transcript_id)
  out[, rank := seq_len(.N)]
  qc_extra <- list(
    annotation_enabled = TRUE,
    annotation_name = cfg$name,
    annotation_route = cfg$route,
    annotation_source = ann_source,
    ensembl_release = chk$release,
    genetic_code = cfg$genetic_code,
    n_transcripts = nrow(tsel),
    n_transcripts_annotated = length(manifest_tr),
    n_transcripts_skipped = length(skipped_tr),
    annotation_available = TRUE,
    n_haplotypes_annotated = uniqueN(out$haplotype_id[out$cds_ok == TRUE]),
    n_haplotypes_skipped = uniqueN(out$haplotype_id[is.na(out$cds_ok) | out$cds_ok == FALSE]),
    n_frameshift = sum(out$consequence_any_transcript == "frameshift", na.rm = TRUE),
    n_stop_gained = sum(out$consequence_any_transcript == "stop_gained", na.rm = TRUE),
    n_stop_lost = sum(out$consequence_any_transcript == "stop_lost", na.rm = TRUE),
    n_start_lost = sum(out$consequence_any_transcript == "start_lost", na.rm = TRUE),
    n_missense = sum(out$consequence_any_transcript == "missense", na.rm = TRUE),
    n_synonymous = sum(out$consequence_any_transcript == "synonymous", na.rm = TRUE),
    n_inframe = sum(out$consequence_any_transcript %in%
                      c("inframe_insertion", "inframe_deletion"), na.rm = TRUE),
    n_transcript_conflicts = uniqueN(out$haplotype_id[out$transcript_conflict == TRUE])
  )
  # Only present when something was actually dropped, so a clean run does not
  # carry an empty annotation_skip_reason row in qc.tsv.
  if (length(skipped_tr) > 0L) qc_extra$annotation_skip_reason <- skip_reason
  write_tsv(out, file.path(outdir, "annotation.tsv"))
  if (isTRUE(include_detail) && length(detail_rows) > 0) {
    det <- data.table::rbindlist(detail_rows, use.names = TRUE, fill = TRUE)
    data.table::setcolorder(det, c("haplotype_id", "transcript_id", "type",
                                   "genome_pos", "cds_pos", "ref", "alt",
                                   "codon_ref", "codon_alt", "aa_ref", "aa_alt",
                                   "consequence_en", "consequence_zh"))
    write_tsv(det, file.path(outdir, "variants_annotation.tsv"))
  }
  invisible(list(
    requested = TRUE, available = TRUE, table = out, qc = qc_extra,
    candidates = ctx$candidates,
    manifest = list(
      enabled = TRUE, available = TRUE, source = ann_source,
      ensembl_release = chk$release,
      config_path = cfg$config_path %||% NA_character_,
      config = cfg[c("name", "route", "genetic_code", "transcript_id", "transcript_all")],
      genomic = if (is.null(ctx$genomic)) NULL else ctx$genomic[c("chrom", "start", "end", "strand", "identity", "n_mismatch", "method")],
      transcripts = manifest_tr,
      # Present in both outcomes: a run that annotated 7 of 8 transcripts must
      # not look as if the locus only had 7.
      skipped_transcripts = skipped_tr
    )
  ))
}

# Route "cds": build the same structure shape from the configured coordinates.
.annotation_cds_route_structure <- function(tid, cds_frame, ref_seq) {
  start <- cds_frame$start
  end <- cds_frame$end
  seq <- substr(ref_seq, start, end)
  if (identical(cds_frame$strand, "-")) {
    seq <- as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(seq)))
  }
  frame <- cds_frame$frame
  if (frame > 0L) seq <- substr(seq, frame + 1L, nchar(seq))
  cds <- data.table::data.table(
    chrom = NA_character_, start = start, end = end,
    strand = if (identical(cds_frame$strand, "-")) -1L else 1L,
    phase = frame, protein_id = NA_character_
  )
  problem <- NA_character_
  if (!is.na(seq) && nchar(seq) %% 3L != 0L) {
    problem <- sprintf("CDS length %d is not a multiple of 3 (drop %d bp or fix the frame)",
                       nchar(seq), nchar(seq) %% 3L)
  }
  list(transcript_id = tid, exons = cds, cds = cds, cds_seq = seq,
       ok = is.na(problem), problem = problem,
       chrom = NA_character_, strand = if (identical(cds_frame$strand, "-")) -1L else 1L)
}

# ---------------------------------------------------------------------------
# Mode integration
# ---------------------------------------------------------------------------

#' Annotation entry point used by the analysis modes
#'
#' Returns a list with `available = FALSE` when no config was supplied, so that
#' callers can stay unchanged when annotation is off (the default).
annotation_pass <- function(config_path, ref, hap, variants, outdir,
                            list_only = FALSE, haplotype_id_col = "haplotype_id",
                            quiet = FALSE, include_proteins = FALSE,
                            include_detail = FALSE) {
  if (is.null(config_path) || is.na(config_path) || !nzchar(config_path)) {
    return(list(requested = FALSE, available = FALSE, table = NULL,
                qc = NULL, manifest = NULL))
  }
  cfg <- annotation_config_read(config_path)
  cfg$config_path <- normalizePath(config_path, mustWork = FALSE)

  h <- data.table::as.data.table(hap)
  if (!"haplotype_id" %in% names(h) && haplotype_id_col %in% names(h)) {
    data.table::setnames(h, haplotype_id_col, "haplotype_id")
  }
  if (!"count" %in% names(h)) h[, count := NA_integer_]
  if (!"proportion" %in% names(h)) h[, proportion := NA_real_]
  if (!"variants" %in% names(h)) h[, variants := NA_character_]
  if (!"sequence" %in% names(h) && "consensus" %in% names(h)) {
    data.table::setnames(h, "consensus", "sequence")
  }
  if (!"signature" %in% names(h)) {
    # Mode B does not carry a variant signature; the consensus sequence is
    # annotated through its own diff operations, so an empty signature is used
    # and the haplotype consequence falls back to the protein comparison.
    h[, signature := ""]
  }
  need <- c("haplotype_id", "count", "proportion", "variants", "signature", "sequence")
  missing <- setdiff(need, names(h))
  if (length(missing) > 0) {
    stop(sprintf("annotation: haplotype table lacks column(s): %s",
                 paste(missing, collapse = ", ")), call. = FALSE)
  }
  res <- run_annotation(
    ref_seq = ref$sequence, hap = h, variants = variants,
    outdir = outdir, cfg = cfg, list_only = list_only, quiet = quiet,
    include_proteins = include_proteins, include_detail = include_detail
  )
  res
}
