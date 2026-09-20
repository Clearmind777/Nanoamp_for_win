"""install.exe - one-click installer for nanoamp on Windows.

The audience is a biologist who does not write code, so this window does four
things and nothing else:

  1. find or install R,
  2. install the R packages nanoamp needs (from the bundled offline copy),
  3. install the nanoamp package itself,
  4. register the ``nanoamp`` command and put a desktop shortcut in place.

Everything is installed under ``%LOCALAPPDATA%\\nanoamp`` so nothing touches
system directories and no administrator rights are needed. The user's own R
library is left alone by pointing ``R_LIBS_USER`` at the nanoamp library
through ``%USERPROFILE%\\Documents\\.Renviron``.

The layout expected next to this executable:

    release/
      install.exe
      _offline/r/R-4.6.1-win.exe              the R installer
      _offline/extra/*.zip                    109 R package binaries
      _offline/minimap2.exe                   bundled aligner
      01_R-package/nanoamp_0.1.0.tar.gz       the R package source
"""

from __future__ import annotations

import configparser
import ctypes
import os
import queue
import re
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
import tkinter as tk

import nanoamp_common as common
from nanoamp_common import (
    CONFIG_FILE,
    PRODUCT,
    SHORTCUT_NAME,
    app_dir as _app_subdir,
    bin_dir as _bin_subdir,
    config_dir as _config_subdir,
    desktop_dir,
    lib_dir as _lib_subdir,
    parse_config,
    renviron_path,
    shortcut_path,
    write_pointer,
)

APP_TITLE = "nanoamp 安装程序"
MIN_R_MAJOR = 4
MIN_R_MINOR = 2
CREATE_NO_WINDOW = 0x08000000
PACKAGE_NAME = "nanoamp"


# --------------------------------------------------------------------------
# paths
# --------------------------------------------------------------------------
def app_dir() -> Path:
    """Locate the directory that holds ``_offline/`` and ``01_R-package/``.

    Two layouts have to work:

    * frozen as ``release/install.exe`` - PyInstaller onedir extracts the
      Python modules into a sibling folder, so ``sys.executable`` is the
      reliable anchor, and the payload sits next to it;
    * run as a script from ``release/_installer/`` - walk up to the directory
      that actually contains the payload.

    The payload is never bundled inside the executable: it is ~250 MB of R
    installers and package archives, which would make the .exe enormous and
    slow to start.
    """
    if getattr(sys, "frozen", False):
        anchor = Path(sys.executable).resolve().parent
    else:
        anchor = Path(__file__).resolve().parent
    for candidate in (anchor, anchor.parent, anchor.parent.parent):
        if (candidate / "_offline").is_dir() or (candidate / "01_R-package").is_dir():
            return candidate
    return anchor


def install_home() -> Path:
    """Default install root (used only for the pointer file location)."""
    return common.default_install_home()


# Kept for backwards compatibility with the earlier release scripts; the real
# paths are derived from the chosen install root held by Context.
def r_lib_dir() -> Path:
    return _lib_subdir(install_home())


def bin_dir() -> Path:
    return _bin_subdir(install_home())


# --------------------------------------------------------------------------
# locating R
# --------------------------------------------------------------------------
def _r_candidates() -> list[Path]:
    """Candidate Rscript.exe paths, newest-looking first."""
    out: list[Path] = []
    env = os.environ.get("NANOAMP_RSCRIPT")
    if env:
        out.append(Path(env))

    for var in ("ProgramFiles", "ProgramFiles(x86)", "LOCALAPPDATA"):
        base = os.environ.get(var)
        if not base:
            continue
        root = Path(base) / ("Programs/R" if var == "LOCALAPPDATA" else "R")
        if root.is_dir():
            for child in sorted(root.glob("R-*"), reverse=True):
                out.append(child / "bin" / "Rscript.exe")

    for drive in ("C:", "D:"):
        root = Path(f"{drive}/tools/R")
        if root.is_dir():
            for child in sorted(root.glob("R-*"), reverse=True):
                out.append(child / "bin" / "Rscript.exe")

    which = shutil.which("Rscript")
    if which:
        out.append(Path(which))
    return out


def find_rscript() -> Path | None:
    for cand in _r_candidates():
        if cand.is_file():
            return cand
    return None


def r_version(rscript: Path) -> tuple[int, int] | None:
    """Parse the R version from ``Rscript --version``.

    The banner differs by invocation: ``Rscript --version`` prints
    "Rscript (R) version 4.6.1 (2026-06-24)" while ``R --version`` prints
    "R version 4.6.1 ...". Match either, so the check works for both.
    """
    try:
        proc = subprocess.run(
            [str(rscript), "--version"],
            capture_output=True, text=True, timeout=30,
            creationflags=CREATE_NO_WINDOW,
        )
        text = (proc.stdout or "") + (proc.stderr or "")
        m = re.search(r"version\s+(\d+)\.(\d+)", text)
        if m:
            return int(m.group(1)), int(m.group(2))
    except (OSError, subprocess.SubprocessError):
        return None
    return None


def r_supported(rscript: Path) -> bool:
    v = r_version(rscript)
    if v is None:
        return False
    return (v[0], v[1]) >= (MIN_R_MAJOR, MIN_R_MINOR)


