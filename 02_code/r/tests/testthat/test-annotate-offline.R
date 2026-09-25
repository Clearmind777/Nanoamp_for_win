# Offline functional-annotation tests (cds route).
#
# These run without network by design: the cds route needs no reference
# service, so every annotation invariant that does not involve Ensembl can be
# checked here. Genome-route behaviour (cache, HTTP, rate limiting) is covered
# by the separate tests in test-annotate-online.R.

rc <- function(s) {
  as.character(Biostrings::reverseComplement(Biostrings::DNAStringSet(s)))
}

# A synthetic amplicon with no homopolymer run >= 4, so that nothing here
# depends on how an aligner places indels inside repeats.
synthetic_reference <- function(n = 300L, seed = 42L) {
  set.seed(seed)
  bases <- c("A", "C", "G", "T")
  out <- character(0)
  while (length(out) < n) {
    b <- sample(bases, 1L)
    if (length(out) >= 2L && out[length(out)] == b && out[length(out) - 1L] == b) next
    out <- c(out, b)
  }
  paste(out, collapse = "")
}

write_cfg <- function(path, start, end, strand = "+", extra = list()) {
  cfg <- c(list(name = "test", route = "cds",
                cds = list(start = start, end = end, strand = strand,
                           frame = 0L, boundaries = "inclusive"),
                genetic_code = "Standard"), extra)
  nanoamp:::write_json(cfg, path)
  path
}

make_haps <- function(seqs, variants, signatures) {
  data.table::data.table(
    haplotype_id = sprintf("H%d", seq_along(seqs)),
    count = rep(100L, length(seqs)),
    proportion = rep(1 / length(seqs), length(seqs)),
    variants = variants, signature = signatures, sequence = seqs
  )
}

test_that("the cds route annotates substitutions, a deletion and the reference", {
  R <- synthetic_reference()
  td <- withr::local_tempdir()
  fa <- file.path(td, "ref.fa")
  writeLines(c(">synthetic", R), fa)
  cfg <- write_cfg(file.path(td, "cfg.json"), 40L, 120L)
  out <- file.path(td, "out"); dir.create(out)

  sub_pos <- 50L
  alt <- setdiff(c("A", "C", "G", "T"), strsplit(R, "")[[1]][sub_pos])[1]
  b <- strsplit(R, "")[[1]]
  mut <- paste(c(b[seq_len(sub_pos - 1L)], alt, b[(sub_pos + 1L):length(b)]), collapse = "")
  del_pos <- 62L
  del <- paste(b[-del_pos], collapse = "")

  haps <- make_haps(
    c(R, mut, del), c(".", "sub", "del"),
    c("", sprintf("snv|%d|%s|%s", sub_pos, b[sub_pos], alt),
      sprintf("del|%d|%s|", del_pos, b[del_pos]))
  )
  res <- nanoamp:::annotation_pass(cfg, nanoamp:::read_reference(fa), haps, NULL, out,
                                   quiet = TRUE)
  tbl <- data.table::as.data.table(res$table)
  expect_equal(nrow(tbl), 3L)
  expect_equal(tbl$consequence_en[1], "no_variant")      # exact reference match
  expect_equal(tbl$protein_change[1], "p.(=)")
  expect_equal(tbl$consequence_en[2], "missense")
  expect_equal(tbl$consequence_en[3], "frameshift")
  expect_true(file.exists(file.path(out, "annotation.tsv")))
  expect_equal(res$qc$annotation_source, "cds-config")
  expect_equal(res$qc$annotation_available, TRUE)
  # L10: the offline route has no authoritative protein to compare against, so
  # the manifest must not claim that the reference protein was verified.
  expect_length(res$manifest$transcripts, 1L)
  expect_false(isTRUE(res$manifest$transcripts[[1]]$protein_verified))
  expect_equal(res$manifest$transcripts[[1]]$cds_length, 81L)
})

test_that("a minus-strand cds config mirrors the plus-strand result", {
  # Upstream compared the amplicon alleles against the reverse-complemented CDS
  # without flipping them, so every minus-strand substitution was reported as
  # synonymous. The same molecule viewed from the other strand must give the
  # same consequences.
  R <- synthetic_reference()
  L <- nchar(R)
  td <- withr::local_tempdir()
  plus_fa <- file.path(td, "plus.fa"); minus_fa <- file.path(td, "minus.fa")
  writeLines(c(">plus", R), plus_fa)
  writeLines(c(">minus", rc(R)), minus_fa)
  plus_cfg <- write_cfg(file.path(td, "plus.json"), 40L, 120L, "+")
  minus_cfg <- write_cfg(file.path(td, "minus.json"), L - 120L + 1L, L - 40L + 1L, "-")

  b <- strsplit(R, "")[[1]]
  sub_pos <- 50L
  alt <- setdiff(c("A", "C", "G", "T"), b[sub_pos])[1]
  mut <- paste(c(b[seq_len(sub_pos - 1L)], alt, b[(sub_pos + 1L):length(b)]), collapse = "")
  mpos <- L - sub_pos + 1L
  mb <- rc(b[sub_pos])

  plus_haps <- make_haps(c(R, mut), c(".", "sub"),
                         c("", sprintf("snv|%d|%s|%s", sub_pos, b[sub_pos], alt)))
  minus_haps <- make_haps(c(rc(R), rc(mut)), c(".", "sub"),
                          c("", sprintf("snv|%d|%s|%s", mpos, mb, rc(alt))))

  out_p <- file.path(td, "op"); dir.create(out_p)
  out_m <- file.path(td, "om"); dir.create(out_m)
  tp <- data.table::as.data.table(
    nanoamp:::annotation_pass(plus_cfg, nanoamp:::read_reference(plus_fa),
                              plus_haps, NULL, out_p, quiet = TRUE)$table)
  tm <- data.table::as.data.table(
    nanoamp:::annotation_pass(minus_cfg, nanoamp:::read_reference(minus_fa),
                              minus_haps, NULL, out_m, quiet = TRUE)$table)
  expect_equal(tm$consequence_en, tp$consequence_en)
  expect_equal(tm$protein_change, tp$protein_change)
  expect_equal(tm$consequence_en[2], "missense")   # not the upstream "synonymous"
})

