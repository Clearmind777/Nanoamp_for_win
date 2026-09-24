"""Run the nanoamp R analysis with streaming output.

The analysis itself already exists as the ``nanoamp`` R package. This module
does not reimplement any of it: it locates R, makes sure the package is
loadable, invokes ``nanoamp_cli()`` with the right arguments, and streams the
log lines back to the caller so the GUI can show progress.

Design notes
------------
* The R entry point is a tiny generated wrapper rather than
  ``Rscript -e "..."``. Passing arguments to ``-e`` is unreliable because
  ``commandArgs(trailingOnly = TRUE)`` picks up the ``--args`` marker, and a
  real script file keeps quoting predictable for paths with spaces or Chinese
  characters.
* Output is read as raw bytes and decoded as UTF-8 with ``errors="replace"``.
  R writes Chinese log text; decoding with the console code page would either
  raise or mangle it.
* The wrapper is written into the repository's ``tmp/`` directory, which is
  already git-ignored, so a two-letter relative path still resolves.
"""

from __future__ import annotations

import os
import shutil
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from pathlib import Path

# Windows: keep the helper console window from flashing on every R launch.
_CREATE_NO_WINDOW = 0x08000000


class RNotFoundError(RuntimeError):
    """R (Rscript) could not be located."""


@dataclass
class RunResult:
    """Outcome of one analysis run."""

    returncode: int
    outdir: Path
    log: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.returncode == 0


def _configured_rscript() -> Path | None:
    """The Rscript.exe recorded by install.exe in config.ini.

    This is the authoritative answer when nanoamp was installed: the installer
    may have bundled its own R under the install root, which none of the
    well-known locations below would ever find. Reading it first is what makes
    a nanoamp.exe that shipped its own R able to start at all.
    """
    return _configured_paths().get("rscript")


def _configured_paths() -> dict[str, Path]:
    """Paths recorded by install.exe in config.ini: rscript, rlib, home.

    The installer is the only component that knows where it put things, so its
    answers are preferred over every hard-coded guess. Both entries matter:
    rscript is the interpreter, rlib is the library holding nanoamp and its
    109 dependencies.
    """
    found: dict[str, Path] = {}
    for root in _config_roots():
        ini = root / "config.ini"
        if not ini.is_file():
            continue
        try:
            lines = ini.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            continue
        for line in lines:
            key, _, value = line.partition("=")
            key = key.strip()
            if key in ("rscript", "rlib", "home") and key not in found:
                candidate = Path(value.strip().strip('"'))
                if candidate.is_dir() or candidate.is_file():
                    found[key] = candidate
    return found


def _config_roots() -> list[Path]:
    """Directories that may hold config.ini, most authoritative first."""
    roots: list[Path] = []

    env_home = os.environ.get("NANOAMP_HOME")
    if env_home:
        roots.append(Path(env_home))

    local = os.environ.get("LOCALAPPDATA")
    if local:
        # The pointer file records a non-default install location.
        marker = Path(local) / "nanoamp.path"
        try:
            if marker.is_file():
                text = marker.read_text(encoding="utf-8").strip()
                if text:
                    roots.append(Path(text))
        except OSError:
            pass
        roots.append(Path(local) / "nanoamp")
    return roots


def _candidate_rscipts() -> Iterable[Path]:
    """Yield plausible Rscript.exe locations, best guess first."""
    env = os.environ.get("NANOAMP_RSCRIPT")
    if env:
        yield Path(env)

    configured = _configured_rscript()
    if configured is not None:
        yield configured

    local = os.environ.get("LOCALAPPDATA")
    # An R that install.exe unpacked into the nanoamp directory.
    if local:
        install_root = Path(local) / "nanoamp"
        yield install_root / "R" / "R-runtime" / "bin" / "Rscript.exe"

    roots = [
        Path(r"D:\tools\R"),
        Path(r"C:\tools\R"),
        Path(r"C:\Program Files\R"),
        Path(r"C:\Program Files (x86)\R"),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "R",
    ]
    for root in roots:
        if not root.is_dir():
            continue
        # Prefer the newest R-* directory found under the root.
        for child in sorted(root.glob("R-*"), reverse=True):
            yield child / "bin" / "Rscript.exe"
        yield root / "bin" / "Rscript.exe"

    which = shutil.which("Rscript")
    if which:
        yield Path(which)


def find_rscript() -> Path:
    """Return the first working Rscript.exe, or raise RNotFoundError."""
    tried: list[str] = []
    for cand in _candidate_rscipts():
        if not cand or str(cand) == ".":
            continue
        tried.append(str(cand))
        if cand.is_file():
            return cand
    raise RNotFoundError(
        "Could not find Rscript.exe.\n"
        "Searched:\n  " + "\n  ".join(tried) + "\n\n"
        "Install R, or point NANOAMP_RSCRIPT at Rscript.exe."
    )