# --------------------------------------------------------------------------
# the install steps
# --------------------------------------------------------------------------
@dataclass
class Context:
    """Everything the steps need, resolved once at start."""

    root: Path
    install_root: Path = field(default_factory=common.default_install_home)
    make_shortcut: bool = True
    touch_path: bool = True
    log: list[str] = field(default_factory=list)

    # -- paths derived from the chosen install location --------------------
    @property
    def lib(self) -> Path:
        return _lib_subdir(self.install_root)

    @property
    def bin(self) -> Path:
        return _bin_subdir(self.install_root)

    @property
    def app(self) -> Path:
        return _app_subdir(self.install_root)

    @property
    def config(self) -> Path:
        return _config_subdir(self.install_root)

    @property
    def config_file(self) -> Path:
        return self.install_root / CONFIG_FILE

    @property
    def offline(self) -> Path:
        return self.root / "_offline"

    @property
    def repo_root(self) -> Path:
        """Root of the bundled R package repository (CRAN layout)."""
        return self.offline / "r-packages"

    def extra_dir(self, r_tag: str) -> Path:
        """Package directory for a given ``<major>.<minor>`` R tag.

        ``repos=`` needs ``<root>/bin/windows/contrib/<rver>/PACKAGES``;
        ``contriburl=`` would look for ``<root>/PACKAGES`` instead. Getting the
        layout right is what makes one offline ``install.packages()`` call work.
        """
        return self.repo_root / "bin" / "windows" / "contrib" / r_tag

    def available_r_tags(self) -> list[str]:
        """R version tags actually present in the bundled repository."""
        base = self.repo_root / "bin" / "windows" / "contrib"
        if not base.is_dir():
            return []
        return sorted((d.name for d in base.iterdir() if d.is_dir()), reverse=True)

    @property
    def r_installer(self) -> Path | None:
        rdir = self.offline / "r"
        if not rdir.is_dir():
            return None
        exes = sorted(rdir.glob("R-*-win.exe"))
        return exes[-1] if exes else None

    @property
    def pkg_tarball(self) -> Path | None:
        d = self.root / "01_R-package"
        tarballs = sorted(d.glob("nanoamp_*.tar.gz")) if d.is_dir() else []
        return tarballs[-1] if tarballs else None

    @property
    def gui_exe(self) -> Path | None:
        for cand in (self.root / "03_GUI" / "nanoamp.exe",
                     self.root / "06_GUI" / "dist" / "nanoamp.exe"):
            if cand.is_file():
                return cand
        return None

    @property
    def cli_launcher(self) -> Path | None:
        cand = self.root / "02_CLI" / "bin" / "nanoamp.cmd"
        return cand if cand.is_file() else None


