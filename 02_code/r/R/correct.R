# ---------------------------------------------------------------------------
# Mode A: reference-guided correction and haplotype counting
# ---------------------------------------------------------------------------

empty_ops <- function() {
  data.table::data.table(
    type = character(0), pos = integer(0),
    ref = character(0), alt = character(0)
  )
}

signature_to_ops <- function(signature) {
  if (is.na(signature) || !nzchar(signature)) return(empty_ops())
  keys <- strsplit(signature, ";", fixed = TRUE)[[1]]
  parts <- strsplit(keys, "|", fixed = TRUE)
  data.table::data.table(
    type = vapply(parts, `[`, character(1), 1),
    pos = as.integer(vapply(parts, `[`, character(1), 2)),
    ref = vapply(parts, `[`, character(1), 3),
    alt = vapply(parts, `[`, character(1), 4)
  )
}

apply_variants <- function(ref_seq, ops) {
  if (is.null(ops) || nrow(ops) == 0) return(ref_seq)
  ops <- data.table::as.data.table(ops)
  ops <- ops[order(pos, match(type, c("snv", "del", "ins")))]
  out <- character(0)
  cursor <- 1L
  L <- nchar(ref_seq)
  for (i in seq_len(nrow(ops))) {
    p <- as.integer(ops$pos[i])
    type <- ops$type[i]
    r <- ops$ref[i]
    a <- ops$alt[i]
    if (type == "ins") {
      p <- max(p, 0L)
      if (p >= cursor) out <- c(out, substr(ref_seq, cursor, p))
      out <- c(out, a)
      cursor <- p + 1L
    } else {
      if (p > cursor) out <- c(out, substr(ref_seq, cursor, p - 1L))
      out <- c(out, a)
      cursor <- p + nchar(r)
    }
  }
  if (cursor <= L) out <- c(out, substr(ref_seq, cursor, L))
  paste0(out, collapse = "")
}

wilson_ci <- function(k, n, z = 1.96) {
  if (n <= 0) return(c(low = NA_real_, high = NA_real_))
  p <- k / n
  denom <- 1 + z^2 / n
  centre <- (p + z^2 / (2 * n)) / denom
  half <- z * sqrt(p * (1 - p) / n + z^2 / (4 * n^2)) / denom
  c(low = max(0, centre - half), high = min(1, centre + half))
}

build_haplotype_table <- function(counts, ref_seq) {
  n_total <- sum(counts$count)
  rows <- lapply(seq_len(nrow(counts)), function(i) {
    sig <- counts$signature[i]
    ops <- signature_to_ops(sig)
    seq <- apply_variants(ref_seq, ops)
    ci <- wilson_ci(counts$count[i], n_total)
    data.table::data.table(
      rank = i,
      haplotype_id = sprintf("H%d", i),
      count = counts$count[i],
      proportion = counts$count[i] / n_total,
      ci_low = ci[["low"]],
      ci_high = ci[["high"]],
      is_reference = !nzchar(sig),
      n_snv = sum(ops$type == "snv"),
      n_ins = sum(ops$type == "ins"),
      n_del = sum(ops$type %in% c("del", "delregion")),
      length = nchar(seq),
      variants = if (nrow(ops) == 0) "." else paste(
        format_op(ops$type, ops$pos, ops$ref, ops$alt), collapse = ";"
      ),
      signature = sig,
      sequence = seq
    )
  })
  data.table::rbindlist(rows, use.names = TRUE)
}

build_qc_table <- function(values) {
  data.table::data.table(
    metric = names(values),
    value = vapply(values, function(x) as.character(x)[1], character(1))
  )
}

run_manifest <- function(outdir, mode, params, reference, qc, extra = list(),
                         status = "done") {
  info <- list(
    nanoamp_version = nanoamp_version(),
    mode = mode,
    # `status` is "done" for a completed run; a failed run gets its own manifest
    # from write_failure_manifest() so a failure is never indistinguishable from
    # a run that produced nothing.
    status = status,
    timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S %z"),
    r_version = R.version.string,
    log_path = log_current_path(),
    reference = list(
      name = reference$name,
      length = reference$length,
      md5 = reference$md5,
      path = reference$path
    ),
    params = params,
    qc = qc
  )
  if (length(extra) > 0) info <- c(info, extra)
  write_json(info, file.path(outdir, "run_manifest.json"))
  invisible(info)
}

