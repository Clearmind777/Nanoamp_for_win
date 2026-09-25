# Silence R CMD check notes for data.table non-standard evaluation.
utils::globalVariables(c(
  ".", ".I", ".N", ".SD",
  "alt", "ci_high", "ci_low", "cluster", "cluster_id", "count",
  "dp", "dp_minus", "dp_plus", "end", "Filter_Reason", "Filter_Status",
  "freq", "hp_run", "iend", "istart", "key", "len", "minus", "n_snv",
  "n_ins", "n_del", "ov", "passed_filter", "plus", "pos", "proportion",
  "rank", "ref", "ref_fwd", "ref_rev", "region_key", "sample_read_id",
  "Seq", "signature", "start", "support", "type",
  "cs", "DP4", "flag", "haplotype_id", "is_reference", "nm", "read_id",
  "ref_cov", "ref_end", "ref_span", "ref_start", "strand", "variants",
  # functional annotation (R/annotate.R, R/annotate_config.R)
  "cds_overlap_bp", "transcript_id", "transcript_name", "is_mane", "is_canonical",
  "genome_pos", "cds_pos", "consequence_en", "consequence_any_transcript",
  "consequence_any_transcript_zh", "transcript_conflict", "anchor_coverage",
  "protein_id", "bp", "label", "chrom", "alt_protein", "ref_protein"
))

# ---------------------------------------------------------------------------
# Pairwise alignment provider.
#
# Bioconductor 3.19 moved pairwiseAlignment(), pattern(), subject(), aligned()
# and score() out of Biostrings into the pwalign package.
#
# Three Biostrings generations have to be supported:
#   1. old (< 2.77): pairwiseAlignment() lives in Biostrings and works;
#   2. middle: the symbol is not exported any more ("not an exported object");
#   3. current (>= 2.77.1): the symbol is *still exported* but is defunct and
#      aborts at call time with
#        "pairwiseAlignment() has moved from Biostrings to the pwalign package"
#
# Because of generation 3 a test of the form
#   "pairwiseAlignment" %in% getNamespaceExports("Biostrings")
# is not sufficient, and it silently selected the defunct Biostrings version on
# Bioconductor >= 3.19. Prefer pwalign whenever it is installed; that is correct
# for generations 2 and 3, and harmless for generation 1.
#
# The provider is resolved lazily, on first call, and cached. Only
# aligner = "r" and the Mode B consensus annotation use it, so a package
# without a usable provider must still load and must still run the default
# minimap2 workflow; the error belongs at the call site that actually needs
# pairwise alignment, not at library().
# ---------------------------------------------------------------------------
.pa_env <- new.env(parent = emptyenv())
.pa_optional_package <- "pwalign"
.pa_fns <- c("pairwiseAlignment", "pattern", "subject", "aligned", "score")

.pa_exported <- function(ns, fn) {
  # A symbol can be exported yet not defined in the namespace when it is
  # re-exported from a dependency (Biostrings 2.66 re-exports the IRanges /
  # S4Vectors generics `subject()` and `score()`). Asking for the exported
  # value directly accepts those re-exports and still rejects symbols that are
  # not available from the namespace at all.
  is.function(tryCatch(getExportedValue(ns, fn), error = function(e) NULL))
}

.pa_resolve <- function() {
  if (requireNamespace(.pa_optional_package, quietly = TRUE)) {
    return(asNamespace(.pa_optional_package))
  }
  bs <- asNamespace("Biostrings")
  if (all(vapply(.pa_fns, .pa_exported, logical(1), ns = bs))) {
    return(bs)
  }
  stop(
    "Pairwise alignment is unavailable: this Biostrings build no longer ",
    "provides pairwiseAlignment() and the 'pwalign' package is not installed.\n",
    "Install it with: BiocManager::install(\"pwalign\")",
    call. = FALSE
  )
}

.pa_provider <- function() {
  if (is.null(.pa_env$namespace)) {
    prov <- .pa_resolve()
    .pa_env$namespace <- prov
    .pa_env$provider <- environmentName(prov)
  }
  .pa_env$namespace
}

.pa_fn <- function(name) getExportedValue(.pa_provider(), name)

pa_pairwise_alignment <- function(...) .pa_fn("pairwiseAlignment")(...)
pa_pattern <- function(x) .pa_fn("pattern")(x)
pa_subject <- function(x) .pa_fn("subject")(x)
pa_aligned <- function(x) .pa_fn("aligned")(x)
pa_score <- function(x) .pa_fn("score")(x)

# NA until pairwise alignment is actually used, so that QC output does not
# force a resolution (and cannot fail) on minimap2-only runs.
pa_provider_name <- function() .pa_env$provider %||% NA_character_

