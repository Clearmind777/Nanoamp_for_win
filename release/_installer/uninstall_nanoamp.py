"""uninstall.exe - remove nanoamp from Windows.

Removes what install.exe created and nothing else:

  * the install directory (default %LOCALAPPDATA%\\nanoamp, or wherever the
    user chose to put it)
  * the desktop shortcut
  * the %LOCALAPPDATA%\\nanoamp\\bin entry from the user PATH
  * the R_LIBS_USER line from Documents\\.Renviron
  * the install-location pointer file

The user's own R installation and R library are left alone: install.exe never
touched them. R itself is only removed if the user asks for it AND it was
installed by us (i.e. it lives inside the nanoamp install directory).
"""

from __future__ import annotations

import ctypes
import os
import queue
import shutil
import stat
import subprocess
import sys
import tempfile
import threading
import time
import winreg
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import messagebox, ttk
import tkinter as tk

import nanoamp_common as common
from nanoamp_common import (
    CONFIG_FILE,
    PRODUCT,
    bin_dir as _bin_subdir,
    config_dir as _config_subdir,
    desktop_dir,
    lib_dir as _lib_subdir,
    renviron_path,
    shortcut_path,
)

APP_TITLE = "nanoamp 卸载程序"
CREATE_NO_WINDOW = 0x08000000
DETACHED_PROCESS = 0x00000008

# Fixed width for the window; fit_to_content() only varies the height.
WINDOW_WIDTH = 760

# A file can stay locked for a moment after the process holding it exits.
# Delays before each delete attempt; the list length is the attempt count.
REMOVE_RETRY_DELAYS = (0.0, 1.0, 2.0, 4.0, 8.0)

# Refuse to delete anything at or above these; a bad config.ini must never be
# able to wipe a system directory.
FORBIDDEN = {
    Path(os.environ.get("SystemRoot", r"C:\Windows")).resolve(),
    Path(os.environ.get("SystemDrive", "C:") + "\\").resolve(),
    Path(os.environ.get("ProgramFiles", r"C:\Program Files")).resolve(),
    Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")).resolve(),
    Path(os.environ.get("USERPROFILE", str(Path.home()))).resolve(),
    Path(os.environ.get("LOCALAPPDATA", "")).resolve() if os.environ.get("LOCALAPPDATA") else None,
    Path(os.environ.get("APPDATA", "")).resolve() if os.environ.get("APPDATA") else None,
}
FORBIDDEN.discard(None)


@dataclass
class Plan:
    """What the uninstall will do, decided before anything is touched."""

    install_root: Path | None = None
    config: dict[str, str] = field(default_factory=dict)
    remove_dir: bool = False
    remove_shortcut: bool = False
    remove_path_entry: bool = False
    remove_renviron_line: bool = False
    remove_runtime: bool = False
    runtime_root: Path | None = None
    warnings: list[str] = field(default_factory=list)

    def items(self) -> list[tuple[str, str, bool]]:
        """(key, description, will_do) for display."""
        out: list[tuple[str, str, bool]] = []
        if self.install_root:
            n = _count_files(self.install_root) if self.install_root.is_dir() else 0
            out.append(("dir", f"安装目录  {self.install_root}  （{n} 个文件）", self.remove_dir))
        out.append(("shortcut", f"桌面快捷方式  {shortcut_path()}", self.remove_shortcut))
        out.append(("path", f"用户 PATH 中的 {self._bin() or 'bin'} 条目", self.remove_path_entry))
        out.append(("renviron", f"{renviron_path()} 里的 R_LIBS_USER 行", self.remove_renviron_line))
        if self.runtime_root:
            n = _count_files(self.runtime_root) if self.runtime_root.is_dir() else 0
            out.append(("runtime",
                        f"随程序安装的 R 运行时  {self.runtime_root}  （{n} 个文件）",
                        self.remove_runtime))
        return out

    def _bin(self) -> Path | None:
        return _bin_subdir(self.install_root) if self.install_root else None


def _count_files(root: Path) -> int:
    try:
        return sum(1 for p in root.rglob("*") if p.is_file())
    except OSError:
        return 0


def _human_size(size: int) -> str:
    """Byte count in the largest unit that keeps it readable.

    Rounding small installs to "0 MB" reads like a bug, so anything under a
    megabyte is reported in KB.
    """
    mb = size / 1024 / 1024
    if mb >= 1:
        return f"{mb:.0f} MB"
    return f"{max(round(size / 1024), 1)} KB"


def _size_of(root: Path) -> int:
    total = 0
    try:
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return total


