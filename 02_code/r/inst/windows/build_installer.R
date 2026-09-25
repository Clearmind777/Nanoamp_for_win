# ---------------------------------------------------------------------------
# Skeleton: build a Windows installer for the nanoamp Shiny GUI with RInno.
# Run this on a Windows machine with Rtools and RInno installed.
# ---------------------------------------------------------------------------

if (!requireNamespace("RInno", quietly = TRUE)) {
  stop("Install RInno first: install.packages('RInno')", call. = FALSE)
}

app_dir <- system.file("shiny", package = "nanoamp")
if (!nzchar(app_dir)) {
  stop("Could not find inst/shiny in the installed nanoamp package.", call. = FALSE)
}

pkgs <- c(
  "shiny", "DT",
  "Biostrings", "IRanges", "Matrix", "Rsamtools",
  "data.table", "optparse", "jsonlite", "readxl"
)

RInno::create_app(
  app_name = "nanoamp",
  app_dir = app_dir,
  pkgs = pkgs,
  include_R = TRUE,
  R_version = paste(R.version$major, R.version$minor, sep = "."),
  user_browser = "default",
  app_repo_url = "https://example.invalid/nanoamp"
)

# After create_app() succeeds, build the installer:
# RInno::compile_iss()

cat("RInno project created. Review the generated configuration, then run RInno::compile_iss().\n")
