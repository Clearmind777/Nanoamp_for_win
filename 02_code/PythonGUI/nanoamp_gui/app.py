"""nanoamp GUI - a simple Tkinter window over the nanoamp R analysis.

The analysis logic lives in the ``nanoamp`` R package and is invoked exactly as
the CLI would invoke it (see ``r_runner``). Nothing is reimplemented here, so
the GUI and the command line can never disagree about results.

Tkinter is used deliberately: it ships with CPython, so there is no runtime
dependency to install and PyInstaller can freeze it into a single .exe.
"""

from __future__ import annotations

import csv
import json
import os
import queue
import subprocess
import sys
import tempfile
import threading
import traceback
import webbrowser
from datetime import datetime
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .r_runner import NanoampRunner, RNotFoundError, find_rscript

APP_TITLE = "nanoamp - 纳米孔 PCR 产物分析"
MODES = [
    ("A - 参考引导（默认）", "A"),
    ("B - 从头聚类", "B"),
    ("C - 精确匹配（诊断用）", "C"),
]

# Functional annotation: where the configuration comes from. The offline route
# is listed first because it needs no network at all -- the online route needs
# the Ensembl REST API (and therefore a working proxy/firewall path).
ANNOTATION_OFFLINE = "离线 CDS（不联网）"
ANNOTATION_ONLINE = "在线 genome（需联网，用 Ensembl）"
ANNOTATION_CUSTOM = "自定义 JSON…"
ANNOTATION_SOURCES = [ANNOTATION_OFFLINE, ANNOTATION_ONLINE, ANNOTATION_CUSTOM]

# Transcript picker: the first entry means "let nanoamp choose" (MANE Select,
# else Ensembl canonical). The rest are filled in by 「列出转录本」.
TRANSCRIPT_AUTO = "自动选择（MANE / 规范）"

# Kept in step with the geometry set in main(); used for label wrapping.
WINDOW_WIDTH = 1040
WINDOW_MIN_HEIGHT = 600

# run_manifest.json carries `error_class` for a failed run (P0-7). The GUI turns
# that single word into "what do I do now", instead of showing the same generic
# dialog for a typo in a path and for a firewall blocking Ensembl.
ERROR_CLASS_HINTS = {
    "input": (
        "输入或配置有问题。\n\n"
        "请检查：FASTQ / FASTA 是否选对且文件存在；注释配置是否为合法 JSON、"
        "CDS 长度是否为 3 的倍数。"
    ),
    "environment": (
        "运行环境有问题（R 包、外部工具或磁盘/权限）。\n\n"
        "请先点「环境自检」确认 R、依赖包与 minimap2；确认输出目录可写、"
        "磁盘未满；必要时重新运行安装器。"
    ),
    "network": (
        "网络不可达——在线注释需要访问 Ensembl。\n\n"
        "可以改用「离线 CDS（不联网）」配置再跑一次（不需要网络）；"
        "或者检查代理/防火墙后重试，必要时用 --cache-dir 指定缓存目录。"
    ),
    "internal": (
        "nanoamp 自身的错误（含自检不通过）。\n\n"
        "请把「运行日志」和输出目录里的 run_manifest.json 一起反馈。"
    ),
}

ERROR_CLASS_FALLBACK = (
    "分析未正常结束。常见原因为 R 包未安装、minimap2 不可用或输入文件有问题。\n\n"
    "详见「运行日志」；输出目录里的 run_manifest.json 记录了失败原因。"
)