test_that("a CDS whose length is not a multiple of 3 is skipped and recorded", {
  R <- synthetic_reference()
  td <- withr::local_tempdir()
  fa <- file.path(td, "ref.fa"); writeLines(c(">synthetic", R), fa)
  # 82 bp: 40..121 is deliberately not a multiple of three
  cfg <- write_cfg(file.path(td, "bad.json"), 40L, 121L)
  out <- file.path(td, "out"); dir.create(out)
  haps <- make_haps(R, ".", "")
  res <- nanoamp:::annotation_pass(cfg, nanoamp:::read_reference(fa), haps, NULL, out,
                                   quiet = TRUE)
  expect_false(isTRUE(res$available))
  expect_false(file.exists(file.path(out, "annotation.tsv")))
  expect_equal(res$qc$annotation_available, FALSE)
  expect_match(res$qc$annotation_skip_reason, "multiple of 3")
  expect_true(length(res$manifest$skipped_transcripts) >= 1L)
})

test_that("an invalid annotation config is rejected with a reason", {
  td <- withr::local_tempdir()
  bad <- file.path(td, "bad.json")
  writeLines('{"route": "cds", "cds": {"strand": "*"}}', bad)
  expect_error(nanoamp:::annotation_config_read(bad), "strand")
  writeLines('{"route": "nonsense"}', file.path(td, "route.json"))
  expect_error(nanoamp:::annotation_config_read(file.path(td, "route.json")))
})

test_that("no annotation config leaves the outputs untouched", {
  R <- synthetic_reference()
  td <- withr::local_tempdir()
  fa <- file.path(td, "ref.fa"); writeLines(c(">synthetic", R), fa)
  out <- file.path(td, "out"); dir.create(out)
  haps <- make_haps(R, ".", "")
  res <- nanoamp:::annotation_pass(NULL, nanoamp:::read_reference(fa), haps, NULL, out)
  expect_false(isTRUE(res$requested))
  expect_null(res$table)
  expect_false(file.exists(file.path(out, "annotation.tsv")))
})

test_that("the bundled example configs are usable", {
  cfg_dir <- system.file("configs", package = "nanoamp")
  expect_true(nzchar(cfg_dir) && dir.exists(cfg_dir))
  online <- nanoamp:::annotation_config_read(file.path(cfg_dir, "example_online.json"))
  expect_equal(online$route, "genome")
  cds <- nanoamp:::annotation_config_read(file.path(cfg_dir, "example_cds.json"))
  expect_equal(cds$route, "cds")
  # the bundled example must describe a translatable CDS
  len <- as.integer(cds$cds$end) - as.integer(cds$cds$start) + 1L
  expect_equal(len %% 3L, 0L)
})

test_that("the candidate table (transcripts.tsv) is machine-readable", {
  # `--list-transcripts` prints a human table and writes this one; the GUI builds
  # its transcript picker from the file, so the shape is part of the contract.
  ctx <- list(
    genomic = list(chrom = "19", start = 100L, end = 200L, strand = "+"),
    candidates = data.table::data.table(
      transcript_id = c("ENST1", "ENST2"),
      transcript_name = c("A", NA_character_),
      biotype = c("protein_coding", "lncRNA"),
      is_mane = c(TRUE, FALSE), is_canonical = c(TRUE, FALSE),
      cds_overlap_bp = c(50L, NA_integer_)
    )
  )
  t <- nanoamp:::annotation_candidates_table(ctx)
  expect_equal(t$transcript_id, c("ENST1", "ENST2"))
  expect_equal(t$name, c("A", "-"))
  expect_equal(t$mane, c("MANE", ""))
  expect_equal(t$canonical, c("canonical", ""))
  expect_equal(t$chrom, c("19", "19"))
  expect_equal(t$start, c(100L, 100L))
  expect_equal(t$strand, c("+", "+"))

  # An amplicon with no overlapping transcript must still produce the same
  # columns, so the GUI never has to special-case an empty file.
  empty <- nanoamp:::annotation_candidates_table(
    list(genomic = NULL, candidates = NULL))
  expect_equal(nrow(empty), 0L)
  expect_true(all(c("transcript_id", "name", "biotype", "mane", "canonical",
                    "chrom", "start", "end", "strand", "cds_overlap_bp") %in%
                    names(empty)))
})

test_that("write_tsv keeps embedded newlines out of a machine-read table", {
  df <- data.frame(metric = c("a", "b"), value = c("one\ntwo", "x\ty"),
                   stringsAsFactors = FALSE)
  p <- file.path(withr::local_tempdir(), "t.tsv")
  nanoamp:::write_tsv(df, p)
  expect_equal(length(readLines(p, warn = FALSE)), 3L)
  back <- data.table::fread(p, sep = "\t", header = TRUE)
  expect_equal(nrow(back), 2L)
  expect_equal(back$value, c("one two", "x y"))
})
