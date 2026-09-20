@echo off
REM ===========================================================================
REM  nanoamp command-line launcher (release build)
REM
REM  install.exe copies this to %LOCALAPPDATA%\nanoamp\bin\nanoamp.cmd and adds
REM  that directory to the user PATH, so "nanoamp" works from any terminal.
REM
REM  IMPORTANT: keep this file pure ASCII. cmd.exe reads .cmd files using the
REM  console OEM code page, so UTF-8 Chinese here would be parsed as garbage
REM  commands. Chinese documentation lives in the README files instead.
REM ===========================================================================
setlocal EnableDelayedExpansion

set "NANOAMP_HOME=%LOCALAPPDATA%\nanoamp"
set "NANOAMP_LIB=%NANOAMP_HOME%\R\lib"

REM --- 1. locate Rscript -----------------------------------------------------
REM  install.exe writes config.ini as key=value with no spaces around "=",
REM  so "rscript=..." parses cleanly here.
set "RSCRIPT="
if exist "%NANOAMP_HOME%\config.ini" (
  for /f "usebackq tokens=1,* delims==" %%a in ("%NANOAMP_HOME%\config.ini") do (
    if /i "%%a"=="rscript" set "RSCRIPT=%%b"
  )
)
if not defined RSCRIPT if defined NANOAMP_RSCRIPT set "RSCRIPT=%NANOAMP_RSCRIPT%"
if not defined RSCRIPT for %%R in (Rscript.exe) do if not defined RSCRIPT set "RSCRIPT=%%~$PATH:R"

if not defined RSCRIPT (
  echo [ERROR] Rscript.exe was not found.
  echo         Run install.exe first, or install R and try again.
  echo         You can also set NANOAMP_RSCRIPT to the full path of Rscript.exe.
  exit /b 1
)

REM --- 2. R library: prefer the installed one --------------------------------
if exist "%NANOAMP_LIB%" set "R_LIBS_USER=%NANOAMP_LIB%"

REM --- 3. locate the driver script -------------------------------------------
set "DRIVER="
if exist "%NANOAMP_HOME%\config\nanoamp_cli.R" set "DRIVER=%NANOAMP_HOME%\config\nanoamp_cli.R"
if not defined DRIVER if exist "%~dp0nanoamp_cli.R" set "DRIVER=%~dp0nanoamp_cli.R"
if not defined DRIVER if exist "%~dp0nanoamp.R"     set "DRIVER=%~dp0nanoamp.R"

if not defined DRIVER (
  echo [ERROR] nanoamp driver script was not found.
  echo         Run install.exe again to repair the installation.
  exit /b 1
)

"%RSCRIPT%" --vanilla "%DRIVER%" %*
exit /b %ERRORLEVEL%
