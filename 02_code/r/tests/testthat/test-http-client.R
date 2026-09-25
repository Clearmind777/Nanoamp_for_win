# The HTTP client must return the body byte-for-byte.
#
# R's `system2(..., stdout = TRUE)` inserts line breaks into very long captured
# lines (measured: a 39,893-character Ensembl JSON response came back as 39,897
# characters on 5 lines, splitting tokens such as "GRCh38"), which corrupted
# every large single-line response until the body was written to a file instead.
# These tests need no network: curl can read a file:// URL.

test_that("a large single-line body survives the HTTP client unchanged", {
  skip_on_os("linux")   # the bug is R's pipe capture on Windows; see below
  body <- paste0("[", paste(rep('{"a":"GRCh38_havana_tagene"}', 1400),
                            collapse = ","), "]")
  expect_gt(nchar(body), 30000)
  td <- withr::local_tempdir()
  path <- file.path(td, "body.json")
  writeLines(body, path)          # one very long line
  url <- paste0("file:///", gsub("\\\\", "/", path))

  txt <- nanoamp:::.http_get_once(url)
  expect_equal(nchar(txt), nchar(body))
  expect_equal(length(strsplit(txt, "\n")[[1]]), 1L)
  expect_silent(jsonlite::fromJSON(txt, simplifyVector = FALSE))
})

test_that("the HTTP client reports the client it will use", {
  client <- nanoamp:::annotation_http_client()
  expect_true(client %in% c("curl", "r"))
  if (nzchar(Sys.which("curl"))) {
    expect_equal(client, "curl")
  } else {
    expect_equal(client, "r")
  }
})

test_that("the R fallback client reads a large body too", {
  body <- paste0("[", paste(rep('{"a":"GRCh38"}', 2000), collapse = ","), "]")
  td <- withr::local_tempdir()
  path <- file.path(td, "body.json")
  writeLines(body, path)
  url <- paste0("file:///", gsub("\\\\", "/", path))
  txt <- nanoamp:::.http_get_r(url)
  expect_equal(nchar(txt), nchar(body))
  expect_silent(jsonlite::fromJSON(txt, simplifyVector = FALSE))
})