def _candidate_libs(repo_root: Path | None = None) -> list[str]:
    """Return candidate R library directories, most likely first.

    The install's own ``R\\lib`` has to come first when nanoamp was installed:
    that is where install.exe put the nanoamp package and all 109 dependencies,
    and on a machine whose R was bundled by the installer it is the *only*
    place they exist. Omitting it made 环境自检 fail with exit code 1 and
    开始分析 report "R 包未安装" on exactly those machines, while working fine
    on a developer box that happens to have nanoamp in its own library.

    Paths are returned with forward slashes: they are embedded in a generated R
    string literal, where a Windows backslash would be read as an escape
    sequence (``\\R``, ``\\t``) and break parsing. R accepts forward slashes on
    Windows.
    """
    libs: list[str] = []
    env = os.environ.get("NANOAMP_R_LIB")
    if env:
        libs.append(env)

    # What install.exe recorded, and what a bundled layout implies.
    configured = _configured_paths()
    if "rlib" in configured:
        libs.append(str(configured["rlib"]))
    root = Path(repo_root) if repo_root else configured.get("home")
    if root:
        libs.append(str(root / "R" / "lib"))
        # A bundled R keeps its own package library, which may hold deps.
        libs.append(str(root / "R" / "R-runtime" / "library"))

    libs += [r"D:\tools\R\lib", r"C:\tools\R\lib"]
    # R_LIBS_USER is where plain install.packages() lands by default.
    local = os.environ.get("LOCALAPPDATA")
    if local:
        libs.append(os.path.join(local, "R", "win-library", "4.6"))
        libs.append(os.path.join(local, "R", "win-library", "4.5"))

    seen: set[str] = set()
    out: list[str] = []
    for p in libs:
        norm = p.replace("\\", "/")
        key = norm.lower()          # Windows paths are case-insensitive
        if key not in seen:
            seen.add(key)
            out.append(norm)
    return out


WRAPPER_TEMPLATE = """\
# Generated by 02_code/PythonGUI - do not edit; it is rewritten on every run.
.libPaths(c({libs}))
if (!requireNamespace("nanoamp", quietly = TRUE)) {{
  stop("The nanoamp R package is not installed in any of:\\n  ",
       paste(.libPaths(), collapse = "\\n  "), call. = FALSE)
}}
suppressPackageStartupMessages(library(nanoamp))
status <- tryCatch({{
  nanoamp_cli(commandArgs(trailingOnly = TRUE))
  0L
}}, error = function(e) {{
  message("NANOAMP-ERROR: ", conditionMessage(e))
  1L
}})
quit(save = "no", status = status, runLast = FALSE)
"""


class NanoampRunner:
    """Invokes the nanoamp R CLI on behalf of the GUI."""

    def __init__(self, repo_root: Path):
        self.repo_root = Path(repo_root).resolve()
        self.rscript = find_rscript()
        # The R process currently running, so the GUI can cancel it.
        self._proc = None

    # -- environment --------------------------------------------------------
    def wrapper_path(self) -> Path:
        """Path of the generated R wrapper inside the repository."""
        tmp = self.repo_root / "tmp"
        tmp.mkdir(exist_ok=True)
        return tmp / "_gui_run_nanoamp.R"

    def write_wrapper(self) -> Path:
        libs = ", ".join(f'"{p}"' for p in _candidate_libs(self.repo_root))
        path = self.wrapper_path()
        path.write_text(WRAPPER_TEMPLATE.format(libs=libs), encoding="utf-8")
        return path

    def _env(self) -> dict[str, str]:
        env = dict(os.environ)
        # R and the analysis write UTF-8 log text.
        env["PYTHONUTF8"] = "1"
        env["PYTHONIOENCODING"] = "utf-8"
        # Put the install's own library where R looks by default, so the R code
        # and anything R spawns agree with the wrapper's .libPaths() instead of
        # depending on the user's .Renviron having been written correctly.
        libs = _candidate_libs(self.repo_root)
        if libs:
            env["R_LIBS_USER"] = os.pathsep.join(libs)
        # Point R straight at the aligner install.exe put in <home>\bin. Without
        # this the R package falls back to searching PATH, which an already
        # running Explorer may not have refreshed after the install, and the
        # analysis then fails with "External tool 'minimap2' not found".
        minimap2 = self.repo_root / "bin" / "minimap2.exe"
        if minimap2.is_file():
            env["NANOAMP_MINIMAP2"] = str(minimap2)
        return env

    # -- invocation ---------------------------------------------------------
    def doctor(self) -> tuple[int, list[str]]:
        """Run ``nanoamp doctor`` and return (returncode, output lines)."""
        return self.run(["doctor"], stream=None)

    def run(
        self,
        argv: Sequence[str],
        stream: Callable[[str], None] | None = None,
    ) -> tuple[int, list[str]]:
        """Run the CLI with ``argv``, streaming decoded lines.

        Returns ``(returncode, all_lines)``. When ``stream`` is given it is
        called for each line as it arrives.
        """
        import subprocess

        wrapper = self.write_wrapper()
        cmd = [str(self.rscript), "--vanilla", str(wrapper), *argv]

        lines: list[str] = []
        proc = subprocess.Popen(
            cmd,
            cwd=str(self.repo_root),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            creationflags=_CREATE_NO_WINDOW,
            env=self._env(),
        )
        self._proc = proc
        assert proc.stdout is not None
        try:
            for raw in iter(proc.stdout.readline, b""):
                line = raw.decode("utf-8", errors="replace").rstrip("\r\n")
                lines.append(line)
                if stream is not None:
                    stream(line)
        finally:
            self._proc = None
            proc.stdout.close()
            proc.wait()
        return proc.returncode, lines

    def cancel(self) -> None:
        """Stop the analysis that is currently running.

        Kills the R process. Whatever partial output it had written stays on
        disk, so the GUI tells the user which folder to look at rather than
        pretending the run never happened.
        """
        proc = self._proc
        if proc is not None and proc.poll() is None:
            try:
                proc.kill()
            except OSError:
                pass