class Installer:
    """Runs the install on a worker thread, reporting through a queue."""

    def __init__(self, ctx: Context, events: queue.Queue):
        self.ctx = ctx
        self.events = events
        self.rscript: Path | None = None
        self.lib = ctx.lib          # the library is inside the chosen root

    @property
    def r_exe(self) -> Path:
        """R.exe next to the resolved Rscript.exe."""
        assert self.rscript is not None
        candidate = self.rscript.parent / "R.exe"
        return candidate if candidate.is_file() else self.rscript

    # -- reporting ------------------------------------------------------
    def say(self, text: str) -> None:
        self.ctx.log.append(text)
        self.events.put(("log", text))

    def step(self, index: int, total: int, text: str) -> None:
        self.events.put(("step", index, total, text))

    # -- process helper -------------------------------------------------
    def run(self, cmd: list[str], env_extra: dict[str, str] | None = None,
            timeout: int = 3600) -> tuple[int, str]:
        """Run a command and return (returncode, combined output).

        R writes UTF-8, including Chinese messages, but Python picks the
        console code page (GBK here) when decoding. Decode explicitly as UTF-8
        with errors="replace" so a stray byte can never crash the installer.
        """
        env = dict(os.environ)
        env["R_LIBS_USER"] = str(self.lib)
        if env_extra:
            env.update(env_extra)
        try:
            proc = subprocess.run(
                cmd, capture_output=True, timeout=timeout,
                creationflags=CREATE_NO_WINDOW, env=env,
            )
        except subprocess.TimeoutExpired:
            return 124, "命令超时"
        except OSError as exc:
            return 127, str(exc)
        out = (proc.stdout or b"") + (proc.stderr or b"")
        text = out.decode("utf-8", errors="replace")
        return proc.returncode, text

    def run_to_file(self, cmd: list[str], env_extra: dict[str, str] | None = None,
                    timeout: int = 3600, tag: str = "cmd") -> tuple[int, str]:
        """Run a command with its output redirected to a *file*, not a pipe.

        ``R CMD INSTALL`` launches helper child processes. When the parent R
        process is started with stdout/stderr bound to anonymous pipes, those
        children cannot write to them and the whole thing dies with a Windows
        access violation (exit code 0xC0000005 / 3221225477). Writing to a real
        file descriptor avoids that entirely, and we still get the full log.
        """
        env = dict(os.environ)
        env["R_LIBS_USER"] = str(self.lib)
        if env_extra:
            env.update(env_extra)

        log_path = self.ctx.config / f"_{tag}.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(log_path, "wb") as fh:
                proc = subprocess.run(
                    cmd, stdin=subprocess.DEVNULL, stdout=fh, stderr=subprocess.STDOUT,
                    timeout=timeout, creationflags=CREATE_NO_WINDOW, env=env,
                )
            text = log_path.read_bytes().decode("utf-8", errors="replace")
            return proc.returncode, text
        except subprocess.TimeoutExpired:
            return 124, "命令超时"
        except OSError as exc:
            return 127, str(exc)

    # -- main flow ------------------------------------------------------
    def run_all(self) -> bool:
        try:
            self._preflight()

            # Create the target directories before touching R: the library path
            # is passed to every R invocation, and R drops a non-existent entry
            # from .libPaths(), which would make later steps look broken.
            self._prepare_dirs()

            total = 6
            self.step(0, total, "检查并安装 R 运行环境…")
            if not self._ensure_r():
                return False

            self.step(1, total, "安装 R 依赖包…")
            if not self._install_r_dependencies():
                return False

            self.step(2, total, f"安装 {PACKAGE_NAME} 主程序…")
            if not self._install_package():
                return False

            self.step(3, total, "配置 nanoamp 命令…")
            ok_cli = self._configure_cli()

            self.step(4, total, "创建桌面快捷方式…")
            ok_gui = self._configure_gui()

            self.step(5, total, "自检…")
            ok_check = self._self_check()

            self._write_config()
            self.events.put(("done", ok_cli and ok_gui and ok_check))
            return True
        except Exception as exc:  # noqa: BLE001 - report anything to the user
            import traceback
            self.say(traceback.format_exc())
            self.events.put(("fatal", str(exc)))
            return False

    # -- steps ----------------------------------------------------------
    def _preflight(self) -> None:
        self.say(f"安装程序目录 : {self.ctx.root}")
        self.say(f"安装目标目录 : {self.ctx.install_root}")
        self.say(f"R 包库目录   : {self.lib}")

        missing = []
        if self.ctx.r_installer is None and find_rscript() is None:
            missing.append("_offline/r/R-*-win.exe（R 安装器）")
        if not self.ctx.available_r_tags():
            missing.append("_offline/r-packages/bin/windows/contrib/<版本>/*.zip（R 包）")
        if self.ctx.pkg_tarball is None:
            missing.append("01_R-package/nanoamp_*.tar.gz（主程序）")
        if missing:
            raise RuntimeError(
                "安装包不完整，缺少以下文件：\n\n  " + "\n  ".join(missing) +
                "\n\n请重新完整解压安装包后重试。"
            )

        free = shutil.disk_usage(str(self.ctx.install_root.anchor or "C:")).free
        need = 1500 * 1024 * 1024  # ~1.5 GB with headroom
        if free < need:
            self.say(f"警告：剩余磁盘空间 {free / 1e9:.1f} GB，建议至少 1.5 GB。")
        for tag in self.ctx.available_r_tags():
            n = len(list(self.ctx.extra_dir(tag).glob("*.zip")))
            self.say(f"R 包文件     : R {tag} 共 {n} 个")

    def _ensure_r(self) -> bool:
        existing = find_rscript()
        if existing and r_supported(existing):
            ver = r_version(existing)
            self.say(f"检测到已安装的 R {ver[0]}.{ver[1]}：{existing}")
            self.rscript = existing
            return True

        if existing:
            self.say(f"检测到 R 版本过低，将安装新版（现有：{existing}）")

        installer = self.ctx.r_installer
        if installer is None:
            self.say("未找到 R 安装器，且系统内没有可用的 R。")
            self.events.put(("ask_r",))
            return False

        target = self.ctx.install_root / "R"
        target.mkdir(parents=True, exist_ok=True)
        rdir = target / "R-runtime"
        self.say(f"正在安装 R（约需 1-3 分钟，请勿关闭窗口）…")
        self.say(f"安装位置：{rdir}")
        cmd = [
            str(installer), "/VERYSILENT", "/NORESTART", "/CURRENTUSER",
            f"/DIR={rdir}",
        ]
        code, out = self.run(cmd, timeout=1800)
        if code != 0:
            self.say(f"R 安装器返回代码 {code}")
            if out.strip():
                self.say(out.strip()[-2000:])
            self.events.put(("ask_r",))
            return False

        rscript = rdir / "bin" / "Rscript.exe"
        if not rscript.is_file():
            self.say(f"未找到 {rscript}")
            self.events.put(("ask_r",))
            return False
        self.rscript = rscript
        v = r_version(rscript)
        self.say(f"R 安装完成：{'%d.%d' % v if v else '未知版本'}")
        return True

    def _prepare_dirs(self) -> None:
        for d in (self.lib, self.ctx.bin, self.ctx.config):
            d.mkdir(parents=True, exist_ok=True)
        self.say(f"已创建 {self.lib}")

        # Remember the chosen root so uninstall.exe can find it even when the
        # user installed somewhere other than the default.
        marker = write_pointer(self.ctx.install_root)
        self.say(f"已记录安装位置到 {marker}")

        # Point the user's R at the nanoamp library without touching their
        # existing library, and without needing administrator rights.
        renv = renviron_path()
        renv.parent.mkdir(parents=True, exist_ok=True)
        line = f'R_LIBS_USER="{self.lib}"'
        existing = ""
        if renv.is_file():
            existing = renv.read_text(encoding="utf-8", errors="replace")
        lines = [ln for ln in existing.splitlines() if not ln.strip().startswith("R_LIBS_USER")]
        lines.append(line)
        renv.write_text("\n".join(lines).lstrip("\n") + "\n", encoding="utf-8")
        self.say(f"已写入 {renv}")
        self.say(f"  {line}")

    def _install_r_dependencies(self) -> bool:
        assert self.rscript is not None
        ver = r_version(self.rscript)
        if ver is None:
            self.say("无法确定 R 版本，跳过依赖安装。")
            return False
        tag = f"{ver[0]}.{ver[1]}"
        pkg_dir = self.ctx.extra_dir(tag)
        if not pkg_dir.is_dir():
            tags = self.ctx.available_r_tags()
            self.say(f"安装包内没有适配 R {tag} 的依赖包。")
            if tags:
                self.say(f"安装包提供的是：{', '.join(tags)}")
                self.say("请安装与安装包匹配的 R 版本，或获取对应版本的安装包。")
            return False

        repo = self.ctx.repo_root.as_uri()
        lib = str(self.lib).replace("\\", "/")
        script = self._write_temp_r("install_deps", f"""
.libPaths(c({lib!r}, .libPaths()))
options(repos = c(CRAN = {repo!r}), download.file.method = "libcurl", timeout = 3600)
ap <- available.packages(repos = {repo!r}, type = "win.binary")
cat("本地仓库可用包数:", nrow(ap), "\\n")
if (!nrow(ap)) stop("本地 R 包仓库为空，安装包可能不完整")
utils::install.packages(rownames(ap), lib = {lib!r}, repos = {repo!r},
                        type = "win.binary", dependencies = TRUE, quiet = TRUE)
ok <- requireNamespace("Biostrings", quietly = TRUE) &&
      requireNamespace("data.table", quietly = TRUE)
cat("关键依赖检查:", ok, "\\n")
if (!ok) stop("关键依赖安装后仍不可用")
""")
        self.say(f"使用 R {tag} 对应的 {len(list(pkg_dir.glob('*.zip')))} 个依赖包")
        code, out = self.run([str(self.rscript), "--vanilla", str(script)], timeout=3600)
        self._log_tail(out)
        if code != 0:
            self.say(f"R 依赖安装失败（代码 {code}）")
            return False
        self.say("R 依赖包安装完成")
        return True

    def _install_package(self) -> bool:
        assert self.rscript is not None
        tarball = self.ctx.pkg_tarball
        assert tarball is not None
        cmd = [
            str(self.r_exe), "--vanilla", "CMD", "INSTALL",
            f"--library={self.lib}", str(tarball),
        ]
        # R.exe, not Rscript.exe: `Rscript CMD INSTALL` dies with a Windows
        # access violation (0xC0000005) when launched from a non-console
        # process, while `R CMD INSTALL` works. Verified on this machine.
        code, out = self.run_to_file(cmd, timeout=1800, tag="install_package")
        self._log_tail(out)
        if code != 0:
            self.say(f"{PACKAGE_NAME} 安装失败（代码 {code}）")
            return False
        self.say(f"{PACKAGE_NAME} 安装完成")
        return True

    def _configure_cli(self) -> bool:
        """Create the CLI driver plus nanoamp.cmd, and put it on the user PATH."""
        assert self.rscript is not None
        lib = str(self.lib).replace("\\", "/")
        minimap2 = self.ctx.bin / "minimap2.exe"

        # The driver is written to a stable path that nanoamp.cmd looks for.
        # Pinning NANOAMP_MINIMAP2 here (rather than relying on PATH) means the
        # installed copy is always the one used, whatever else is on the disk.
        driver = self._write_named_r("nanoamp_cli.R", f"""
# 由 install.exe 生成，请勿手工编辑（重装会覆盖）。
# 调用 nanoamp 命令行接口。
.libPaths(c({lib!r}, .libPaths()))
Sys.setenv(NANOAMP_MINIMAP2 = {str(minimap2).replace(chr(92), '/')!r})
if (!requireNamespace("{PACKAGE_NAME}", quietly = TRUE)) {{
  stop("未找到 {PACKAGE_NAME} 包。请重新运行安装程序 install.exe。")
}}
suppressPackageStartupMessages(library({PACKAGE_NAME}))
status <- tryCatch({{ {PACKAGE_NAME}_cli(commandArgs(trailingOnly = TRUE)); 0L }},
                   error = function(e) {{ message("错误: ", conditionMessage(e)); 1L }})
quit(save = "no", status = status, runLast = FALSE)
""")
        self.say(f"已创建命令行驱动 -> {driver}")

        cmd_path = self.ctx.bin / "nanoamp.cmd"
        launcher = self.ctx.cli_launcher
        if launcher is not None and launcher.is_file():
            shutil.copy2(launcher, cmd_path)
            self.say(f"已安装命令行启动器 -> {cmd_path}")
        else:
            # Fallback: a minimal wrapper, in case the release tree is partial.
            cmd_path.write_text(
                "@echo off\r\n"
                f'set "R_LIBS_USER={self.lib}"\r\n'
                f'"{self.rscript}" --vanilla "{driver}" %*\r\n',
                encoding="ascii",
            )
            self.say(f"已创建命令行包装（简化版） -> {cmd_path}")

        added = _add_to_user_path(str(self.ctx.bin)) if self.ctx.touch_path else False
        if not self.ctx.touch_path:
            self.say("（已按参数要求跳过修改 PATH）")
        elif added:
            self.say(f"已把 {self.ctx.bin} 加入用户 PATH")
            self.say("提示：新开的命令行窗口才会生效。")
        else:
            self.say(f"{self.ctx.bin} 已在 PATH 中")

        # Copy the bundled aligner next to the config so the R package finds it.
        mm = self.ctx.offline / "minimap2.exe"
        if mm.is_file():
            target = self.ctx.bin / "minimap2.exe"
            shutil.copy2(mm, target)
            self.say(f"已安装比对程序 minimap2 -> {target}")
        return True

    def _configure_gui(self) -> bool:
        gui = self.ctx.gui_exe
        if gui is None:
            self.say("安装包内没有找到图形界面 nanoamp.exe，跳过快捷方式。")
            return True
        target_dir = self.ctx.app
        target_dir.mkdir(parents=True, exist_ok=True)
        target = target_dir / "nanoamp.exe"
        shutil.copy2(gui, target)
        self.say(f"已安装图形界面 -> {target}")

        if not self.ctx.make_shortcut:
            self.say("（已按参数要求跳过创建桌面快捷方式）")
            return True
        if _create_shortcut(target, "nanoamp 分析工具（双击打开）"):
            self.say("已在桌面创建快捷方式")
        else:
            self.say(f"桌面快捷方式创建失败，可直接双击 {target}")
        return True

    def _self_check(self) -> bool:
        assert self.rscript is not None
        lib = str(self.lib).replace("\\", "/")
        minimap2 = str(self.ctx.bin / "minimap2.exe").replace("\\", "/")
        script = self._write_temp_r("doctor", f"""
.libPaths(c({lib!r}, .libPaths()))
# Pin the bundled aligner explicitly. Without this, nanoamp's dependence-dir
# search can walk up from the current working directory and pick up a
# different minimap2.exe (for example the repository copy when install.exe is
# run from a source checkout).
Sys.setenv(NANOAMP_MINIMAP2 = {minimap2!r})
suppressPackageStartupMessages(library({PACKAGE_NAME}))
cat("{PACKAGE_NAME} 版本:", as.character(packageVersion("{PACKAGE_NAME}")), "\\n")
for (p in c("Biostrings","Rsamtools","ShortRead","data.table")) {{
  cat(sprintf("  %-12s %s\\n", p, requireNamespace(p, quietly = TRUE)))
}}
mp <- {PACKAGE_NAME}:::nanoamp_tool_path("minimap2", required = FALSE)
cat("  minimap2    ", if (is.null(mp)) "未找到" else mp, "\\n")
""")
        code, out = self.run([str(self.rscript), "--vanilla", str(script)], timeout=600)
        for line in out.splitlines():
            if line.strip():
                self.say("  " + line.strip())
        if code != 0:
            self.say("自检未通过")
            return False
        self.say("自检通过")
        return True

    def _write_config(self) -> None:
        """Write config.ini in the install root, in a format .cmd can parse.

        ``home`` must be the *install* root, not the directory install.exe was
        run from: the launcher and the uninstaller use it to find the
        installation, and the two are only the same by coincidence.
        configparser would also emit "rscript = D:\\..." with spaces, which a
        ``for /f "delims=="`` loop reads as the key "rscript " and never
        matches, so the file is written as plain key=value.
        """
        lines = [
            "[nanoamp]",
            f"home={self.ctx.install_root}",
            f"rscript={self.rscript if self.rscript else ''}",
            f"rlib={self.lib}",
            f"installed_at={time.strftime('%Y-%m-%d %H:%M:%S')}",
        ]
        path = self.ctx.config_file
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        self.say(f"已写入配置 {path}")

    # -- helpers --------------------------------------------------------
    def _write_named_r(self, name: str, body: str) -> Path:
        """Write a generated R helper to a stable, predictable path."""
        d = self.ctx.config
        d.mkdir(parents=True, exist_ok=True)
        path = d / name
        path.write_text(body, encoding="utf-8")
        return path

    def _write_temp_r(self, name: str, body: str) -> Path:
        return self._write_named_r(f"_{name}.R", body)

    def _log_tail(self, out: str, lines: int = 12) -> None:
        tail = [ln for ln in out.splitlines() if ln.strip()][-lines:]
        for ln in tail:
            self.say("  " + ln.strip())