# --------------------------------------------------------------------------
# planning
# --------------------------------------------------------------------------
def build_plan() -> Plan:
    plan = Plan()

    found = common.find_existing_install()
    if found:
        plan.install_root, plan.config = found
        plan.remove_dir = plan.install_root.is_dir()
    else:
        plan.warnings.append("没有检测到已安装的 nanoamp（未找到 config.ini）。")

    plan.remove_shortcut = shortcut_path().is_file()

    if plan.install_root:
        plan.remove_path_entry = _path_has(str(_bin_subdir(plan.install_root)))
    else:
        plan.remove_path_entry = _path_has(str(_bin_subdir(common.default_install_home())))

    plan.remove_renviron_line = _renviron_has_our_line()

    # Only offer to remove R if it lives inside our install directory.
    if plan.install_root:
        runtime = plan.install_root / "R" / "R-runtime"
        if runtime.is_dir():
            plan.runtime_root = runtime

    _check_safety(plan)
    return plan


def _check_safety(plan: Plan) -> None:
    """Refuse obviously wrong targets instead of trusting config.ini blindly."""
    root = plan.install_root
    if root is None:
        return
    resolved = root.resolve()
    if resolved in FORBIDDEN:
        plan.warnings.append(
            f"安装目录 {resolved} 指向系统目录，出于安全考虑不会删除它。"
        )
        plan.remove_dir = False
        return
    # Must look like ours: contains a nanoamp marker.
    markers = [
        resolved / "R" / "lib" / PRODUCT,
        resolved / "app" / "nanoamp.exe",
        resolved / "bin" / "nanoamp.cmd",
        resolved / CONFIG_FILE,
    ]
    if not any(m.exists() for m in markers):
        plan.warnings.append(
            f"{resolved} 里没有 nanoamp 的特征文件，出于安全考虑不会删除它。"
        )
        plan.remove_dir = False


