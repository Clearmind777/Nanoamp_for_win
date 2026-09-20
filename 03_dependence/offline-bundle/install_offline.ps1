#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Install R and every nanoamp dependency on a machine with NO network,
    using the bundle produced by fetch_offline_bundle.R.

.DESCRIPTION
    Steps:
      1. verify every bundled file against SHA256SUMS.txt
      2. install R silently, current-user only (no administrator rights)
      3. install all 90 R package binaries from the bundle's local repository
      4. install the nanoamp package itself and run the bundled test suite

    No conda, no WSL, and no network access is required or used.

.PARAMETER BundleDir
    The bundle directory. Default: <repo>/dist
.PARAMETER RDir
    Where to install R. Default: D:\tools\R
.PARAMETER RLib
    R library for the packages. Default: <RDir>\lib
.PARAMETER SkipVerify
    Skip the SHA256 verification step.

.EXAMPLE
    pwsh -File 03_dependence/offline-bundle/install_offline.ps1
#>
[CmdletBinding()]
param(
  [string]$BundleDir,
  [string]$RDir = 'D:\tools\R',
  [string]$RLib,
  [switch]$SkipVerify
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Say($m)  { Write-Host "==> $m" -ForegroundColor Cyan }
function Ok($m)   { Write-Host "    $m" -ForegroundColor Green }
function Warn2($m){ Write-Host "    $m" -ForegroundColor Yellow }

# --- locate bundle and repo ------------------------------------------------
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = (Resolve-Path (Join-Path $scriptDir '..\..')).Path
if (-not $BundleDir) { $BundleDir = Join-Path $repoRoot 'dist' }
if (-not (Test-Path $BundleDir)) {
  throw "bundle not found: $BundleDir`nBuild it with: Rscript 03_dependence/offline-bundle/fetch_offline_bundle.R"
}
if (-not $RLib) { $RLib = Join-Path $RDir 'lib' }
$pkgDir = Join-Path $BundleDir 'r-packages'

Say "bundle  : $BundleDir"
Say "R dir   : $RDir"
Say "R lib   : $RLib"

# --- 1. verify -------------------------------------------------------------
if (-not $SkipVerify) {
  Say "Verifying SHA256SUMS.txt"
  $sumsFile = Join-Path $BundleDir 'SHA256SUMS.txt'
  if (-not (Test-Path $sumsFile)) { throw "missing $sumsFile" }
  $bad = 0; $n = 0
  foreach ($line in Get-Content $sumsFile) {
    if ($line -notmatch '^([0-9a-fA-F]{64})\s+(.+)$') { continue }
    $expected = $Matches[1].ToLower()
    $rel = $Matches[2].Trim()
    # Paths are relative and use forward slashes; normalise for Windows.
    # (An absolute path would also be tolerated, but then it would not be
    # portable, which is why the generator writes relative paths.)
    if ([System.IO.Path]::IsPathRooted($rel)) { $file = $rel }
    else { $file = Join-Path $BundleDir ($rel -replace '/', '\') }
    $n++
    if (-not (Test-Path -LiteralPath $file)) { Warn2 "MISSING $rel"; $bad++; continue }
    $actual = (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash.ToLower()
    if ($actual -ne $expected) { Warn2 "MISMATCH $rel"; $bad++ }
  }
  if ($bad -gt 0) { throw "$bad of $n files failed verification" }
  Ok "$n files verified"
} else {
  Warn2 "verification skipped"
}

# --- 2. install R ----------------------------------------------------------
# Accept either an installation root (D:\tools\R containing R-4.6.1\) or an
# R home directly (D:\tools\R\R-4.6.1).
function Get-RHome([string]$root) {
  if (Test-Path (Join-Path $root 'bin\Rscript.exe')) { return (Resolve-Path $root).Path }
  $sub = Get-ChildItem $root -Directory -ErrorAction SilentlyContinue |
    Where-Object { Test-Path (Join-Path $_.FullName 'bin\Rscript.exe') } |
    Select-Object -First 1
  if ($sub) { return $sub.FullName }
  return $null
}

$rExe = Get-ChildItem $BundleDir -Filter 'R-*-win.exe' | Select-Object -First 1
if (-not $rExe) { throw "R installer not found in $BundleDir" }
$rHome = $null
if (Test-Path $RDir) { $rHome = Get-RHome $RDir }
if ($rHome) {
  Say "R already installed: $rHome"
} else {
  Say "Installing $($rExe.Name) (current user, silent)"
  New-Item -ItemType Directory -Force -Path $RDir | Out-Null
  # BaseName looks like "R-4.6.1-win"; strip the trailing "-win" for the folder.
  $ver = $rExe.BaseName -replace '-win$', ''
  $target = Join-Path $RDir $ver
  $p = Start-Process -FilePath $rExe.FullName -Wait -PassThru -ArgumentList @(
    '/VERYSILENT', '/NORESTART', '/CURRENTUSER', "/DIR=$target"
  )
  if ($p.ExitCode -ne 0) { throw "R installer exited with $($p.ExitCode)" }
  $rHome = Get-RHome $RDir
  if (-not $rHome) { throw "R installation not found under $RDir" }
  Ok $rHome
}
$rscript = Join-Path $rHome 'bin\Rscript.exe'
$rexec   = Join-Path $rHome 'bin\R.exe'

# --- 3. install packages from the local repository -------------------------
New-Item -ItemType Directory -Force -Path $RLib | Out-Null
Say "Installing R packages from the local repository"
$localRepo = 'file:///' + ($pkgDir -replace '\\', '/')
$installScript = Join-Path $env:TEMP 'nanoamp_offline_pkgs.R'
# NOTE: use repos= (not contriburl=). For a local repository root the two
# differ: repos= resolves <root>/bin/windows/contrib/<rver>/PACKAGES, while
# contriburl= would look for <root>/PACKAGES.
@"
.libPaths(c('$($RLib -replace '\\','/')', .libPaths()))
options(repos = c(CRAN = '$localRepo'), download.file.method = 'libcurl', timeout = 3600)
ap <- available.packages(repos = '$localRepo', type = 'win.binary')
cat('local repository packages:', nrow(ap), '\n')
if (!nrow(ap)) stop('local repository index is empty: $localRepo')
want <- c('BiocManager','data.table','jsonlite','optparse','readxl','testthat',
          'pkgload','Biostrings','IRanges','Rsamtools','ShortRead','pwalign',
          'DECIPHER','shiny','DT')
missing <- setdiff(want, rownames(ap))
if (length(missing)) cat('NOT IN BUNDLE:', paste(missing, collapse=', '), '\n')
# install the whole bundled closure so nothing is missing at load time
utils::install.packages(rownames(ap), lib = '$($RLib -replace '\\','/')',
                        repos = '$localRepo', type = 'win.binary',
                        dependencies = TRUE, quiet = FALSE)
cat('\n=== installed ===\n')
for (p in want) {
  v <- tryCatch(as.character(utils::packageVersion(p)), error = function(e) NA_character_)
  cat(sprintf('%-14s %s\n', p, ifelse(is.na(v), '<MISSING>', v)))
}
"@ | Set-Content -Path $installScript -Encoding ASCII

& $rscript --vanilla $installScript
if ($LASTEXITCODE -ne 0) { throw "package installation failed" }

# --- 4. install nanoamp and test ------------------------------------------
Say "Installing the nanoamp package"
& $rexec --vanilla CMD INSTALL --library=$RLib (Join-Path $repoRoot '02_code\r')
if ($LASTEXITCODE -ne 0) { throw "nanoamp installation failed" }

Say "Running the test suite"
& $rscript --vanilla (Join-Path $repoRoot '03_dependence\r-environment\materialize_test_data.R')
& $rscript --vanilla (Join-Path $repoRoot '03_dependence\r-environment\run_tests.R')

Write-Host ""
Ok "Offline installation complete"
Write-Host "  R      : $rHome"
Write-Host "  library: $RLib"
Write-Host ""
Write-Host "To use it in a session:" -ForegroundColor Cyan
Write-Host "  .libPaths(c('$($RLib -replace '\\','/')', .libPaths()))"
Write-Host "  library(nanoamp)"