def resource_base() -> Path:
    """Directory to resolve repository-relative paths against.

    When frozen by PyInstaller, ``__file__`` points inside the bundle, so
    ``sys.executable`` is used instead: the .exe sits in
    ``02_code/PythonGUI/dist/``. ``find_repo_root`` then walks upwards looking
    for a repository marker, so the exact depth does not matter as long as
    ``start`` is inside the repository.
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def find_repo_root(start: Path) -> Path:
    """Locate the nanoamp working directory.

    Resolution order:

    1. ``NANOAMP_HOME`` environment variable, if set;
    2. ``%LOCALAPPDATA%\\nanoamp\\config.ini``, written by install.exe - this is
       how an installed nanoamp.exe finds the data directory it was installed
       against, since the exe no longer lives inside that directory;
    3. walking upwards from ``start`` looking for a repository marker.

    Returning the wrong directory is recoverable: the window still opens and
    the user can pick any input/output paths by hand. Only the bundled
    minimap2.exe lookup and the default output directory depend on it.
    """
    env = os.environ.get("NANOAMP_HOME")
    if env and Path(env).is_dir():
        return Path(env).resolve()

    local = os.environ.get("LOCALAPPDATA")
    if local:
        ini = Path(local) / "nanoamp" / "config.ini"
        if ini.is_file():
            try:
                for line in ini.read_text(encoding="utf-8").splitlines():
                    if line.strip().startswith("home"):
                        _, _, value = line.partition("=")
                        candidate = Path(value.strip().strip('"'))
                        if candidate.is_dir():
                            return candidate.resolve()
            except OSError:
                pass

    p = start.resolve()
    for _ in range(8):
        if (p / "03_dependence").is_dir() or (p / "02_code").is_dir():
            return p
        if p.parent == p:
            break
        p = p.parent
    return start.resolve()


def latest_outdir(repo_root: Path) -> Path:
    """Pick a sensible default output directory.

    A researcher using the installed GUI does not want results buried inside
    C:\\Users\\...\\AppData, so they go to ``Documents\\nanoamp 结果``. The
    repository layout (a checkout, where tmp/test_results/ exists) is kept working
    for development.
    """
    if (repo_root / "tmp/test_results").is_dir():
        candidate = repo_root / "tmp/test_results" / "gui"
    else:
        docs = Path(os.environ.get("USERPROFILE", str(Path.home()))) / "Documents"
        candidate = docs / "nanoamp 结果"
    try:
        candidate.mkdir(parents=True, exist_ok=True)
        return candidate
    except OSError:
        return repo_root


class NanoampApp(ttk.Frame):
    """The whole window."""

    def __init__(self, master: tk.Tk, repo_root: Path):
        super().__init__(master, padding=10)
        self.repo_root = repo_root
        self.grid(row=0, column=0, sticky="nsew")
        master.columnconfigure(0, weight=1)
        master.rowconfigure(0, weight=1)

        self.runner: NanoampRunner | None = None
        self.worker: threading.Thread | None = None
        # True once the user asked to stop, so the "finished" handler can say
        # "cancelled" instead of implying the analysis failed.
        self._cancel_requested = False
        self.log_queue: queue.Queue[str | None] = queue.Queue()
        self.last_outdir: Path | None = None
        self.fasta_cache: dict[str, str] = {}

        # form state
        self.var_reads = tk.StringVar()
        self.var_reference = tk.StringVar()
        self.var_outdir = tk.StringVar(value=str(latest_outdir(repo_root)))
        self.var_mode = tk.StringVar(value="A")
        self.var_topn = tk.IntVar(value=20)
        self.var_status = tk.StringVar(value="就绪。")

        # functional annotation state (see _build_annotation_group)
        self.var_annot_on = tk.BooleanVar(value=False)
        self.var_annot_source = tk.StringVar(value=ANNOTATION_SOURCES[0])
        self.var_annot_custom = tk.StringVar()
        self.var_cds_start = tk.StringVar(value="1")
        self.var_cds_end = tk.StringVar(value="")
        self.var_cds_strand = tk.StringVar(value="+")
        self.var_cds_frame = tk.StringVar(value="0")
        self.var_annot_proteins = tk.BooleanVar(value=False)
        self.var_annot_detail = tk.BooleanVar(value=True)
        self.var_annot_hint = tk.StringVar(value="")
        self.var_annot_transcript = tk.StringVar(value=TRANSCRIPT_AUTO)
        # Transcript rows fetched by 「列出转录本」, kept so the picker survives a
        # re-render and so tests can assert on the parsed table.
        self.transcript_choices: list[str] = []

        self._build_layout()
        self._detect_environment()
        self.after(100, self._drain_log_queue)

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(3, weight=1)

        # -- title
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="本程序为 nanoamp R 包的图形界面。",
            foreground="#555555",
        ).pack(anchor="w")

        # -- inputs
        form = ttk.LabelFrame(self, text="输入", padding=8)
        form.grid(row=1, column=0, sticky="ew")
        form.columnconfigure(1, weight=1)

        def row(r: int, label: str, var: tk.StringVar, picker) -> ttk.Entry:
            ttk.Label(form, text=label).grid(row=r, column=0, sticky="w", padx=(0, 6), pady=3)
            entry = ttk.Entry(form, textvariable=var)
            entry.grid(row=r, column=1, sticky="ew", pady=3)
            ttk.Button(form, text="浏览…", command=picker).grid(row=r, column=2, padx=(6, 0))
            return entry

        self.entry_reads = row(0, "测序文件 (FASTQ)", self.var_reads, self._pick_reads)
        self.entry_ref = row(1, "目的序列 (FASTA)", self.var_reference, self._pick_reference)
        row(2, "输出目录", self.var_outdir, self._pick_outdir)

        opts = ttk.Frame(form)
        opts.grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))
        ttk.Label(opts, text="模式").pack(side="left")
        mode_box = ttk.Combobox(
            opts, state="readonly", width=22,
            values=[label for label, _ in MODES],
        )
        mode_box.current(0)
        mode_box.pack(side="left", padx=(6, 16))
        mode_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: self.var_mode.set(
                dict(MODES)[mode_box.get()]
            ),
        )
        ttk.Label(opts, text="显示前 n 条").pack(side="left")
        ttk.Spinbox(opts, from_=1, to=1000, width=6, textvariable=self.var_topn).pack(
            side="left", padx=(6, 0)
        )
        # The switch that turns functional annotation on. It lives here (not in
        # the annotation panel) because the panel itself is hidden while
        # annotation is off - without this the panel could never be reached.
        ttk.Checkbutton(opts, text="功能注释…",
                        variable=self.var_annot_on).pack(side="left", padx=(16, 0))

        # -- functional annotation (optional, off by default)
        self._build_annotation_group()

        # -- results
        nb = ttk.Notebook(self)
        nb.grid(row=3, column=0, sticky="nsew", pady=8)
        self.notebook = nb
        self._build_haplotype_tab(nb)
        self._build_annotation_tab(nb)
        self._build_variant_annotation_tab(nb)
        self._build_qc_tab(nb)
        self._build_files_tab(nb)
        self._build_log_tab(nb)

        # -- actions
        actions = ttk.Frame(self)
        actions.grid(row=4, column=0, sticky="ew")
        actions.columnconfigure(5, weight=1)

        self.btn_run = ttk.Button(actions, text="开始分析", command=self._on_run)
        self.btn_run.grid(row=0, column=0)
        self.btn_doctor = ttk.Button(actions, text="环境自检", command=self._on_doctor)
        self.btn_doctor.grid(row=0, column=1, padx=(6, 0))
        # Copying the log is how a user reports a problem: the window is the only
        # place R's output is shown, so there must be a way to get it out.
        self.btn_copy_diag = ttk.Button(actions, text="复制诊断信息",
                                        command=self._on_copy_diagnostics)
        self.btn_copy_diag.grid(row=0, column=2, padx=(6, 0))
        # Enabled only while R is running; stops the analysis.
        self.btn_cancel = ttk.Button(actions, text="取消操作", command=self._on_cancel,
                                     state="disabled")
        self.btn_cancel.grid(row=0, column=2, padx=(6, 0), sticky="w")
        self.btn_open = ttk.Button(
            actions, text="打开输出目录", command=self._on_open_outdir, state="disabled"
        )
        self.btn_open.grid(row=0, column=3, padx=(6, 0))

        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=140)
        self.progress.grid(row=0, column=4, padx=(12, 0))

        status = ttk.Label(self, textvariable=self.var_status, anchor="w", foreground="#333333")
        status.grid(row=5, column=0, sticky="ew", pady=(6, 0))
        self.status_label = status

    # ------------------------------------------------- functional annotation
    def _build_annotation_group(self) -> None:
        """Optional annotation group: config source, CDS coordinates, outputs.

        The offline (cds) route is first because it needs no network: the user
        gives the CDS interval on the amplicon reference and the program only
        translates. The online (genome) route locates the amplicon in GRCh38
        and fetches the transcript structure from Ensembl.
        """
        box = ttk.Frame(self, padding=(10, 4, 10, 0))
        box.grid(row=2, column=0, sticky="ew")
        box.columnconfigure(1, weight=1)
        self._annotation_box = box
        ttk.Label(box, text="功能注释", foreground="#333333").grid(
            row=0, column=0, sticky="w")

        self.lbl_annot_source = ttk.Label(box, text="配置来源")
        self.lbl_annot_source.grid(row=1, column=0, sticky="w", pady=(2, 0))
        src = ttk.Combobox(box, state="readonly", width=32,
                           values=ANNOTATION_SOURCES, textvariable=self.var_annot_source)
        src.grid(row=1, column=1, sticky="w", padx=(6, 0), pady=(2, 0))
        src.bind("<<ComboboxSelected>>", lambda _e: self._sync_annotation_state())
        self.btn_annot_browse = ttk.Button(box, text="浏览…",
                                           command=self._pick_annotation_config)
        self.btn_annot_browse.grid(row=1, column=2, padx=(6, 0), pady=(2, 0))

        cds = ttk.Frame(box)
        cds.grid(row=2, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._annot_cds_row = cds
        ttk.Label(cds, text="CDS 起").pack(side="left")
        self.entry_cds_start = ttk.Entry(cds, width=7, textvariable=self.var_cds_start)
        self.entry_cds_start.pack(side="left", padx=(4, 10))
        ttk.Label(cds, text="止").pack(side="left")
        self.entry_cds_end = ttk.Entry(cds, width=7, textvariable=self.var_cds_end)
        self.entry_cds_end.pack(side="left", padx=(4, 10))
        ttk.Label(cds, text="链").pack(side="left")
        self.box_cds_strand = ttk.Combobox(cds, state="readonly", width=3, values=["+", "-"],
                                           textvariable=self.var_cds_strand)
        self.box_cds_strand.pack(side="left", padx=(4, 10))
        ttk.Label(cds, text="读码框").pack(side="left")
        self.box_cds_frame = ttk.Combobox(cds, state="readonly", width=3,
                                          values=["0", "1", "2"],
                                          textvariable=self.var_cds_frame)
        self.box_cds_frame.pack(side="left", padx=(4, 0))

        self.chk_annot_detail = ttk.Checkbutton(
            box, text="输出变异级明细（variants_annotation.tsv）",
            variable=self.var_annot_detail)
        self.chk_annot_detail.grid(row=3, column=0, columnspan=2, sticky="w", pady=(4, 0))
        self.chk_annot_proteins = ttk.Checkbutton(
            box, text="输出蛋白序列", variable=self.var_annot_proteins)
        self.chk_annot_proteins.grid(row=3, column=2, sticky="w", pady=(4, 0))

        # Transcript picker. The list is empty until 「列出转录本」 asks Ensembl
        # which transcripts overlap the amplicon, so the only entry at first is
        # "let nanoamp choose" - which is what the offline route always does.
        pick = ttk.Frame(box)
        pick.grid(row=4, column=0, columnspan=3, sticky="w", pady=(4, 0))
        self._annot_pick_row = pick
        ttk.Label(pick, text="转录本").pack(side="left")
        self.box_annot_transcript = ttk.Combobox(
            pick, state="readonly", width=34, values=[TRANSCRIPT_AUTO],
            textvariable=self.var_annot_transcript)
        self.box_annot_transcript.pack(side="left", padx=(6, 8))
        self.btn_list_transcripts = ttk.Button(
            pick, text="列出转录本", command=self._on_list_transcripts)
        self.btn_list_transcripts.pack(side="left")
        ttk.Label(pick, text="（在线路线：先列出再挑一个）",
                  foreground="#555555").pack(side="left", padx=(8, 0))

        self.lbl_annot_hint = ttk.Label(box, textvariable=self.var_annot_hint,
                                        foreground="#7a5c00",
                                        wraplength=WINDOW_WIDTH - 90, justify="left")
        self.lbl_annot_hint.grid(row=5, column=0, columnspan=3, sticky="w", pady=(4, 0))
        # The whole panel is hidden while annotation is off: the default window
        # is 720 px tall and must keep the results area and buttons in view.
        self._annot_hidden = [box]

        for var in (self.var_cds_start, self.var_cds_end, self.var_cds_strand,
                    self.var_cds_frame, self.var_annot_source, self.var_annot_on):
            var.trace_add("write", lambda *_: self._sync_annotation_state())
        self._sync_annotation_state()

    def _annotation_widgets(self) -> list:
        return [self.entry_cds_start, self.entry_cds_end, self.box_cds_strand,
                self.box_cds_frame, self.btn_annot_browse,
                self.box_annot_transcript, self.btn_list_transcripts]

    def _sync_annotation_state(self) -> None:
        """Show/hide the optional rows, enable/disable, keep the hint in sync."""
        on = bool(self.var_annot_on.get())
        source = self.var_annot_source.get()
        offline = source == ANNOTATION_OFFLINE

        for widget in self._annot_hidden:
            if on:
                widget.grid()
            else:
                widget.grid_remove()

        cds_widgets = (self.entry_cds_start, self.entry_cds_end,
                       self.box_cds_strand, self.box_cds_frame)
        # The transcript picker only means something on the online route: the
        # offline route annotates the CDS span the user typed, where there is no
        # transcript list to choose from.
        picker_widgets = (self.box_annot_transcript, self.btn_list_transcripts)
        for w in self._annotation_widgets():
            if not on:
                state = "disabled"
            elif w in cds_widgets and not offline:
                state = "disabled"
            elif w in picker_widgets and offline:
                state = "disabled"
            else:
                state = "normal"
            if isinstance(w, ttk.Combobox):
                state = "readonly" if state == "normal" else "disabled"
            w.configure(state=state)
        if offline and self.var_annot_transcript.get() != TRANSCRIPT_AUTO:
            # A transcript id left over from the online route must not be passed
            # with a cds config, where it would be meaningless.
            self.var_annot_transcript.set(TRANSCRIPT_AUTO)

        if not on:
            self.var_annot_hint.set("")
            return
        if offline:
            problem = self._cds_problem()
            if problem:
                self.var_annot_hint.set(f"离线 CDS 路线：{problem}")
            else:
                start = self._int_or_none(self.var_cds_start.get())
                end = self._int_or_none(self.var_cds_end.get())
                length = (end - start + 1) if (start and end) else None
                self.var_annot_hint.set(
                    f"离线 CDS 路线：不联网。CDS 长度 {length} bp"
                    f"（{length // 3 if length else 0} 个密码子）。"
                    "坐标以目的序列（扩增子参考）为准，1-based。")
        elif source == ANNOTATION_ONLINE:
            self.var_annot_hint.set(
                "在线 genome 路线：需要联网（程序自行在 GRCh38 定位扩增子并从 "
                "Ensembl 取转录本结构）。扩增子不在内置 panel 时会退化为逐染色体扫描，"
                "可能非常慢；建议先用「列出转录本」确认，或改用离线 CDS 配置。")
        else:
            path = self.var_annot_custom.get().strip()
            self.var_annot_hint.set(
                f"自定义配置：{path}" if path else "自定义配置：请先选择一个 JSON 文件。")
        self._grow_to_fit()
        # The wrapped hint can change the required height a moment later, so a
        # second pass is scheduled for when the event loop goes idle.
        try:
            self.after_idle(self._grow_to_fit)
        except tk.TclError:
            pass

    def _grow_to_fit(self) -> None:
        """Grow the window instead of squeezing the result tables.

        Enabling the annotation panel adds rows; at the default 720 px the
        notebook would be left only a few dozen pixels tall. The window is only
        ever grown, never shrunk, and never beyond the screen. The frame's own
        requested height is used (rather than the toplevel's) so the value is
        correct in the same event-loop turn as the layout change.
        """
        try:
            root = self.winfo_toplevel()
            self.update_idletasks()
            root.update_idletasks()
            # Frame and toplevel can disagree while the layout settles; take the
            # larger of the two so the tables are never squeezed.
            need = max(self.winfo_reqheight(), root.winfo_reqheight()) + 10
            if root.winfo_height() >= need:
                return
            screen_h = root.winfo_screenheight() - 80
            width = max(root.winfo_width(), WINDOW_WIDTH)
            root.geometry(f"{width}x{min(need, screen_h)}")
            root.update_idletasks()
        except tk.TclError:
            pass

    @staticmethod
    def _int_or_none(text: str) -> int | None:
        try:
            return int(str(text).strip())
        except (TypeError, ValueError):
            return None

    def _cds_problem(self) -> str:
        """Return a human-readable problem with the CDS form, or ""."""
        start = self._int_or_none(self.var_cds_start.get())
        end = self._int_or_none(self.var_cds_end.get())
        if start is None or start < 1:
            return "起始坐标无效（应为 ≥1 的整数）。"
        if end is None or end < start:
            return "终止坐标无效（应 ≥ 起始坐标）。"
        length = end - start + 1
        if length % 3 != 0:
            return (f"CDS 长度 {length} bp 不是 3 的倍数，注释会被跳过"
                    f"（应删掉 {length % 3} bp 或调整读码框）。")
        return ""

    def _bundled_config(self, name: str) -> Path | None:
        """Locate a bundled example config in a checkout or an installed tree."""
        candidates = [
            self.repo_root / "02_code" / "r" / "inst" / "configs" / name,
            Path(self.repo_root) / "inst" / "configs" / name,
        ]
        try:
            from .r_runner import _configured_paths  # type: ignore
            cfg = _configured_paths()
            rlib = cfg.get("rlib")
            if rlib:
                # Where the package keeps its own copy...
                candidates.insert(0, Path(rlib) / "nanoamp" / "configs" / name)
            home = cfg.get("home")
            if home:
                # ...and the copy install.exe puts where a user can find it.
                candidates.insert(0, Path(home) / "configs" / name)
        except Exception:  # noqa: BLE001 - discovery is best effort
            pass
        env_home = os.environ.get("NANOAMP_HOME")
        if env_home:
            candidates.insert(0, Path(env_home) / "configs" / name)
        for cand in candidates:
            if cand.is_file():
                return cand
        return None

    def _pick_annotation_config(self) -> None:
        path = filedialog.askopenfilename(
            title="选择功能注释配置 JSON",
            filetypes=[("JSON", "*.json"), ("所有文件", "*.*")],
        )
        if path:
            self.var_annot_custom.set(path)
            self.var_annot_source.set(ANNOTATION_CUSTOM)
            self._sync_annotation_state()

    def _annotation_config_path(self) -> tuple[Path | None, str]:
        """Resolve the config to pass to the CLI; returns (path, error)."""
        if not self.var_annot_on.get():
            return None, ""
        source = self.var_annot_source.get()
        if source == ANNOTATION_OFFLINE:
            problem = self._cds_problem()
            if problem:
                return None, problem
            start = self._int_or_none(self.var_cds_start.get())
            end = self._int_or_none(self.var_cds_end.get())
            cfg = {
                "name": "gui_offline_cds",
                "route": "cds",
                "cds": {"start": start, "end": end,
                        "strand": self.var_cds_strand.get(),
                        "frame": int(self.var_cds_frame.get()),
                        "boundaries": "inclusive"},
                "genetic_code": "Standard",
                "notes": "written by nanoamp GUI",
            }
            tmp = Path(tempfile.gettempdir()) / f"nanoamp_gui_cds_{os.getpid()}.json"
            tmp.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")
            return tmp, ""
        if source == ANNOTATION_ONLINE:
            bundled = self._bundled_config("example_online.json")
            if bundled is None:
                return None, ("找不到随包的在线示例配置 example_online.json。\n"
                              "请改用「自定义 JSON…」指定一个 route=genome 的配置。")
            return bundled, ""
        path = Path(self.var_annot_custom.get().strip())
        if not path.is_file():
            return None, f"自定义配置不存在：{path}"
        return path, ""

    def _build_haplotype_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="单倍型结果")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)

        cols = ("rank", "haplotype_id", "count", "proportion", "is_reference",
                "n_snv", "n_ins", "n_del", "length", "variants")
        heads = {
            "rank": "排名", "haplotype_id": "编号", "count": "reads 数",
            "proportion": "占比", "is_reference": "是否与目的序列一致",
            "n_snv": "SNV", "n_ins": "插入", "n_del": "缺失",
            "length": "长度", "variants": "变异",
        }
        widths = {"rank": 50, "haplotype_id": 70, "count": 70, "proportion": 80,
                  "is_reference": 130, "n_snv": 50, "n_ins": 50, "n_del": 50,
                  "length": 60, "variants": 260}

        self.tree = ttk.Treeview(frame, columns=cols, show="headings", height=12)
        for c in cols:
            self.tree.heading(c, text=heads[c])
            self.tree.column(c, width=widths[c], anchor="w" if c == "variants" else "center")
        self.tree.grid(row=0, column=0, sticky="nsew")

        yscroll = ttk.Scrollbar(frame, orient="vertical", command=self.tree.yview)
        yscroll.grid(row=0, column=1, sticky="ns")
        self.tree.configure(yscrollcommand=yscroll.set)

        self.seq_box = tk.Text(frame, height=5, wrap="char", font=("Consolas", 9))
        self.seq_box.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.seq_box.configure(state="disabled")
        ttk.Label(frame, text="选中一行可查看对应单倍型序列。",
                  foreground="#777777").grid(row=2, column=0, sticky="w")
        self.tree.bind("<<TreeviewSelect>>", self._on_select_haplotype)

    def _build_qc_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="QC 指标")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.qc_text = tk.Text(frame, wrap="none", font=("Consolas", 10))
        self.qc_text.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.qc_text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.qc_text.configure(yscrollcommand=sb.set, state="disabled")

    def _build_files_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="输出文件")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.files_tree = ttk.Treeview(frame, columns=("name", "size"), show="headings")
        self.files_tree.heading("name", text="文件")
        self.files_tree.heading("size", text="大小 (字节)")
        self.files_tree.column("name", width=380)
        self.files_tree.column("size", width=110, anchor="e")
        self.files_tree.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.files_tree.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.files_tree.configure(yscrollcommand=sb.set)
        self.files_tree.bind("<Double-1>", self._on_open_file)

    def _build_log_tab(self, nb: ttk.Notebook) -> None:
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="运行日志")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        self.log_text = tk.Text(frame, wrap="none", font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.log_text.yview)
        sb.grid(row=0, column=1, sticky="ns")
        self.log_text.configure(yscrollcommand=sb.set, state="disabled")

    def _build_annotation_tab(self, nb: ttk.Notebook) -> None:
        """Per-haplotype x per-transcript consequences (annotation.tsv)."""
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="注释结果")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self.annot_status = tk.StringVar(value="未运行功能注释。")
        ttk.Label(frame, textvariable=self.annot_status, foreground="#7a5c00",
                  wraplength=WINDOW_WIDTH - 90, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w")

        cols = ("haplotype_id", "transcript_id", "consequence_zh",
                "consequence_any_transcript_zh", "transcript_conflict",
                "protein_change", "variants")
        heads = {
            "haplotype_id": "编号", "transcript_id": "转录本",
            "consequence_zh": "后果", "consequence_any_transcript_zh": "最严重后果",
            "transcript_conflict": "转录本冲突", "protein_change": "蛋白变化",
            "variants": "变异",
        }
        widths = {"haplotype_id": 65, "transcript_id": 145, "consequence_zh": 85,
                  "consequence_any_transcript_zh": 95, "transcript_conflict": 85,
                  "protein_change": 120, "variants": 185}
        self.annot_tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.annot_tree.heading(c, text=heads[c])
            self.annot_tree.column(c, width=widths[c],
                                   anchor="w" if c in ("variants", "transcript_id") else "center")
        self.annot_tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.annot_tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.annot_tree.configure(yscrollcommand=sb.set)
        # Selecting a haplotype here highlights the same row in the other tabs.
        self.annot_tree.bind("<<TreeviewSelect>>", self._on_select_annotation)

    def _build_variant_annotation_tab(self, nb: ttk.Notebook) -> None:
        """Per-variant consequences (variants_annotation.tsv)."""
        frame = ttk.Frame(nb, padding=4)
        nb.add(frame, text="变异注释")
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(1, weight=1)

        self.var_annot_status = tk.StringVar(
            value="需要勾选「输出变异级明细」并在分析完成后查看。")
        ttk.Label(frame, textvariable=self.var_annot_status, foreground="#666666",
                  wraplength=WINDOW_WIDTH - 90, justify="left").grid(
            row=0, column=0, columnspan=2, sticky="w")

        cols = ("haplotype_id", "type", "genome_pos", "cds_pos", "ref", "alt",
                "codon_ref", "codon_alt", "aa_ref", "aa_alt", "consequence_zh")
        heads = {
            "haplotype_id": "编号", "type": "类型", "genome_pos": "参考坐标",
            "cds_pos": "CDS 坐标", "ref": "参考碱基", "alt": "变异碱基",
            "codon_ref": "原密码子", "codon_alt": "新密码子",
            "aa_ref": "原氨基酸", "aa_alt": "新氨基酸", "consequence_zh": "后果",
        }
        self.var_annot_tree = ttk.Treeview(frame, columns=cols, show="headings", height=8)
        for c in cols:
            self.var_annot_tree.heading(c, text=heads[c])
            self.var_annot_tree.column(c, width=82, anchor="center")
        self.var_annot_tree.grid(row=1, column=0, sticky="nsew")
        sb = ttk.Scrollbar(frame, orient="vertical", command=self.var_annot_tree.yview)
        sb.grid(row=1, column=1, sticky="ns")
        self.var_annot_tree.configure(yscrollcommand=sb.set)

    # -------------------------------------------------------- environment
    def _detect_environment(self) -> None:
        try:
            self.runner = NanoampRunner(self.repo_root)
        except RNotFoundError as exc:
            self.runner = None
            self.var_status.set("未找到 R。请运行环境自检。")
            self._append_log(str(exc))
            return
        self._append_log(f"仓库根目录 : {self.repo_root}")
        self._append_log(f"Rscript    : {self.runner.rscript}")
        self._append_log("初始化完成。")

    # ------------------------------------------------------------ actions
    def _pick_reads(self) -> None:
        path = filedialog.askopenfilename(
            title="选择测序 FASTQ",
            filetypes=[("FASTQ", "*.fastq *.fq *.fastq.gz *.fq.gz"), ("所有文件", "*.*")],
        )
        if path:
            self.var_reads.set(path)
            if not self.var_reference.get():
                self._suggest_reference(Path(path))

    def _pick_reference(self) -> None:
        path = filedialog.askopenfilename(
            title="选择目的序列 FASTA",
            filetypes=[("FASTA", "*.fa *.fasta *.fna *.fas"), ("所有文件", "*.*")],
        )
        if path:
            self.var_reference.set(path)

    def _pick_outdir(self) -> None:
        path = filedialog.askdirectory(title="选择输出目录")
        if path:
            self.var_outdir.set(path)

    def _suggest_reference(self, reads: Path) -> None:
        """If the reads sit in a sample directory, offer its reference file."""
        for name in ("reference.self.fa", "reference.fa", "reference.wt.fa"):
            cand = reads.parent / name
            if cand.is_file():
                self.var_reference.set(str(cand))
                return

    def _on_run(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        reads = self.var_reads.get().strip()
        reference = self.var_reference.get().strip()
        outdir = self.var_outdir.get().strip()
        if not reads or not reference or not outdir:
            messagebox.showwarning("输入不完整", "请指定测序文件、目的序列与输出目录。")
            return
        for label, path in (("测序文件", reads), ("目的序列", reference)):
            if not Path(path).is_file():
                messagebox.showerror("文件不存在", f"{label} 不存在：\n{path}")
                return

        if self.runner is None:
            messagebox.showerror("R 不可用", "未找到 Rscript。请先运行环境自检。")
            return

        annot_cfg, annot_problem = self._annotation_config_path()
        if annot_problem:
            messagebox.showwarning("注释配置不完整", annot_problem)
            return
        mode = self.var_mode.get()
        if annot_cfg is not None and mode == "C":
            messagebox.showinfo(
                "模式 C 不执行注释",
                "模式 C 只做原始精确匹配统计，不运行功能注释。\n"
                "注释参数已被忽略；如需注释请改用模式 A 或 B。",
            )
            annot_cfg = None

        argv = [
            "call",
            "--reads", reads,
            "--reference", reference,
            "--outdir", outdir,
            "--mode", mode,
            "--top-n", str(self.var_topn.get()),
        ]
        if annot_cfg is not None:
            argv += ["--annotate-config", str(annot_cfg)]
            transcript = self._selected_transcript_id()
            if transcript:
                argv += ["--transcript", transcript]
            if self.var_annot_detail.get():
                argv.append("--annotation-detail")
            if self.var_annot_proteins.get():
                argv.append("--annotation-proteins")
        self._clear_results()
        self._cancel_requested = False
        self._set_running(True)
        self._append_log("")
        self._append_log("$ nanoamp " + " ".join(argv))

        self.worker = threading.Thread(
            target=self._run_worker, args=(argv, Path(outdir)), daemon=True
        )
        self.worker.start()

    def _on_doctor(self) -> None:
        if self.worker and self.worker.is_alive():
            return
        try:
            runner = NanoampRunner(self.repo_root)
        except RNotFoundError as exc:
            messagebox.showerror("R 不可用", str(exc))
            return
        self.runner = runner
        self._cancel_requested = False
        self._set_running(True)
        self._append_log("")
        self._append_log("$ nanoamp doctor")
        self.worker = threading.Thread(
            target=self._doctor_worker, args=(runner,), daemon=True
        )
        self.worker.start()

    def _selected_transcript_id(self) -> str:
        """The transcript id to pass as --transcript, or "" for automatic."""
        value = self.var_annot_transcript.get().strip()
        if not value or value == TRANSCRIPT_AUTO:
            return ""
        return value.split()[0]

    def _on_list_transcripts(self) -> None:
        """Ask Ensembl which transcripts overlap the amplicon.

        Uses the same CLI entry point as everything else (mode A analysis plus
        `--list-transcripts`), so the GUI cannot disagree with the command line.
        The rows come back as transcripts.tsv, which is what makes the picker a
        real picker instead of a hint to go read the log.
        """
        if self.worker and self.worker.is_alive():
            return
        reads = self.var_reads.get().strip()
        reference = self.var_reference.get().strip()
        for label, path in (("测序文件", reads), ("目的序列", reference)):
            if not path or not Path(path).is_file():
                messagebox.showwarning("输入不完整", f"请先选择{label}（列出转录本需要扩增子序列）。")
                return
        annot_cfg, problem = self._annotation_config_path()
        if problem:
            messagebox.showwarning("注释配置不完整", problem)
            return
        if annot_cfg is None:
            messagebox.showinfo("需要注释配置",
                                "请先勾选「功能注释…」并选择配置来源（在线 genome 或自定义）。")
            return
        if self.runner is None:
            try:
                self.runner = NanoampRunner(self.repo_root)
            except RNotFoundError as exc:
                messagebox.showerror("R 不可用", str(exc))
                return
        outdir = Path(tempfile.gettempdir()) / f"nanoamp_gui_transcripts_{os.getpid()}"
        argv = [
            "call", "--reads", reads, "--reference", reference,
            "--outdir", str(outdir), "--mode", "A",
            "--annotate-config", str(annot_cfg), "--list-transcripts",
        ]
        self._cancel_requested = False
        self._set_running(True)
        self._append_log("")
        self._append_log("$ nanoamp " + " ".join(argv))
        self.worker = threading.Thread(
            target=self._list_transcripts_worker, args=(argv, outdir), daemon=True
        )
        self.worker.start()

    def _list_transcripts_worker(self, argv: list[str], outdir: Path) -> None:
        assert self.runner is not None
        try:
            code, _ = self.runner.run(argv, stream=self._emit)
        except Exception:
            self._emit(traceback.format_exc())
            code = 1
        self.log_queue.put(("__transcripts_done__", code, outdir))

    def _finish_transcripts(self, code: int, outdir: Path) -> None:
        self._set_running(False)
        if code != 0:
            self.var_status.set("列出转录本失败。详见运行日志。")
            return
        rows = self._load_transcript_rows(outdir)
        if not rows:
            self.var_status.set("没有找到与该扩增子重叠的转录本（见运行日志）。")
            return
        self.transcript_choices = [r["transcript_id"] for r in rows
                                   if r.get("transcript_id")]
        values = [TRANSCRIPT_AUTO] + self.transcript_choices
        self.box_annot_transcript.configure(values=values)
        self.var_annot_transcript.set(TRANSCRIPT_AUTO)
        mane = [r for r in rows if NanoampApp._cell(r, "mane").upper() == "MANE"]
        for row in rows:
            self._append_log("[GUI] {} {} {} {} {}".format(
                row.get("transcript_id", ""), row.get("name", ""),
                row.get("biotype", ""), row.get("mane", ""),
                row.get("canonical", "")))
        self.var_status.set(
            f"找到 {len(rows)} 个重叠转录本"
            + (f"，其中 {len(mane)} 个 MANE Select" if mane else "")
            + "。默认自动选择；也可在上方「转录本」里指定一个。"
        )

    @staticmethod
    def _load_transcript_rows(outdir: Path) -> list[dict[str, str]]:
        path = Path(outdir) / "transcripts.tsv"
        if not path.is_file():
            return []
        _fields, rows, error = NanoampApp._read_tsv_safe(path)
        return [] if error else rows

    def _on_open_outdir(self) -> None:
        if not self.last_outdir or not self.last_outdir.is_dir():
            return
        self._open_path(self.last_outdir)

    def _on_copy_diagnostics(self) -> None:
        """Put the log (which includes doctor output) on the clipboard."""
        text = self.log_text.get("1.0", "end").strip()
        if not text:
            messagebox.showinfo(
                "没有可复制的信息",
                "运行日志还是空的。先点「环境自检」，或在失败后重试一次分析。",
            )
            return
        header = [
            f"nanoamp GUI：{APP_TITLE}",
            f"仓库根目录: {self.repo_root}",
            f"Rscript: {self.runner.rscript if self.runner else '(未检测)'}",
            "--- 运行日志 ---",
        ]
        try:
            self.clipboard_clear()
            self.clipboard_append("\n".join(header) + "\n" + text)
            self.update_idletasks()
        except tk.TclError as exc:
            messagebox.showerror("复制失败", str(exc))
            return
        self.var_status.set("诊断信息已复制到剪贴板。")

    def _on_open_file(self, _event) -> None:
        sel = self.files_tree.selection()
        if not sel or not self.last_outdir:
            return
        target = self.last_outdir / sel[0]
        if target.is_file():
            self._open_path(target)

    @staticmethod
    def _open_path(path: Path) -> None:
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]
        except AttributeError:
            webbrowser.open(path.as_uri())
        except OSError as exc:
            messagebox.showerror("打开失败", f"{path}\n\n{exc}")

    # -------------------------------------------------------- worker side
    def _run_worker(self, argv: list[str], outdir: Path) -> None:
        assert self.runner is not None
        try:
            code, _ = self.runner.run(argv, stream=self._emit)
            self.log_queue.put(("__done__", code, outdir))
        except Exception:
            self._emit(traceback.format_exc())
            self.log_queue.put(("__done__", 1, outdir))

    def _doctor_worker(self, runner: NanoampRunner) -> None:
        try:
            code, _ = runner.run(["doctor"], stream=self._emit)
            self.log_queue.put(("__doctor_done__", code, None))
        except Exception:
            self._emit(traceback.format_exc())
            self.log_queue.put(("__doctor_done__", 1, None))

    def _emit(self, line: str) -> None:
        self.log_queue.put(line)

    def _drain_log_queue(self) -> None:
        try:
            while True:
                item = self.log_queue.get_nowait()
                if isinstance(item, tuple):
                    kind, code, outdir = item
                    if kind == "__done__":
                        self._finish_run(code, outdir)
                    elif kind == "__transcripts_done__":
                        self._finish_transcripts(code, outdir)
                    else:
                        self._finish_doctor(code)
                else:
                    self._append_log(item)
        except queue.Empty:
            pass
        self.after(100, self._drain_log_queue)

    # -------------------------------------------------------------- state
    def _set_running(self, running: bool) -> None:
        state = "disabled" if running else "normal"
        self.btn_run.configure(state=state)
        self.btn_doctor.configure(state=state)
        # Cancel is the mirror image: available exactly while R is running.
        self.btn_cancel.configure(state="normal" if running else "disabled")
        if running:
            self.progress.start(12)
            self.var_status.set("正在分析…（首次运行需加载 R 包，耗时较长）")
        else:
            self.progress.stop()

    def _on_cancel(self) -> None:
        """Stop the running analysis or environment check.

        Nothing is deleted: partial output stays in the output directory, so
        the user can look at what was produced before stopping.
        """
        if self.worker is None or not self.worker.is_alive():
            self.btn_cancel.configure(state="disabled")
            return
        self.btn_cancel.configure(state="disabled")
        self.var_status.set("正在取消…")
        self._append_log("")
        self._append_log("用户请求取消，正在终止 R 进程…")
        self._cancel_requested = True
        # self.runner is set for both paths: _on_run stores the analysis
        # runner and _on_doctor stores the one it created, so either kind of
        # run can actually be stopped.
        if self.runner is not None:
            self.runner.cancel()

    def _finish_doctor(self, code: int) -> None:
        self._set_running(False)
        if self._cancel_requested:
            self._cancel_requested = False
            self.var_status.set("环境自检已取消。")
            return
        self.var_status.set("环境自检完成。" if code == 0 else f"环境自检失败（退出码 {code}）。")

    def _finish_run(self, code: int, outdir: Path) -> None:
        self._set_running(False)
        self.last_outdir = outdir
        if self._cancel_requested:
            # A cancelled run is not a failure: say what happened and where the
            # partial output is, instead of the generic error dialog. The
            # manifest is marked so that the directory does not look like a
            # completed run later on.
            self._cancel_requested = False
            self._mark_cancelled(outdir)
            self.var_status.set(f"分析已取消。部分结果保留在：{outdir}")
            if outdir.is_dir():
                self.btn_open.configure(state="normal")
            messagebox.showinfo(
                "已取消",
                "分析已取消。\n\n"
                f"已产生的部分结果保留在：\n{outdir}",
            )
            return
        if code != 0:
            self._report_failure(code, outdir)
            return
        self.btn_open.configure(state="normal")
        self._load_results(outdir)
        n = len(self.tree.get_children())
        self.var_status.set(f"分析完成，输出目录：{outdir}（{n} 条单倍型）")

    # ------------------------------------------------------------ results
    def _clear_results(self) -> None:
        for item in self.tree.get_children():
            self.tree.delete(item)
        for item in self.files_tree.get_children():
            self.files_tree.delete(item)
        for tree in (self.annot_tree, self.var_annot_tree):
            for item in tree.get_children():
                tree.delete(item)
        self.annot_status.set("分析进行中…")
        self.var_annot_status.set("分析进行中…")
        self._set_text(self.qc_text, "")
        self._set_text(self.seq_box, "")
        self.fasta_cache.clear()

    @staticmethod
    def _set_text(widget: tk.Text, value: str) -> None:
        widget.configure(state="normal")
        widget.delete("1.0", "end")
        if value:
            widget.insert("1.0", value)
        widget.configure(state="disabled")

    # --------------------------------------------------- failure reporting
    @staticmethod
    def _read_manifest(outdir: Path) -> dict:
        """run_manifest.json as a dict, or {} when it is missing/unreadable."""
        path = Path(outdir) / "run_manifest.json"
        if not path.is_file():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        return data if isinstance(data, dict) else {}

    @staticmethod
    def _failure_hint(manifest: dict) -> tuple[str, str]:
        """(error_class, hint) for a failed run's manifest."""
        cls = str(manifest.get("error_class") or "").strip()
        return cls, ERROR_CLASS_HINTS.get(cls, ERROR_CLASS_FALLBACK)

    def _report_failure(self, code: int, outdir: Path) -> None:
        """Explain a failed run using its manifest instead of a generic dialog.

        R writes run_manifest.json (status/error_class/error_message) even when
        the analysis dies, so the user gets a class-specific next step - and the
        file stays readable after the window is closed.
        """
        manifest = self._read_manifest(outdir)
        cls, hint = self._failure_hint(manifest)
        message = str(manifest.get("error_message") or "").strip()
        label = {"input": "输入错误", "environment": "环境问题",
                 "network": "网络问题", "internal": "内部错误"}.get(cls)
        if label:
            self.var_status.set(f"分析失败（退出码 {code}，{label}）。详见运行日志。")
        else:
            self.var_status.set(f"分析失败（退出码 {code}）。详见运行日志。")
        if cls:
            self._append_log(f"[GUI] 失败分类：{cls}")
        if message:
            self._append_log("[GUI] " + message.replace("\n", " "))
        self._append_log(f"[GUI] {hint.splitlines()[0]}")
        detail = f"\n\nR 报告的失败原因：\n{message}" if message else ""
        messagebox.showerror(
            "分析失败",
            f"{hint}{detail}\n\n输出目录：{outdir}",
        )

    def _mark_cancelled(self, outdir: Path) -> None:
        """Record a cancelled run in run_manifest.json (best effort).

        R cannot write this itself: cancelling kills the R process, so the
        manifest it wrote (if any) would still say "done" or would be missing.
        The GUI is the only component that knows the run was cancelled, so it
        keeps the directory from looking like a completed analysis.
        """
        if not outdir.is_dir():
            return
        info = self._read_manifest(outdir)
        info["status"] = "cancelled"
        info["cancelled_by"] = "gui"
        info["cancelled_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        try:
            (Path(outdir) / "run_manifest.json").write_text(
                json.dumps(info, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        except OSError as exc:
            self._append_log(f"[GUI] 无法写入取消状态：{exc}")

    @staticmethod
    def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            return list(reader.fieldnames or []), list(reader)

    @staticmethod
    def _read_tsv_safe(path: Path) -> tuple[list[str], list[dict[str, str]], str]:
        """[fields, rows, error]; a file that cannot be read is not fatal.

        A truncated or hand-edited results file must produce a readable message
        in the window, never a traceback (the user cannot fix a crash).
        """
        try:
            fields, rows = NanoampApp._read_tsv(path)
            return fields, rows, ""
        except (OSError, csv.Error, UnicodeError) as exc:
            return [], [], f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _cell(row: dict, key: str) -> str:
        """A TSV cell as text: a short/garbled row yields "" instead of None."""
        value = row.get(key)
        return "" if value is None else str(value)

    def _insert_row(self, tree: tk.ttk.Treeview, iid: str | None, values) -> bool:
        """Insert one table row, tolerating duplicate or invalid row ids."""
        try:
            if iid is None:
                tree.insert("", "end", values=values)
            else:
                tree.insert("", "end", iid=iid, values=values)
            return True
        except tk.TclError:
            # Duplicate iid: fall back to an anonymous row so the data is still
            # shown rather than the whole table being lost.
            try:
                tree.insert("", "end", values=values)
                return True
            except tk.TclError:
                return False

    def _load_results(self, outdir: Path) -> None:
        self._load_haplotypes(outdir / "haplotypes.tsv")
        self._load_annotation(outdir)
        self._load_qc(outdir / "qc.tsv")
        self._load_files(outdir)

    def _load_annotation(self, outdir: Path) -> None:
        """Fill the annotation tabs and the three-state annotation status.

        The status deliberately reports what the run *covered* (how many
        transcripts were annotated or skipped), not how many rows
        annotation.tsv happens to have: a run that annotated one transcript of
        eight must not look like a complete success.
        """
        ann_path = outdir / "annotation.tsv"
        detail_path = outdir / "variants_annotation.tsv"
        for tree in (self.annot_tree, self.var_annot_tree):
            for item in tree.get_children():
                tree.delete(item)

        qc = {}
        qc_path = outdir / "qc.tsv"
        if qc_path.is_file():
            _f, rows, qc_error = self._read_tsv_safe(qc_path)
            qc = {self._cell(r, "metric"): self._cell(r, "value") for r in rows}
            if qc_error:
                self._append_log(f"[GUI] qc.tsv 读取失败：{qc_error}")

        requested = qc.get("annotation_enabled", "").upper() == "TRUE"
        available = qc.get("annotation_available", "").upper() == "TRUE"
        if not requested and not ann_path.is_file():
            self.annot_status.set("未运行功能注释。")
            self.var_annot_status.set("需要勾选「输出变异级明细」并在分析完成后查看。")
            return

        if not available and requested:
            reason = qc.get("annotation_skip_reason", "未说明原因")
            self.annot_status.set(f"注释不可用：{reason}")
            self._append_log(f"[GUI] 注释不可用：{reason}")
            self.var_annot_status.set("注释不可用，因此没有变异级明细。")
            return

        rows = []
        if ann_path.exists():
            if not ann_path.is_file():
                self.annot_status.set(
                    f"annotation.tsv 不是普通文件，无法显示：{ann_path}")
                self._append_log(f"[GUI] {self.annot_status.get()}")
                self.var_annot_status.set("annotation.tsv 无法读取。")
                return
            _f, rows, ann_error = self._read_tsv_safe(ann_path)
            if ann_error or not _f:
                # A malformed result file must not crash the window: say what is
                # wrong and keep the rest of the results usable.
                why = ann_error or "表头为空（文件不是制表符分隔的表）"
                self.annot_status.set(f"annotation.tsv 不符合契约，无法显示：{why}")
                self._append_log(f"[GUI] {self.annot_status.get()}")
                self.var_annot_status.set("annotation.tsv 无法读取。")
                return
            for r in rows:
                conflict = self._cell(r, "transcript_conflict")
                self._insert_row(
                    self.annot_tree,
                    f"{self._cell(r, 'haplotype_id')}|{self._cell(r, 'transcript_id')}",
                    (self._cell(r, "haplotype_id"), self._cell(r, "transcript_id"),
                     self._cell(r, "consequence_zh"),
                     self._cell(r, "consequence_any_transcript_zh"),
                     {"TRUE": "是", "FALSE": "否"}.get(conflict.upper(), conflict),
                     self._cell(r, "protein_change"), self._cell(r, "variants")),
                )
        n_ann = qc.get("n_transcripts_annotated", "")
        n_skip = qc.get("n_transcripts_skipped", "")
        n_hap = qc.get("n_haplotypes_annotated", "")
        source = qc.get("annotation_source", "")
        if n_skip not in ("", "0"):
            reason = qc.get("annotation_skip_reason", "")
            self.annot_status.set(
                f"部分完成：已注释 {n_ann} 个转录本、{n_hap} 个单倍型；"
                f"跳过 {n_skip} 个转录本。" + (f" 原因：{reason}" if reason else ""))
        else:
            self.annot_status.set(
                f"已注释 {n_ann} 个转录本、{n_hap} 个单倍型（来源：{source}）。"
                f"共 {len(rows)} 行后果。")
        self._append_log("[GUI] " + self.annot_status.get())

        if detail_path.is_file():
            _f, drows, det_error = self._read_tsv_safe(detail_path)
            if det_error:
                self.var_annot_status.set(
                    f"variants_annotation.tsv 不符合契约，无法显示：{det_error}")
            else:
                for r in drows:
                    self._insert_row(
                        self.var_annot_tree, None,
                        (self._cell(r, "haplotype_id"), self._cell(r, "type"),
                         self._cell(r, "genome_pos"), self._cell(r, "cds_pos"),
                         self._cell(r, "ref"), self._cell(r, "alt"),
                         self._cell(r, "codon_ref"), self._cell(r, "codon_alt"),
                         self._cell(r, "aa_ref"), self._cell(r, "aa_alt"),
                         self._cell(r, "consequence_zh")),
                    )
                self.var_annot_status.set(f"{len(drows)} 条变异级后果。")
        elif self.var_annot_detail.get():
            self.var_annot_status.set(
                "没有 variants_annotation.tsv：可能是本次没有落入 CDS 的变异，"
                "或注释被跳过（见「注释结果」页）。")
        else:
            self.var_annot_status.set("未请求变异级明细（勾选后重跑即可生成）。")

    def _on_select_annotation(self, _event) -> None:
        """Selecting an annotation row also selects the haplotype elsewhere."""
        sel = self.annot_tree.selection()
        if not sel:
            return
        hid = str(sel[0]).split("|", 1)[0]
        if hid in self.tree.get_children():
            self.tree.selection_set(hid)
            self.tree.see(hid)

    def _load_haplotypes(self, path: Path) -> None:
        if not path.is_file():
            self._append_log(f"[GUI] 未找到 {path.name}")
            return
        _fields, rows, error = self._read_tsv_safe(path)
        if error:
            self.var_status.set(f"{path.name} 不符合契约，无法显示：{error}")
            self._append_log(f"[GUI] {self.var_status.get()}")
            return
        for row in rows:
            prop = self._cell(row, "proportion")
            try:
                prop_txt = f"{float(prop):.2%}"
            except (TypeError, ValueError):
                prop_txt = prop
            ref = self._cell(row, "is_reference")
            ref_txt = {"TRUE": "是", "FALSE": "否"}.get(ref.upper(), ref)
            self._insert_row(
                self.tree,
                self._cell(row, "haplotype_id") or None,
                (
                    self._cell(row, "rank"),
                    self._cell(row, "haplotype_id"),
                    self._cell(row, "count"),
                    prop_txt,
                    ref_txt,
                    self._cell(row, "n_snv"),
                    self._cell(row, "n_ins"),
                    self._cell(row, "n_del"),
                    self._cell(row, "length"),
                    self._cell(row, "variants"),
                ),
            )

    def _load_qc(self, path: Path) -> None:
        if not path.is_file():
            return
        _fields, rows, error = self._read_tsv_safe(path)
        if error:
            self._set_text(self.qc_text, f"qc.tsv 不符合契约，无法显示：{error}")
            self._append_log(f"[GUI] qc.tsv 不符合契约：{error}")
            return
        lines = [f"{self._cell(r, 'metric'):<24} {self._cell(r, 'value')}" for r in rows]
        self._set_text(self.qc_text, "\n".join(lines))

    def _load_files(self, outdir: Path) -> None:
        try:
            entries = sorted(p for p in outdir.iterdir() if p.is_file())
        except OSError as exc:
            self._append_log(f"[GUI] 无法列出输出目录：{exc}")
            return
        for p in entries:
            self.files_tree.insert("", "end", iid=p.name,
                                   values=(p.name, f"{p.stat().st_size:,}"))

    def _on_select_haplotype(self, _event) -> None:
        sel = self.tree.selection()
        if not sel or not self.last_outdir:
            return
        hid = sel[0]
        if not self.fasta_cache:
            self.fasta_cache = self._load_fasta(self.last_outdir / "haplotypes.fasta")
        seq = self.fasta_cache.get(hid)
        if seq:
            self._set_text(self.seq_box, f">{hid}  ({len(seq)} bp)\n{seq}")
            return
        # haplotypes.fasta only holds the top-n sequences, so a row below that
        # cutoff has no exported sequence. Say so instead of showing nothing.
        values = self.tree.item(hid, "values")
        variants = values[9] if len(values) > 9 else "."
        top_n = self.var_topn.get()
        self._set_text(
            self.seq_box,
            f"{hid}：未导出序列。\n\n"
            f"haplotypes.fasta 仅包含前 {top_n} 条单倍型的序列，"
            f"该单倍型排名超出该范围。\n"
            f"变异组成：{variants or '.'}\n\n"
            f"如需其序列，请增大“显示前 n 条”后重新运行。",
        )

    @staticmethod
    def _load_fasta(path: Path) -> dict[str, str]:
        """Parse haplotypes.fasta into {haplotype_id: sequence}."""
        out: dict[str, str] = {}
        if not path.is_file():
            return out
        name: str | None = None
        chunks: list[str] = []
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            for line in fh:
                line = line.rstrip("\n")
                if line.startswith(">"):
                    if name is not None:
                        out[name] = "".join(chunks)
                    header = line[1:].strip()
                    # headers look like H1_218delG or C3_...
                    name = header.split("_", 1)[0].split()[0]
                    chunks = []
                elif name is not None:
                    chunks.append(line.strip())
        if name is not None:
            out[name] = "".join(chunks)
        return out

    def _append_log(self, line: str) -> None:
        self.log_text.configure(state="normal")
        self.log_text.insert("end", line + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")


def main() -> int:
    root = tk.Tk()
    root.title(APP_TITLE)
    root.geometry("1040x720")
    root.minsize(880, 600)
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass

    base = resource_base()
    app = NanoampApp(root, find_repo_root(base))
    _ = app
    root.mainloop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