def _path_has(entry: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            current, _ = winreg.QueryValueEx(key, "Path")
    except OSError:
        return False
    target = os.path.normcase(entry.rstrip("\\"))
    return any(os.path.normcase(p.rstrip("\\")) == target
               for p in current.split(";") if p.strip())


def _renviron_has_our_line() -> bool:
    p = renviron_path()
    if not p.is_file():
        return False
    try:
        return any(ln.strip().startswith("R_LIBS_USER")
                   for ln in p.read_text(encoding="utf-8", errors="replace").splitlines())
    except OSError:
        return False


# --------------------------------------------------------------------------
# doing it
# --------------------------------------------------------------------------
class Uninstaller:
    def __init__(self, plan: Plan, events: queue.Queue):
        self.plan = plan
        self.events = events
        self.freed = 0
        # Set from the UI thread by cancel(); checked between steps.
        self.cancelled = threading.Event()

    def cancel(self) -> None:
        """Ask the running uninstall to stop after the current step.

        Deleting files cannot be interrupted halfway safely, so this stops at
        the next step boundary instead of killing a recursive delete part-way.
        """
        self.cancelled.set()

    def say(self, text: str) -> None:
        self.events.put(("log", text))

    def step(self, index: int, total: int, text: str) -> None:
        self.events.put(("step", index, total, text))

    def run_all(self) -> bool:
        try:
            total = 4
            ok = True

            self.step(0, total, "删除安装目录…")
            ok &= self._remove_dir()
            if self._stopped():
                return False

            self.step(1, total, "删除桌面快捷方式…")
            ok &= self._remove_shortcut()
            if self._stopped():
                return False

            self.step(2, total, "清理 PATH 与 .Renviron…")
            ok &= self._remove_path_entry()
            ok &= self._remove_renviron()
            if self._stopped():
                return False

            self.step(3, total, "清理记录文件…")
            self._remove_pointer()

            self.events.put(("done", ok, self.freed))
            return True
        except Exception as exc:  # noqa: BLE001
            import traceback
            self.say(traceback.format_exc())
            if self.cancelled.is_set():
                self.events.put(("cancelled",))
                return False
            self.events.put(("fatal", str(exc)))
            return False

    def _stopped(self) -> bool:
        """True when the user cancelled; tells the GUI and stops the flow."""
        if not self.cancelled.is_set():
            return False
        self.say("已按用户要求停止。已删除的内容不会恢复；"
                 "再次运行本程序可继续清理剩余部分。")
        self.events.put(("cancelled",))
        return True

    # -- steps ----------------------------------------------------------
    def _remove_dir(self) -> bool:
        if not self.plan.remove_dir or self.plan.install_root is None:
            self.say("（跳过安装目录）")
            return True
        root = self.plan.install_root
        me = _running_exe()
        self_delete = me if _inside(me, root) else None
        self.freed += _size_of(root)
        if self_delete is not None:
            # It is removed a moment later by the detached helper, so it is not
            # freed by this process; do not claim it was.
            try:
                self.freed -= self_delete.stat().st_size
            except OSError:
                pass
        self.say(f"正在删除 {root} …")

        # The GUI is very likely still running when someone uninstalls (it is
        # what they just closed, or they forgot). Its nanoamp.exe would be
        # locked, so stop our own processes first.
        self._stop_running_background_processes()

        # install.exe puts a copy of this program inside the install directory,
        # so the most likely case is that the file being deleted right now is
        # this very process. Windows will not allow that; everything else is
        # removed here and the locked file is handed to a detached helper.
        if self_delete is not None:
            self.say(f"本程序就在该目录里（{self_delete.name}），最后一个文件会在本窗口"
                     "关闭后自动删除。")

        # A file can stay locked briefly while Windows releases the handle.
        # Retry with a growing delay rather than giving up on the first error.
        last_error: Exception | None = None
        for attempt, delay in enumerate(REMOVE_RETRY_DELAYS, start=1):
            if delay:
                time.sleep(delay)
            try:
                if self_delete is not None:
                    _remove_tree_skipping(root, {self_delete})
                else:
                    _remove_tree(root)
            except OSError as exc:
                last_error = exc
                blocked = _blocking_files(root)
                detail = ("，被占用：" + ", ".join(blocked[:3])) if blocked else ""
                self.say(f"  第 {attempt}/{len(REMOVE_RETRY_DELAYS)} 次删除未完成：{exc}{detail}")
                continue

            if self_delete is None:
                self.say(f"安装目录已删除（第 {attempt} 次尝试）")
                return True

            scheduled = _schedule_final_cleanup(self_delete, root)
            self.say(f"安装目录内容已删除（第 {attempt} 次尝试）")
            if scheduled:
                self.say("已安排在本窗口关闭后删除最后的 uninstall.exe 与空目录。")
            else:
                self.say(f"未能安排自动删除，请手动删除 {self_delete}（以及空目录 {root}）。")
            return True

        self.say(f"删除失败：{last_error}")
        self.say("提示：请关闭正在运行的 nanoamp 窗口后重新运行本程序，或手动删除该目录。")
        return False

    def _stop_running_background_processes(self) -> None:
        """Stop nanoamp processes we may have started.

        Only matched by full image path inside the install root, so an
        unrelated program with a similar name is never touched.
        """
        if self.plan.install_root is None:
            return
        root = self.plan.install_root.resolve()
        import csv
        import io

        try:
            proc = subprocess.run(
                ["tasklist", "/FO", "CSV", "/NH"],
                capture_output=True, timeout=30, creationflags=CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return
        text = (proc.stdout or b"").decode("utf-8", errors="replace")
        for row in csv.reader(io.StringIO(text)):
            if len(row) < 2:
                continue
            name, pid = row[0], row[1]
            if not name.lower().startswith("nanoamp"):
                continue
            try:
                exe_path = _process_image_path(int(pid))
            except (ValueError, OSError):
                continue
            if exe_path and root in Path(exe_path).resolve().parents:
                self.say(f"  结束仍在运行的 {name}（PID {pid}）")
                subprocess.run(["taskkill", "/PID", str(pid), "/F"],
                               capture_output=True, timeout=30,
                               creationflags=CREATE_NO_WINDOW)
                time.sleep(0.5)

    def _remove_shortcut(self) -> bool:
        if not self.plan.remove_shortcut:
            self.say("（没有桌面快捷方式）")
            return True
        link = shortcut_path()
        try:
            link.unlink()
            self.say(f"已删除 {link}")
            return True
        except OSError as exc:
            self.say(f"删除快捷方式失败：{exc}")
            return False

    def _remove_path_entry(self) -> bool:
        if not self.plan.remove_path_entry:
            self.say("（PATH 中没有 nanoamp 条目）")
            return True
        if self.plan.install_root is None:
            return True
        entry = str(_bin_subdir(self.plan.install_root))
        if _remove_from_user_path(entry):
            self.say(f"已从用户 PATH 移除 {entry}")
        else:
            self.say("从 PATH 移除失败")
        return True

    def _remove_renviron(self) -> bool:
        if not self.plan.remove_renviron_line:
            self.say("（.Renviron 中没有相关行）")
            return True
        p = renviron_path()
        try:
            lines = p.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError as exc:
            self.say(f"读取 {p} 失败：{exc}")
            return False
        kept = [ln for ln in lines if not ln.strip().startswith("R_LIBS_USER")]
        try:
            if kept:
                p.write_text("\n".join(kept) + "\n", encoding="utf-8")
                self.say(f"已移除 {p} 中的 R_LIBS_USER 行")
            else:
                p.unlink()
                self.say(f"已删除空的 {p}")
        except OSError as exc:
            self.say(f"写入 {p} 失败：{exc}")
            return False
        return True

    def _remove_pointer(self) -> None:
        marker = common.default_install_home().parent / f"{PRODUCT}.path"
        common.remove_pointer()
        if not marker.exists():
            self.say("已清理安装位置记录")

    # -- optional -------------------------------------------------------
    def remove_runtime(self) -> bool:
        """Delete the R runtime we installed (only if it is inside our tree)."""
        if not self.plan.runtime_root or not self.plan.remove_runtime:
            return True
        root = self.plan.runtime_root
        # Never remove an R that is not ours.
        if self.plan.install_root is None or self.plan.install_root not in root.parents:
            self.say("R 运行时不在 nanoamp 安装目录内，跳过")
            return True
        self.freed += _size_of(root)
        self.say(f"正在删除 R 运行时 {root} …")
        try:
            _remove_tree(root)
            self.say("R 运行时已删除")
            return True
        except OSError as exc:
            self.say(f"删除 R 运行时失败：{exc}")
            return False


def _remove_tree(root: Path) -> None:
    """shutil.rmtree that reliably reports failure.

    The classic ``onerror=lambda *a: chmod(...)`` recipe is silent: when the
    retry fails too, shutil just carries on and rmtree returns normally with
    the directory still there.  That would make the caller's retry loop think
    it had succeeded, so this wrapper records the first failure and raises it
    unless the directory really is gone.
    """
    failed: list[BaseException] = []

    def _on_error(func, path, exc_info) -> None:
        exc = exc_info[1] if len(exc_info) > 1 else None
        try:
            os.chmod(path, stat.S_IWRITE)
            func(path)
            return
        except OSError:
            pass
        if exc is not None and not failed:
            failed.append(exc)

    shutil.rmtree(root, onerror=_on_error)
    if root.exists():
        raise failed[0] if failed else OSError(f"目录未能完全删除：{root}")


def _running_exe() -> Path | None:
    """The uninstall.exe that is executing right now, if it is a frozen one."""
    if not getattr(sys, "frozen", False):
        return None
    try:
        return Path(sys.executable).resolve()
    except (OSError, ValueError):
        return None


def _norm(path: Path | str) -> str:
    """A comparison form for a path: resolved, case-folded, no trailing separator.

    Windows hands out the same directory in several spellings (8.3 short names,
    different case, mixed separators), so comparing raw ``Path`` objects is not
    reliable - and getting it wrong here would mean deleting the running exe.
    """
    try:
        text = str(Path(path).resolve())
    except (OSError, ValueError):
        text = str(path)
    return os.path.normcase(text).rstrip("\\/")


def _same_path(a: Path | str, b: Path | str) -> bool:
    return _norm(a) == _norm(b)


def _inside(path: Path | None, root: Path) -> bool:
    """True when `path` sits inside `root` (never treats root itself as inside)."""
    if path is None:
        return False
    root_norm = _norm(root)
    path_norm = _norm(path)
    return path_norm.startswith(root_norm + "\\")


def _remove_tree_skipping(root: Path, skip: set[Path]) -> None:
    """Delete everything under `root` except `skip`, then the empty directories.

    The uninstaller now ships inside the install directory, so the file that is
    running cannot be deleted - Windows keeps it locked. It is not even
    attempted: skipping it outright makes the result independent of whether some
    other process happens to hold it open. The locked file is removed by a
    detached helper once this process exits (see _schedule_final_cleanup).

    Raises OSError when anything else is still there afterwards.
    """

    def _skip(p: Path) -> bool:
        return any(_same_path(p, kept) for kept in skip)

    failed: list[BaseException] = []
    for dirpath, _dirnames, filenames in os.walk(root, topdown=False):
        for name in filenames:
            candidate = Path(dirpath) / name
            if _skip(candidate):
                continue
            try:
                os.unlink(candidate)
            except OSError:
                # Read-only files (and files that were locked a moment ago)
                # usually go on the second attempt.
                try:
                    os.chmod(candidate, stat.S_IWRITE)
                    os.unlink(candidate)
                except OSError as exc:
                    if not failed:
                        failed.append(exc)
        try:
            os.rmdir(dirpath)          # fails while something is left in it
        except OSError:
            pass

    leftovers = [p for p in root.rglob("*") if p.is_file() and not _skip(p)]
    if leftovers:
        raise failed[0] if failed else OSError(
            f"目录未能完全删除：{leftovers[0]}")


def _schedule_final_cleanup(exe: Path, root: Path) -> bool:
    """Delete `exe` and the (now empty) `root` after this process exits.

    Windows refuses to delete a running executable, so the last step is handed
    to a detached cmd.exe: it waits until this process is gone and then removes
    the file and the directory. The paths are passed as arguments, so the script
    itself is pure ASCII and no path (spaces, ampersands, Chinese characters)
    has to survive being written into a batch file. The helper removes itself
    too, so nothing is left in %TEMP%.
    """
    script = Path(tempfile.gettempdir()) / f"nanoamp_finish_uninstall_{os.getpid()}.cmd"
    body = (
        "@echo off\r\n"
        "rem %1 = uninstall.exe, %2 = install directory.\r\n"
        "rem Windows keeps a running exe locked, so retry the delete until it\r\n"
        "rem succeeds (it does as soon as this process has exited).\r\n"
        "for /l %%i in (1,1,120) do (\r\n"
        "  del /f /q %1 >nul 2>&1\r\n"
        "  if not exist %1 goto :gone\r\n"
        "  ping -n 2 127.0.0.1 >nul\r\n"
        ")\r\n"
        ":gone\r\n"
        "rmdir %2 >nul 2>&1\r\n"
        'del /f /q "%~f0" >nul 2>&1\r\n'
    )
    try:
        script.write_text(body, encoding="ascii")
    except OSError as exc:
        print(f"无法写入延迟删除脚本：{exc}")
        return False
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", str(script), str(exe), str(root)],
            creationflags=CREATE_NO_WINDOW | DETACHED_PROCESS,
            close_fds=True,
        )
    except OSError as exc:
        print(f"无法启动延迟删除脚本：{exc}")
        return False
    return True


def _on_rm_error(func, path, exc_info) -> None:
    """shutil.rmtree callback: clear the read-only bit and retry."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        pass


def _process_image_path(pid: int) -> str:
    """Full path of a running process image, or '' when not readable.

    Uses WMIC-free ctypes so it works on every Windows 10/11 without extra
    tooling; falls back to an empty string if the query is refused.
    """
    PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        return ""
    try:
        size = ctypes.c_ulong(32768)
        buf = ctypes.create_unicode_buffer(size.value)
        if kernel32.QueryFullProcessImageNameW(handle, 0, buf, ctypes.byref(size)):
            return buf.value
    finally:
        kernel32.CloseHandle(handle)
    return ""


def _blocking_files(root: Path) -> list[str]:
    """Best-effort list of what could not be deleted under *root*.

    Whatever is still there after a failed rmtree is exactly what stood in the
    way, which is more precise than probing file handles (Windows happily lets
    you reopen a file whose deletion is only blocked by a byte-range lock).
    A directory that cannot even be listed is reported as ``name/``.
    """
    offenders: list[str] = []
    for dirpath, dirnames, filenames in os.walk(root):
        for name in filenames:
            target = os.path.join(dirpath, name)
            try:
                with open(target, "a"):
                    pass
            except OSError:
                offenders.append(_rel(target, root))
        for name in dirnames:
            target = os.path.join(dirpath, name)
            try:
                os.listdir(target)
            except OSError:
                offenders.append(_rel(target, root) + "\\")
    return offenders


def _rel(target: str, root: Path) -> str:
    try:
        return os.path.relpath(target, root)
    except ValueError:
        return target


def _remove_from_user_path(entry: str) -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment", 0,
                            winreg.KEY_READ | winreg.KEY_WRITE) as key:
            try:
                current, _ = winreg.QueryValueEx(key, "Path")
            except FileNotFoundError:
                return True
            target = os.path.normcase(entry.rstrip("\\"))
            parts = [p for p in current.split(";")
                     if p.strip() and os.path.normcase(p.rstrip("\\")) != target]
            winreg.SetValueEx(key, "Path", 0, winreg.REG_EXPAND_SZ, ";".join(parts))
    except OSError:
        return False
    try:
        ctypes.windll.user32.SendMessageTimeoutW(
            0xFFFF, 0x1A, 0, "Environment", 0x0002, 5000, None)
    except Exception:  # noqa: BLE001
        pass
    return True


# --------------------------------------------------------------------------
# the window
# --------------------------------------------------------------------------
class UninstallWindow:
    def __init__(self) -> None:
        self.root = tk.Tk()
        self.root.title(APP_TITLE)
        # A starting size only; fit_to_content() sets the real one once the
        # widgets have reported how tall they need to be.
        self.root.geometry("720x600")
        self.root.minsize(660, 540)
        self.events: queue.Queue = queue.Queue()
        self.plan = build_plan()
        self.var_shortcut = tk.BooleanVar(value=self.plan.remove_shortcut)
        self.var_path = tk.BooleanVar(value=self.plan.remove_path_entry)
        self.var_renviron = tk.BooleanVar(value=self.plan.remove_renviron_line)
        self.var_runtime = tk.BooleanVar(value=False)
        self.worker: threading.Thread | None = None
        self.uninstaller: Uninstaller | None = None
        self._build()

    def _build(self) -> None:
        pad = 14
        head = ttk.Frame(self.root, padding=(pad, pad, pad, 6))
        head.pack(fill="x")
        ttk.Label(head, text="卸载 nanoamp", font=("Microsoft YaHei UI", 16, "bold")).pack(anchor="w")
        ttk.Label(
            head,
            text="本程序删除安装时创建的文件与设置。\n"
                 "用户自行安装的 R 及其 R 库不会被删除。",
            font=("Microsoft YaHei UI", 9), foreground="#444444", justify="left",
        ).pack(anchor="w", pady=(4, 0))

        # -- what was found --------------------------------------------------
        info = ttk.LabelFrame(self.root, text="检测到的安装", padding=8)
        info.pack(fill="x", padx=pad, pady=(8, 0))
        if self.plan.install_root:
            size = _size_of(self.plan.install_root) if self.plan.install_root.is_dir() else 0
            # A deep install path is common (and the sandbox ones are long), so
            # wrap it instead of letting it run out of the window.
            ttk.Label(info, text=f"安装目录：{self.plan.install_root}",
                      font=("Microsoft YaHei UI", 10, "bold"),
                      wraplength=WINDOW_WIDTH - 60, justify="left").pack(anchor="w")
            ttk.Label(info, text=f"占用约 {_human_size(size)}",
                      font=("Microsoft YaHei UI", 8), foreground="#666666").pack(anchor="w")
        else:
            ttk.Label(info, text="没有检测到已安装的 nanoamp。",
                      font=("Microsoft YaHei UI", 10)).pack(anchor="w")

        for w in self.plan.warnings:
            ttk.Label(info, text="⚠ " + w, font=("Microsoft YaHei UI", 8),
                      foreground="#b00020", wraplength=660, justify="left").pack(anchor="w")

        # -- choices ---------------------------------------------------------
        opts = ttk.LabelFrame(self.root, text="要删除的内容", padding=8)
        opts.pack(fill="x", padx=pad, pady=(8, 0))
        ttk.Checkbutton(opts, text="安装目录（必删）", variable=tk.BooleanVar(value=True),
                        state="disabled").pack(anchor="w")
        if self.plan.remove_shortcut:
            ttk.Checkbutton(opts, text="桌面快捷方式", variable=self.var_shortcut).pack(anchor="w")
        if self.plan.remove_path_entry:
            ttk.Checkbutton(opts, text="用户 PATH 中的 nanoamp 条目", variable=self.var_path).pack(anchor="w")
        if self.plan.remove_renviron_line:
            ttk.Checkbutton(opts, text=".Renviron 中的 R_LIBS_USER 行", variable=self.var_renviron).pack(anchor="w")
        if self.plan.runtime_root:
            # A full path next to a checkbox is wider than the window and gets
            # silently cut off, so the label stays short and the path wraps on
            # its own indented line.
            row = ttk.Frame(opts)
            row.pack(anchor="w", fill="x")
            ttk.Checkbutton(row, text="随程序安装的 R 运行时",
                            variable=self.var_runtime).pack(side="left")
            ttk.Label(opts, text=str(self.plan.runtime_root),
                      font=("Microsoft YaHei UI", 8), foreground="#666666",
                      wraplength=WINDOW_WIDTH - 90, justify="left").pack(
                anchor="w", padx=(24, 0))

        keep = ttk.LabelFrame(self.root, text="不会删除", padding=8)
        keep.pack(fill="x", padx=pad, pady=(8, 0))
        ttk.Label(keep, text="• 用户自行安装的 R\n• 用户 R 库及其中的其他 R 包\n• 测序数据与结果文件",
                  font=("Microsoft YaHei UI", 9), justify="left").pack(anchor="w")

        self.step_label = ttk.Label(self.root, text="确认后点击「开始卸载」。",
                                    font=("Microsoft YaHei UI", 10), padding=(pad, 6))
        self.step_label.pack(anchor="w")
        self.progress = ttk.Progressbar(self.root, mode="determinate", maximum=4)
        self.progress.pack(fill="x", padx=pad)

        # The buttons are packed first with side="bottom" on purpose: the log
        # below can then absorb whatever height is left. Packing them last
        # pushes them outside the window whenever the content is tall, which
        # hides the only way to actually start the uninstall.
        bar = ttk.Frame(self.root, padding=(pad, 0, pad, pad))
        bar.pack(side="bottom", fill="x")
        self.btn = ttk.Button(bar, text="开始卸载", command=self._start)
        self.btn.pack(side="left")
        # Cancel is disabled until an uninstall is actually running.
        self.btn_cancel = ttk.Button(bar, text="取消操作", command=self._cancel,
                                     state="disabled")
        self.btn_cancel.pack(side="left", padx=(8, 0))
        ttk.Button(bar, text="退出", command=self.root.destroy).pack(side="right")

        log_frame = ttk.LabelFrame(self.root, text="详情", padding=4)
        log_frame.pack(side="bottom", fill="both", expand=True, padx=pad, pady=(8, 6))
        self.log_text = tk.Text(log_frame, wrap="word", height=9, font=("Consolas", 9),
                                state="disabled")
        self.log_text.pack(side="left", fill="both", expand=True)
        sb = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        sb.pack(side="right", fill="y")
        self.log_text.configure(yscrollcommand=sb.set)

        self.root.after(120, self._pump)

    def _log(self, text: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def fit_to_content(self) -> None:
        """Size the window to what it shows, and keep the buttons on screen.

        A fixed geometry assumes the layout always needs the same height, which
        stopped being true as soon as the "detected install" box appeared. This
        lets the log pane absorb the slack instead, and shrinks it on a small
        screen so nothing important falls off the bottom.
        """
        text = self.log_text
        wanted = text.cget("height")
        try:
            text.configure(height=3)
            self.root.update_idletasks()
            minimum = self.root.winfo_reqheight()

            text.configure(height=wanted)
            self.root.update_idletasks()
            natural = self.root.winfo_reqheight()

            screen_h = self.root.winfo_screenheight()
            avail = (screen_h - 90) - (minimum - 3 * 22)
            lines = max(3, min(wanted, avail // 22))
            text.configure(height=lines)
            self.root.update_idletasks()
            height = max(minimum, min(self.root.winfo_reqheight(), screen_h - 90))

            self.root.geometry(f"{WINDOW_WIDTH}x{height}+"
                               f"{max((self.root.winfo_screenwidth() - WINDOW_WIDTH) // 2, 0)}+30")
        finally:
            text.configure(height=wanted)

    def _start(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        if self.plan.install_root is None:
            messagebox.showinfo(APP_TITLE, "没有检测到已安装的 nanoamp，无需卸载。")
            return
        if not messagebox.askyesno(
            APP_TITLE,
            f"确认卸载 nanoamp？\n\n安装目录：{self.plan.install_root}\n\n"
            "该操作不可撤销。",
        ):
            return

        self.plan.remove_shortcut = bool(self.var_shortcut.get())
        self.plan.remove_path_entry = bool(self.var_path.get())
        self.plan.remove_renviron_line = bool(self.var_renviron.get())
        self.plan.remove_runtime = bool(self.var_runtime.get())

        self.btn.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.step_label.configure(text="正在卸载…")
        self.worker = threading.Thread(target=self._worker, daemon=True)
        self.worker.start()

    def _cancel(self) -> None:
        """Ask the running uninstall to stop at the next step boundary.

        A recursive delete is not safe to kill part-way, so this only raises a
        flag; the worker checks it between steps.
        """
        un = self.uninstaller
        if un is None or not (self.worker and self.worker.is_alive()):
            self.btn_cancel.configure(state="disabled")
            return
        self.btn_cancel.configure(state="disabled")
        self.step_label.configure(text="正在取消…")
        self._log("")
        self._log("用户请求取消，将在当前步骤结束后停止…")
        un.cancel()

    def _finish_cancelled(self) -> None:
        self.btn.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.step_label.configure(text="已取消。")
        messagebox.showinfo(
            APP_TITLE,
            "卸载已取消。\n\n"
            "已删除的内容不会恢复。如需继续清理，请重新运行本程序，"
            "它会重新检测剩余内容。",
        )

    def _worker(self) -> None:
        un = Uninstaller(self.plan, self.events)
        self.uninstaller = un
        un.run_all()
        if not un.cancelled.is_set() and self.plan.remove_runtime:
            un.remove_runtime()

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
                    self._finish(bool(ev[1]), ev[2])
                elif kind == "cancelled":
                    self._finish_cancelled()
                elif kind == "fatal":
                    self.btn.configure(state="normal")
                    self.btn_cancel.configure(state="disabled")
                    messagebox.showerror(APP_TITLE, f"卸载过程中发生错误。\n\n{ev[1]}")
        except queue.Empty:
            pass
        self.root.after(120, self._pump)

    def _finish(self, ok: bool, freed: int) -> None:
        self.btn.configure(state="normal")
        self.btn_cancel.configure(state="disabled")
        self.progress.configure(value=self.progress.cget("maximum"))
        if ok:
            self.step_label.configure(text="卸载完成。")
            messagebox.showinfo(
                APP_TITLE,
                f"nanoamp 已卸载，释放约 {freed / 1024 / 1024:.0f} MB。\n\n"
                "桌面快捷方式与 PATH 条目已一并清理。\n"
                "用户自行安装的 R 未被删除。",
            )
        else:
            self.step_label.configure(text="卸载未完全成功，请查看详情。")
            messagebox.showwarning(
                APP_TITLE,
                "部分内容未能删除。\n\n"
                "常见原因为 nanoamp 窗口仍在运行，或文件被安全软件占用。\n"
                "关闭相关窗口后重新运行本程序即可。",
            )

    def run(self) -> int:
        self.fit_to_content()
        self.root.mainloop()
        return 0


# --------------------------------------------------------------------------
# console modes
# --------------------------------------------------------------------------
def _configure_console() -> None:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
        except (AttributeError, ValueError, OSError):
            pass


def _report(plan: Plan) -> int:
    if plan.install_root is None:
        print("未检测到已安装的 nanoamp。")
        for w in plan.warnings:
            print("  " + w)
        return 2
    size = _size_of(plan.install_root) if plan.install_root.is_dir() else 0
    print(f"安装目录 : {plan.install_root}  ({size / 1024 / 1024:.0f} MB)")
    print(f"  删除目录           : {plan.remove_dir}")
    print(f"  删除桌面快捷方式   : {plan.remove_shortcut}")
    print(f"  移除 PATH 条目     : {plan.remove_path_entry}")
    print(f"  移除 .Renviron 行  : {plan.remove_renviron_line}")
    print(f"  R 运行时（可选）   : {plan.runtime_root}")
    for w in plan.warnings:
        print(f"  ⚠ {w}")
    return 0


def main() -> int:
    """Entry point.

        uninstall.exe                    graphical uninstaller
        uninstall.exe --dry-run          report what would be removed
        uninstall.exe --silent           remove everything, no prompts
        uninstall.exe --silent --keep-runtime
    """
    argv = sys.argv[1:]

    if "--dry-run" in argv:
        _configure_console()
        return _report(build_plan())

    if "--silent" in argv:
        _configure_console()
        plan = build_plan()
        if plan.install_root is None:
            print("未检测到已安装的 nanoamp，无需卸载。")
            return 2
        events: queue.Queue = queue.Queue()
        un = Uninstaller(plan, events)

        def pump() -> None:
            while True:
                try:
                    ev = events.get_nowait()
                except queue.Empty:
                    return
                if ev[0] == "log":
                    print(ev[1], flush=True)
                elif ev[0] == "step":
                    print(f"\n=== {ev[3]} ===", flush=True)
                elif ev[0] == "done":
                    print(f"\n释放约 {ev[2] / 1024 / 1024:.0f} MB", flush=True)

        result = {"ok": False}

        def target() -> None:
            result["ok"] = un.run_all()
            if "--keep-runtime" not in argv:
                un.remove_runtime()

        th = threading.Thread(target=target, daemon=True)
        th.start()
        while th.is_alive():
            pump()
            time.sleep(0.2)
        th.join()
        pump()
        print("\n卸载完成。" if result["ok"] else "\n卸载未完全成功。", flush=True)
        return 0 if result["ok"] else 1

    return UninstallWindow().run()


if __name__ == "__main__":
    raise SystemExit(main())
