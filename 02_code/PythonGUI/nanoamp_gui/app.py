"""nanoamp GUI - a simple Tkinter window over the nanoamp R analysis.

The analysis logic lives in the ``nanoamp`` R package and is invoked exactly as
the CLI would invoke it (see ``r_runner``). Nothing is reimplemented here, so
the GUI and the command line can never disagree about results.

Tkinter is used deliberately: it ships with CPython, so there is no runtime
dependency to install and PyInstaller can freeze it into a single .exe.
"""

from __future__ import annotations

import csv
import os
import queue
import subprocess
import sys
import threading
import traceback
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from .r_runner import NanoampRunner, RNotFoundError, find_rscript

APP_TITLE = "nanoamp - 纳米孔 PCR 产物分析"
MODES = [
    ("A - 参考引导（推荐）", "A"),
    ("B - 从头聚类", "B"),
    ("C - 精确匹配（仅诊断）", "C"),
]


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
        self.log_queue: queue.Queue[str | None] = queue.Queue()
        self.last_outdir: Path | None = None
        self.fasta_cache: dict[str, str] = {}

        # form state
        self.var_reads = tk.StringVar()
        self.var_reference = tk.StringVar()
        self.var_outdir = tk.StringVar(value=str(latest_outdir(repo_root)))
        self.var_mode = tk.StringVar(value="A")
        self.var_topn = tk.IntVar(value=20)
        self.var_status = tk.StringVar(value="就绪。选择 FASTQ 和参考序列后点击“开始分析”。")

        self._build_layout()
        self._detect_environment()
        self.after(100, self._drain_log_queue)

    # ------------------------------------------------------------------ UI
    def _build_layout(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # -- title
        header = ttk.Frame(self)
        header.grid(row=0, column=0, sticky="ew", pady=(0, 8))
        ttk.Label(header, text=APP_TITLE, font=("Segoe UI", 14, "bold")).pack(anchor="w")
        ttk.Label(
            header,
            text="分析逻辑由 nanoamp R 包执行，本窗口只是调用它的外壳。",
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

        # -- results
        nb = ttk.Notebook(self)
        nb.grid(row=2, column=0, sticky="nsew", pady=8)
        self._build_haplotype_tab(nb)
        self._build_qc_tab(nb)
        self._build_files_tab(nb)
        self._build_log_tab(nb)

        # -- actions
        actions = ttk.Frame(self)
        actions.grid(row=3, column=0, sticky="ew")
        actions.columnconfigure(2, weight=1)

        self.btn_run = ttk.Button(actions, text="开始分析", command=self._on_run)
        self.btn_run.grid(row=0, column=0)
        self.btn_doctor = ttk.Button(actions, text="环境自检", command=self._on_doctor)
        self.btn_doctor.grid(row=0, column=1, padx=(6, 0))
        self.btn_open = ttk.Button(
            actions, text="打开输出目录", command=self._on_open_outdir, state="disabled"
        )
        self.btn_open.grid(row=0, column=3, padx=(6, 0))

        self.progress = ttk.Progressbar(actions, mode="indeterminate", length=140)
        self.progress.grid(row=0, column=4, padx=(12, 0))

        status = ttk.Label(self, textvariable=self.var_status, anchor="w", foreground="#333333")
        status.grid(row=4, column=0, sticky="ew", pady=(6, 0))
        self.status_label = status

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
        ttk.Label(frame, text="选中某一行可查看该单倍型的完整序列",
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

    # -------------------------------------------------------- environment
    def _detect_environment(self) -> None:
        try:
            self.runner = NanoampRunner(self.repo_root)
        except RNotFoundError as exc:
            self.runner = None
            self.var_status.set("未找到 R —— 点击“环境自检”查看详情")
            self._append_log(str(exc))
            return
        self._append_log(f"仓库根目录 : {self.repo_root}")
        self._append_log(f"Rscript    : {self.runner.rscript}")
        self._append_log("已就绪。")

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
            messagebox.showwarning("缺少输入", "请先选择测速文件、目的序列和输出目录。")
            return
        for label, path in (("测序文件", reads), ("目的序列", reference)):
            if not Path(path).is_file():
                messagebox.showerror("文件不存在", f"{label} 不存在：\n{path}")
                return

        if self.runner is None:
            messagebox.showerror("缺少 R", "没有找到 Rscript。请先运行“环境自检”。")
            return

        argv = [
            "call",
            "--reads", reads,
            "--reference", reference,
            "--outdir", outdir,
            "--mode", self.var_mode.get(),
            "--top-n", str(self.var_topn.get()),
        ]
        self._clear_results()
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
            messagebox.showerror("缺少 R", str(exc))
            return
        self.runner = runner
        self._set_running(True)
        self._append_log("")
        self._append_log("$ nanoamp doctor")
        self.worker = threading.Thread(
            target=self._doctor_worker, args=(runner,), daemon=True
        )
        self.worker.start()

    def _on_open_outdir(self) -> None:
        if not self.last_outdir or not self.last_outdir.is_dir():
            return
        self._open_path(self.last_outdir)

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
            messagebox.showerror("无法打开", f"{path}\n\n{exc}")

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
        if running:
            self.progress.start(12)
            self.var_status.set("正在分析…（首次运行需加载 R 包，可能稍慢）")
        else:
            self.progress.stop()

    def _finish_doctor(self, code: int) -> None:
        self._set_running(False)
        self.var_status.set("环境自检完成。" if code == 0 else f"环境自检失败（退出码 {code}）。")

    def _finish_run(self, code: int, outdir: Path) -> None:
        self._set_running(False)
        self.last_outdir = outdir
        if code != 0:
            self.var_status.set(f"分析失败（退出码 {code}）。请查看“运行日志”。")
            messagebox.showerror(
                "分析失败",
                "分析没有正常完成。\n\n请查看“运行日志”标签页，"
                "常见原因是 R 包未安装或 minimap2 不可用。",
            )
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

    @staticmethod
    def _read_tsv(path: Path) -> tuple[list[str], list[dict[str, str]]]:
        with path.open("r", encoding="utf-8", errors="replace", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            return list(reader.fieldnames or []), list(reader)

    def _load_results(self, outdir: Path) -> None:
        self._load_haplotypes(outdir / "haplotypes.tsv")
        self._load_qc(outdir / "qc.tsv")
        self._load_files(outdir)

    def _load_haplotypes(self, path: Path) -> None:
        if not path.is_file():
            self._append_log(f"[GUI] 未找到 {path.name}")
            return
        _fields, rows = self._read_tsv(path)
        for row in rows:
            prop = row.get("proportion", "")
            try:
                prop_txt = f"{float(prop):.2%}"
            except (TypeError, ValueError):
                prop_txt = prop
            ref = row.get("is_reference", "")
            ref_txt = {"TRUE": "是", "FALSE": "否"}.get(ref.upper(), ref)
            self.tree.insert(
                "", "end",
                iid=row.get("haplotype_id", ""),
                values=(
                    row.get("rank", ""),
                    row.get("haplotype_id", ""),
                    row.get("count", ""),
                    prop_txt,
                    ref_txt,
                    row.get("n_snv", ""),
                    row.get("n_ins", ""),
                    row.get("n_del", ""),
                    row.get("length", ""),
                    row.get("variants", ""),
                ),
            )

    def _load_qc(self, path: Path) -> None:
        if not path.is_file():
            return
        _fields, rows = self._read_tsv(path)
        lines = [f"{r.get('metric', ''):<24} {r.get('value', '')}" for r in rows]
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
            f"{hid}: 未导出序列。\n\n"
            f"haplotypes.fasta 只包含前 {top_n} 条（top-n）单倍型的序列，"
            f"该单倍型排名靠后，因此文件里没有它的序列。\n"
            f"它的变异组成是：{variants or '.'}\n\n"
            f"如需其序列，把“显示前 n 条”调大后重新运行。",
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