# Written when an analysis raises an error, so that the output directory of a
# failed run still answers "what happened?" - both for a human and for the GUI,
# which reads `error_class` to choose its hint. Never masks the original error:
# the caller rethrows it, keeping the exit code at 1.
write_failure_manifest <- function(outdir, mode, error) {
  info <- list(
    nanoamp_version = nanoamp_version(),
    mode = mode,
    status = "failed",
    timestamp = format(Sys.time(), "%Y-%m-%d %H:%M:%S %z"),
    r_version = R.version.string,
    log_path = log_current_path(),
    error_class = error_class_of(error),
    error_message = conditionMessage(error)
  )
  try({
    dir.create(outdir, recursive = TRUE, showWarnings = FALSE)
    write_json(info, file.path(outdir, "run_manifest.json"))
  }, silent = TRUE)
  invisible(info)
}

# Does the annotation part of the run have something the caller must know
# about? Returns a reason string, or NULL when annotation either was not
# requested or completed in full.
#
# Two outcomes count as degraded: some transcripts were dropped (partial
# success) and nothing could be annotated at all (`available = FALSE`). Both are
# already recorded in qc.tsv and in the manifest's annotation section; --strict
# is what turns them into a failure for a pipeline.
annotation_degradation <- function(ann) {
  if (is.null(ann) || !isTRUE(ann$requested)) return(NULL)
  skipped <- ann$qc$n_transcripts_skipped %||% 0L
  if (isTRUE(skipped > 0L) || !isTRUE(ann$available)) {
    reason <- ann$qc$annotation_skip_reason %||%
      sprintf("%s transcript(s) could not be annotated", as.integer(skipped))
    return(as.character(reason)[1])
  }
  NULL
}

# The manifest of a strict run whose annotation was degraded must not claim
# "done": the caller is about to exit non-zero. `error_class` is a heuristic on
# the recorded reason (network vs. input), which is all that is known here.
strict_manifest_fields <- function(degraded, strict) {
  if (!isTRUE(strict) || is.null(degraded)) return(list())
  list(error_class = error_class_of(simpleError(degraded)),
       error_message = degraded)
}