# --------------------------------------------------------------------------
# Windows integration helpers
# --------------------------------------------------------------------------
def _add_to_user_path(directory: str) -> bool:
    """Append directory to the user PATH. Returns True if it changed."""
    import winreg

    key_path = r"Environment"
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                current = ""
            parts = [p for p in current.split(";") if p.strip()]
            if any(os.path.normcase(p.rstrip("\\")) == os.path.normcase(directory.rstrip("\\"))
                   for p in parts):
                return False
            new = ";".join(parts + [directory])
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, new)
    except OSError:
        return False

    # Tell already-running processes about it.
    try:
        HWND_BROADCAST, WM_SETTINGCHANGE, SMTO_ABORTIFHUNG = 0xFFFF, 0x1A, 0x0002
        ctypes.windll.user32.SendMessageTimeoutW(
            HWND_BROADCAST, WM_SETTINGCHANGE, 0, "Environment",
            SMTO_ABORTIFHUNG, 5000, None,
        )
    except Exception:  # noqa: BLE001
        pass
    return True


def _create_shortcut(target: Path, description: str) -> bool:
    """Create a desktop .lnk via WScript.Shell (no extra dependency).

    The script is written as **UTF-16LE**, not UTF-8. cscript reads a .vbs
    using the ANSI code page by default, so a UTF-8 script containing the
    Chinese shortcut name is decoded as mojibake and the Save() call fails
    with "Unable to save shortcut ...\\nanoamp ????.lnk". UTF-16LE with a BOM
    (what wscript itself emits) is read correctly on any locale.
    """
    desktop = desktop_dir()
    if not desktop.is_dir():
        return False
    link = shortcut_path()
    script = install_home() / "config" / "_shortcut.vbs"
    script.parent.mkdir(parents=True, exist_ok=True)

    lines = [
        'Set ws = CreateObject("WScript.Shell")',
        f'Set sc = ws.CreateShortcut("{link}")',
        f'sc.TargetPath = "{target}"',
        f'sc.WorkingDirectory = "{target.parent}"',
        f'sc.Description = "{description}"',
        'sc.Save',
    ]
    try:
        # cscript expects UTF-16LE with a BOM; a UTF-8 script would have its
        # Chinese path/name decoded as ANSI mojibake. See the docstring.
        script.write_bytes(b"\xff\xfe" + "\r\n".join(lines).encode("utf-16-le")
                           + "\r\n".encode("utf-16-le"))
        proc = subprocess.run(
            ["cscript", "//nologo", str(script)],
            capture_output=True, timeout=60, creationflags=CREATE_NO_WINDOW,
        )
        if proc.returncode != 0 or not link.is_file():
            detail = (proc.stdout or b"").decode("utf-8", "replace").strip()
            if detail:
                print(f"shortcut creation reported: {detail}")
    except (OSError, subprocess.SubprocessError):
        return False
    finally:
        try:
            script.unlink()
        except OSError:
            pass
    return link.is_file()


