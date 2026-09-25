# FASTQ input is read by the package itself (no ShortRead), so the reader needs
# its own contract: what it accepts, what it rejects, and what it returns.
# ShortRead was dropped because it unconditionally imports pwalign, which forced
# every installation to provide pairwiseAlignment() even though only
# aligner = "r" and the Mode B consensus annotation ever use it.

rec <- function(id, seq, qual = NULL) {
  if (is.null(qual)) qual <- strrep("I", nchar(seq))
  c(paste0("@", id), seq, "+", qual)
}

test_that("read_fastq returns ids without '@', upper-case sequences and qualities", {
  path <- file.path(withr::local_tempdir(), "reads.fastq")
  writeLines(c(rec("read1 desc", "acgtACGT"), rec("read2", "TTTT")), path)
  fq <- nanoamp:::read_fastq(path)
  expect_equal(fq$read_id, c("read1 desc", "read2"))
  expect_equal(fq$sequence, c("ACGTACGT", "TTTT"))
  expect_equal(fq$quality, c("IIIIIIII", "IIII"))
  expect_equal(nanoamp:::count_fastq_reads(path), 2L)
})

test_that("gzip is detected by extension and by content", {
  td <- withr::local_tempdir()
  plain <- file.path(td, "reads.fastq")
  writeLines(c(rec("r1", "ACGT"), rec("r2", "GGCC")), plain)

  by_ext <- file.path(td, "reads.fastq.gz")
  con <- gzfile(by_ext, "wt"); writeLines(readLines(plain), con); close(con)
  # same bytes, but the file name says nothing about gzip
  by_magic <- file.path(td, "reads.bin")
  file.copy(by_ext, by_magic)

  for (path in c(by_ext, by_magic)) {
    fq <- nanoamp:::read_fastq(path)
    expect_equal(fq$read_id, c("r1", "r2"), info = basename(path))
    expect_equal(nanoamp:::count_fastq_reads(path), 2L, info = basename(path))
  }
})

test_that("a malformed FASTQ is rejected instead of silently mis-parsed", {
  td <- withr::local_tempdir()
  # wrapped (multi-line) records: 5 lines, not a multiple of 4
  bad1 <- file.path(td, "wrapped.fastq")
  writeLines(c("@r1", "ACGT", "ACGT", "+", "IIII", "IIII"), bad1)
  expect_error(nanoamp:::read_fastq(bad1), "multiple of 4")
  expect_error(nanoamp:::count_fastq_reads(bad1), "multiple of 4")

  # a record whose header does not start with '@'
  bad2 <- file.path(td, "noat.fastq")
  writeLines(c("r1", "ACGT", "+", "IIII"), bad2)
  expect_error(nanoamp:::read_fastq(bad2), "Malformed FASTQ")

  # a record whose separator does not start with '+'
  bad3 <- file.path(td, "noplus.fastq")
  writeLines(c("@r1", "ACGT", "=", "IIII"), bad3)
  expect_error(nanoamp:::read_fastq(bad3), "Malformed FASTQ")
})

test_that("an empty FASTQ is an empty table, not an error", {
  path <- file.path(withr::local_tempdir(), "empty.fastq")
  file.create(path)
  fq <- nanoamp:::read_fastq(path)
  expect_equal(nrow(fq), 0L)
  expect_equal(names(fq), c("read_id", "sequence", "quality"))
  expect_equal(nanoamp:::count_fastq_reads(path), 0L)
})

test_that("block-wise reading sees every record", {
  td <- withr::local_tempdir()
  path <- file.path(td, "many.fastq")
  n <- 7L
  lines <- unlist(lapply(seq_len(n), function(i) rec(sprintf("r%d", i), "ACGTACGT")))
  writeLines(lines, path)
  fq <- nanoamp:::read_fastq_records(path, block = 2L)
  expect_equal(length(fq$id), n)
  expect_equal(fq$id[1], "@r1")
  expect_equal(fq$id[n], sprintf("@r%d", n))
  expect_equal(nanoamp:::count_fastq_reads(path, block = 2L), n)
})

test_that("a missing FASTQ is reported before anything else happens", {
  expect_error(nanoamp:::read_fastq(file.path(tempdir(), "nope.fastq")),
               "FASTQ file not found")
  expect_error(nanoamp:::count_fastq_reads(file.path(tempdir(), "nope.fastq")),
               "FASTQ file not found")
})

test_that("the package no longer imports ShortRead", {
  # The dependency is what pulled pwalign into every installation; a silent
  # regression here would undo the whole point of the port.
  imports <- utils::packageDescription("nanoamp")$Imports
  expect_false(grepl("ShortRead", imports, fixed = TRUE))
})