run_mode_a <- function(reads_path, reference_path, outdir,
                       top_n = 20L,
                       min_reads = 3L, min_freq = 0.02,
                       min_identity = 0.90, min_ref_coverage = 0.90,
                       homopolymer = 4L, strand_bias = 0.90,
                       aligner = c("minimap2", "r"), use_samtools = FALSE,
                       threads = 4L, keep_intermediates = TRUE,
                       ref_label = NULL, annotation = NULL,
                       list_transcripts = FALSE, annotation_proteins = FALSE,
                       annotation_detail = FALSE, strict = FALSE) {
  aligner <- match.arg(aligner, c("minimap2", "r"))
  outdir <- ensure_dir(outdir)
  ref <- read_reference(reference_path)
  n_total <- count_fastq_reads(reads_path)
  # An empty FASTQ is an input problem, and saying so is far more useful than
  # the "no aligned reads" that the aligner would produce a moment later.
  if (n_total == 0L) {
    nanoamp_abort(sprintf("FASTQ file contains no reads: %s", reads_path),
                  class = "input")
  }
  log_info("Mode A: ", basename(reads_path), " -> ", ref$name, " (", n_total, " reads)")

  prep <- prepare_alignment_data(
    reads_path, reference_path, outdir,
    aligner = aligner, threads = threads, use_samtools = use_samtools
  )
  aln <- prep$aln
  n_primary <- nrow(aln)
  if (n_primary == 0) {
    nanoamp_abort(paste0(
      "Mode A: no aligned reads.\n",
      "Nothing in this FASTQ aligns to the reference. Check that the FASTQ and\n",
      "the reference belong to the same sample/amplicon."
    ), class = "input")
  }

  kept <- filter_alignment_reads(aln, min_identity, min_ref_coverage)
  if (nrow(kept) == 0) {
    nanoamp_abort(paste0(
      "Mode A: no reads left after filtering (min_identity / min_ref_coverage).\n",
      "The reads align but none of them pass the quality thresholds."
    ), class = "input")
  }
  log_info("Mode A: kept ", nrow(kept), "/", n_primary, " aligned reads")

  disc <- discover_variants(
    kept, ref$sequence,
    min_reads = min_reads, min_freq = min_freq,
    homopolymer = homopolymer, strand_bias = strand_bias,
    read_vars = prep$read_vars
  )
  read_vars <- disc$read_vars
  retained <- if (nrow(read_vars) > 0) {
    read_vars[key %in% disc$pass_keys]
  } else {
    read_vars
  }

  read_sig <- data.table::data.table(read_id = kept$read_id)
  if (nrow(retained) > 0) {
    sig <- retained[, .(signature = paste(sort(unique(key)), collapse = ";")), by = read_id]
    read_sig <- sig[read_sig, on = "read_id"]
    read_sig[is.na(signature), signature := ""]
  } else {
    read_sig[, signature := ""]
  }
  counts <- read_sig[, .(count = .N), by = signature][order(-count, signature)]
  hap <- build_haplotype_table(counts, ref$sequence)

  variants_tbl <- variants_to_company_table(disc$variants, ref$name)
  write_tsv(hap[, .(rank, haplotype_id, count, proportion, ci_low, ci_high,
                    is_reference, n_snv, n_ins, n_del, length, variants, signature)],
            file.path(outdir, "haplotypes.tsv"))
  top <- utils::head(hap, top_n)
  write_fasta(stats::setNames(top$sequence, sprintf("%s_%s", top$haplotype_id, top$variants)),
              file.path(outdir, "haplotypes.fasta"))
  write_tsv(variants_tbl, file.path(outdir, "variants.tsv"))

  qc <- list(
    mode = "A",
    aligner = aligner,
    # Which package supplied pairwiseAlignment(); only used by aligner = "r".
    pairwise_provider = if (identical(aligner, "r")) pa_provider_name() else NA_character_,
    reference_label = ref_label %||% ref$name,
    reference_length = ref$length,
    n_reads_total = n_total,
    n_reads_primary = n_primary,
    n_reads_used = nrow(kept),
    mapping_rate = round(n_primary / max(n_total, 1), 6),
    mean_identity = round(mean(kept$identity), 6),
    mean_coverage = round(sum(kept$ref_span) / ref$length, 4),
    n_raw_variants = disc$qc_extra$n_raw_variants,
    n_pass_variants = length(disc$pass_keys),
    n_haplotypes = nrow(hap),
    top1_proportion = round(hap$proportion[1], 6),
    top1_is_reference = hap$is_reference[1],
    exact_reference_proportion = round(hap[is_reference == TRUE, sum(proportion)], 6)
  )
  ann <- annotation_pass(annotation, ref, hap, disc$variants, outdir,
                         list_only = list_transcripts,
                         include_proteins = annotation_proteins,
                         include_detail = annotation_detail)
  # ann$qc is present whenever a config was supplied, including when annotation
  # was requested but produced nothing (the skip reason must reach qc.tsv).
  if (!is.null(ann$qc)) qc <- c(qc, ann$qc)
  write_tsv(build_qc_table(qc), file.path(outdir, "qc.tsv"))
  degraded <- annotation_degradation(ann)
  strict_fields <- strict_manifest_fields(degraded, strict)
  run_manifest(outdir, "A", list(
    top_n = top_n, min_reads = min_reads, min_freq = min_freq,
    min_identity = min_identity, min_ref_coverage = min_ref_coverage,
    homopolymer = homopolymer, strand_bias = strand_bias,
    aligner = aligner, threads = threads
  ), ref, qc,
  status = if (length(strict_fields) > 0L) "failed" else "done",
  extra = c(list(reads_md5 = safe_md5(reads_path)),
            if (!is.null(ann$manifest)) list(annotation = ann$manifest),
            strict_fields))

  if (!isTRUE(keep_intermediates) && !is.null(prep$bam)) {
    unlink(c(prep$bam, paste0(prep$bam, ".bai"), paste0(prep$bam, ".minimap2.log")))
  }
  invisible(list(haplotypes = hap, variants = variants_tbl, qc = qc,
                 annotation = ann$table,
                 # Only set when --strict was asked for and annotation was
                 # degraded; the CLI turns it into a non-zero exit code.
                 strict_failure = if (isTRUE(strict)) degraded else NULL))
}