# --------------------------------------------------------------------------
# the window
# --------------------------------------------------------------------------
class InstallerWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        self.root.geometry("760x640")
        self.root.minsize(680, 580)
        self.events: queue.Queue = queue.Queue()
        self.var_install_root = tk.StringVar(value=str(common.default_install_home()))
        self.var_shortcut = tk.BooleanVar(value=True)
        self.var_path = tk.BooleanVar(value=True)
        self.ctx = Context(root=app_dir())
        self.worker: threading.Thread | None = None
        self._build()

    def _build(self) -> None:
        pad = 14
        head = ttk.Frame(self.root, padding=(pad, pad, pad, 6))
        head.pack(fill="x")
        ttk.Label(head, text="nanoamp 一键安装", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            head,
            text="这个程序会自动安装分析所需的一切：R、依赖包、主程序、命令和桌面快捷方式。\n"
                 "全程无需联网，无需管理员权限，大约需要 3-10 分钟。",
            font=("Microsoft YaHei UI", 9),
            foreground="#444444",
            justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # -- install location ------------------------------------------------
        loc = ttk.LabelFrame(self.root, text="安装位置", padding=8)
        loc.pack(fill="x", padx=pad, pady=(8, 0))
        loc.columnconfigure(0, weight=1)
        row = ttk.Frame(loc)
        row.grid(row=0, column=0, sticky="ew")
        row.columnconfigure(0, weight=1)
        self.entry_root = ttk.Entry(row, textvariable=self.var_install_root)
        self.entry_root.grid(row=0, column=0, sticky="ew")
        ttk.Button(row, text="修改…", command=self._pick_install_root).grid(row=0, column=1, padx=(6, 0))
        ttk.Button(row, text="恢复默认", command=self._reset_install_root).grid(row=0, column=2, padx=(6, 0))
        ttk.Label(
            loc,
            text="默认装在当前用户目录下，不需要管理员权限。"
                 "也可以改到 D:\\nanoamp 这类位置（路径请避免中文和空格）。",
            font=("Microsoft YaHei UI", 8),
            foreground="#666666",
            wraplength=690,
            justify="left",
        ).grid(row=1, column=0, sticky="w", pady=(4, 0))

        self.lbl_space = ttk.Label(loc, text="", font=("Microsoft YaHei UI", 8), foreground="#666666")
        self.lbl_space.grid(row=2, column=0, sticky="w", pady=(2, 0))
        self.var_install_root.trace_add("write", lambda *_: self._update_space())

        # -- options ---------------------------------------------------------
        opts = ttk.LabelFrame(self.root, text="选项", padding=8)
        opts.pack(fill="x", padx=pad, pady=(8, 0))
        ttk.Checkbutton(opts, text="在桌面创建快捷方式（推荐）",
                        variable=self.var_shortcut).pack(anchor="w")
        ttk.Checkbutton(opts, text="把 nanoamp 命令加入用户 PATH（推荐）",
                        variable=self.var_path).pack(anchor="w")

        self.step_label = ttk.Label(self.root, text="准备就绪，点击下方按钮开始安装。",
                                    font=("Microsoft YaHei UI", 10), padding=(pad, 6))
        self.step_label.pack(anchor="w")

        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=6)
        self.progress.pack(fill="x", padx=pad)

        log_frame = ttk.LabelFrame(self.root, text="安装详情", padding=4)
        log_frame.pack(fill="both", expand=True, padx=pad, pady=(8, 6))
        self.log_text = tk.Text(log_frame, wrap="word", height=12,
                                font=("Consolas", 9), state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        bar = ttk.Frame(self.root, padding=(pad, 0, pad, pad))
        bar.pack(fill="x")
        self.btn = ttk.Button(bar, text="开始安装", command=self._start)
        self.btn.pack(side="left")
        self.btn_close = ttk.Button(bar, text="关闭", command=self.root.destroy)
        self.btn_close.pack(side="right")

        self.root.after(120, self._pump)

    # -- logging --------------------------------------------------------
    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    # -- install location -----------------------------------------------
    def _pick_install_root(self) -> None:
        """Let the user choose where to install.

        A directory chooser is used, but the user may want to create a new
        folder, so falling back to a typed path is supported too.
        """
        current = self.var_install_root.get().strip() or str(common.default_install_home())
        chosen = filedialog.askdirectory(
            title="选择安装位置（选中一个文件夹，nanoamp 会装在里面）",
            initialdir=current if Path(current).is_dir() else str(Path(current).parent),
            mustexist=False,
        )
        if not chosen:
            return
        # If the user picked an existing folder, install *into* a nanoamp
        # subfolder rather than scattering files across it.
        picked = Path(chosen)
        if picked.name.lower() != PRODUCT:
            picked = picked / PRODUCT
        self.var_install_root.set(str(picked))
        self._update_space()

    def _reset_install_root(self) -> None:
        self.var_install_root.set(str(common.default_install_home()))
        self._update_space()

    def _update_space(self) -> None:
        """Show where it will go and whether that drive has room."""
        target = Path(self.var_install_root.get().strip() or ".")
        try:
            anchor = target.anchor or "C:\\"
            free = shutil.disk_usage(anchor).free
            need = 1500 * 1024 * 1024
            text = f"将安装到：{target}    该磁盘剩余 {free / 1e9:.1f} GB"
            if free < need:
                text += "  （不足，建议至少 1.5 GB）"
            self.lbl_space.configure(text=text, foreground="#b00020" if free < need else "#666666")
        except OSError:
            self.lbl_space.configure(text=f"将安装到：{target}", foreground="#b00020")

    # -- control --------------------------------------------------------
    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return

        root_text = self.var_install_root.get().strip()
        if not root_text:
            messagebox.showwarning(APP_TITLE, "请先选择安装位置。")
            return
        target = Path(root_text)
        if any(ch in str(target) for ch in '<>:"|?*'):
            messagebox.showerror(APP_TITLE, f"安装路径含有非法字符：\n{target}")
            return

        # Warn before clobbering an existing install in a different place.
        existing = common.find_existing_install()
        if existing and Path(existing[0]).resolve() != target.resolve():
            if not messagebox.askyesno(
                APP_TITLE,
                f"检测到已有一份 nanoamp 安装在：\n{existing[0]}\n\n"
                f"继续会在新位置再装一份（旧的那份需要另行卸载）。\n\n是否继续？",
            ):
                return

        self.ctx.install_root = target
        self.ctx.make_shortcut = bool(self.var_shortcut.get())
        self.ctx.touch_path = bool(self.var_path.get())

        for w in (self.entry_root,):
            w.configure(state="disabled")

        self.btn.configure(state="disabled")
        self.log_text.configure(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.configure(state="disabled")
        self.step_label.configure(text="正在安装…")
        installer = Installer(self.ctx, self.events)
        self.worker = threading.Thread(target=installer.run_all, daemon=True)
        self.worker.start()

    def _pump(self) -> None:
        try:
            while True:
                ev = self.events.get_nowait()
                kind = ev[0]
                if kind == "log":
                    self._log(ev[1])
                elif kind == "step":
                    _, index, total, text = ev
                    self.progress.configure(maximum=total, value=index)
                    self.step_label.configure(text=text)
                    self._log(f"\n=== {text} ===")
                elif kind == "done":
                    self._finish(bool(ev[1]))
                elif kind == "fatal":
                    self.btn.configure(state="normal")
                    self.step_label.configure(text="安装失败。")
                    messagebox.showerror(
                        APP_TITLE,
                        "安装过程中出现错误。\n\n"
                        f"{ev[1]}\n\n"
                        "请把“安装详情”里的内容发给技术支持。",
                    )
                elif kind == "ask_r":
                    self._ask_r()
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    def _ask_r(self) -> None:
        self.btn.configure(state="normal")
        self.step_label.configure(text="需要先安装 R。")
        again = messagebox.askretrycancel(
            APP_TITLE,
            "没有在电脑上找到可用的 R（统计分析环境）。\n\n"
            "请先到 https://cran.r-project.org/bin/windows/base/ 下载并安装 R，\n"
            "安装时全部点“下一步”即可，然后回到本窗口点击“重试”。\n\n"
            "如果安装包里有 _offline/r 文件夹，也可以把 R 安装器放进去后重试。",
        )
        if again:
            self._rearm()
            self._start()

    def _rearm(self) -> None:
        """Re-enable the controls and rerun the pre-install checks."""
        try:
            self.entry_root.configure(state="normal")
        except tk.TclError:
            pass
        self.btn.configure(state="normal")

    def _finish(self, ok: bool) -> None:
        self.btn.configure(state="normal")
        self.progress.configure(value=self.progress.cget("maximum"))
        if ok:
            self.step_label.configure(text="安装完成。")
            gui = self.ctx.app / "nanoamp.exe"
            steps = []
            if self.ctx.make_shortcut:
                steps.append("1）双击桌面上的「nanoamp 分析工具」打开图形界面；")
            else:
                steps.append(f"1）双击这个文件打开图形界面：\n   {gui}")
            steps.append("2）选好测序文件和目的序列，点「开始分析」；")
            steps.append("3）结果会显示在同一个窗口里。")
            tail = [f"\n安装位置：{self.ctx.install_root}"]
            if self.ctx.touch_path:
                tail.append("命令行用法：新开一个命令行窗口，输入 nanoamp doctor")
            else:
                tail.append(f"命令行用法：{self.ctx.bin}\\nanoamp.cmd doctor（未加入 PATH）")
            messagebox.showinfo(
                APP_TITLE,
                "安装完成！\n\n接下来可以这样使用：\n\n"
                + "\n".join(steps)
                + "\n"
                + "\n".join(tail),
            )
        else:
            self.step_label.configure(text="安装未全部成功，请查看安装详情。")
            messagebox.showwarning(
                APP_TITLE,
                "安装没有完全成功。\n\n请查看「安装详情」里的信息，或修好问题后重试一次。",
            )

    def run(self) -> int:
        self.root.mainloop()
        return 0


def _configure_console() -> None:
    """Make console output survive non-UTF-8 code pages.

    The console modes print Chinese. A frozen windowed build inherits the OEM
    code page for stdout, and printing a character it cannot encode raises
    UnicodeEncodeError. Reconfigure with errors="replace" so output degrades
    instead of crashing.
    """
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def _report_status() -> int:
    """Print what is currently installed. Exit 0 if usable, 2 otherwise."""
    ok = True

    found = common.find_existing_install()
    if found is None:
        home = install_home()
        print(f"nanoamp 安装目录 : {home}  {'存在' if home.is_dir() else '不存在'}")
        print("\n状态：未安装（没有找到 config.ini）")
        return 2

    home, cfg = found
    lib = _lib_subdir(home)
    installed = common.looks_installed(home)
    print(f"nanoamp 安装目录 : {home}  {'存在' if home.is_dir() else '不存在'}")
    if not installed:
        ok = False
        print("                  （该目录下没有找到已安装的 nanoamp）")

    rscript = find_rscript()
    if rscript:
        ver = r_version(rscript)
        print(f"R 运行环境       : {rscript}  ({'%d.%d' % ver if ver else '版本未知'})")
        if not r_supported(rscript):
            ok = False
            print("                  版本过低，需要 R >= %d.%d" % (MIN_R_MAJOR, MIN_R_MINOR))
    else:
        ok = False
        print("R 运行环境       : 未找到")

    pkg = lib / PACKAGE_NAME
    print(f"{PACKAGE_NAME} 包      : {'已安装' if pkg.is_dir() else '未安装'}  ({lib})")
    if not pkg.is_dir():
        ok = False

    exe = _app_subdir(home) / "nanoamp.exe"
    print(f"图形界面         : {'已安装' if exe.is_file() else '未安装'}  ({exe})")

    cmd = _bin_subdir(home) / "nanoamp.cmd"
    print(f"命令行包装       : {'已安装' if cmd.is_file() else '未安装'}  ({cmd})")

    mm = _bin_subdir(home) / "minimap2.exe"
    print(f"比对程序         : {'已安装' if mm.is_file() else '未安装'}  ({mm})")

    link = shortcut_path()
    print(f"桌面快捷方式     : {'已创建' if link.is_file() else '未创建'}")

    cfg_path = home / CONFIG_FILE
    if cfg_path.is_file():
        print(f"配置文件         : {cfg_path}")
        print(cfg_path.read_text(encoding="utf-8").strip())

    print("\n状态：" + ("可用" if ok else "不完整，请重新运行安装程序"))
    return 0 if ok else 2


def _parse_install_dir(argv: list[str]) -> Path | None:
    """Read ``--install-dir <path>`` from the command line."""
    for i, arg in enumerate(argv):
        if arg == "--install-dir" and i + 1 < len(argv):
            return Path(argv[i + 1])
        if arg.startswith("--install-dir="):
            return Path(arg.split("=", 1)[1])
    return None


def main() -> int:
    """Entry point.

    With no arguments the graphical installer opens, where the install
    location and the desktop-shortcut option can be changed.

    The console modes exist so the same code path can be exercised without a
    display (CI, testing, deployment scripts):

        install.exe --silent                    install, report on stdout
        install.exe --check                     report what is installed
        install.exe --silent --no-shortcut      skip the desktop shortcut
        install.exe --silent --no-path          do not touch PATH
        install.exe --silent --install-dir D:\\nanoamp
    """
    argv = sys.argv[1:]

    if "--check" in argv:
        _configure_console()
        return _report_status()

    if "--silent" in argv:
        _configure_console()
        chosen = _parse_install_dir(argv)
        ctx = Context(
            root=app_dir(),
            install_root=chosen if chosen else common.default_install_home(),
            make_shortcut="--no-shortcut" not in argv,
            touch_path="--no-path" not in argv,
        )
        events: queue.Queue = queue.Queue()
        installer = Installer(ctx, events)

        def pump() -> bool:
            ok = True
            while True:
                try:
                    ev = events.get_nowait()
                except queue.Empty:
                    break
                if ev[0] == "log":
                    print(ev[1], flush=True)
                elif ev[0] == "step":
                    print(f"\n=== {ev[3]} ===", flush=True)
                elif ev[0] == "done":
                    ok = bool(ev[1])
                elif ev[0] in ("fatal", "ask_r"):
                    ok = False
            return ok

        result = {"ok": False}

        def target() -> None:
            result["ok"] = installer.run_all()

        th = threading.Thread(target=target, daemon=True)
        th.start()
        # Drain periodically so the console shows progress while it runs.
        while th.is_alive():
            pump()
            time.sleep(0.2)
        th.join()
        pump()
        print("\n安装成功。" if result["ok"] else "\n安装未完成。", flush=True)
        return 0 if result["ok"] else 1

    # Development machines may not have the payload next to the script.
    if not (app_dir() / "_offline").is_dir():
        print("警告：未找到 _offline 目录，安装包可能不完整。", file=sys.stderr)

    return InstallerWindow().run()


if __name__ == "__main__":
    raise SystemExit(main())
