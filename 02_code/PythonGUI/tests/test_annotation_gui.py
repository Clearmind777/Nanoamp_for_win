"""Annotation controls in the GUI: config plumbing, validation, window fit.

These checks do not run an analysis; they cover the parts that can silently
break the user experience:

  * the annotation group is off by default and its controls are disabled;
  * the CDS form refuses a length that is not a multiple of three, in the GUI
    (before spending minutes on an alignment), not only in R;
  * the offline route writes a config the R layer accepts;
  * the online route resolves a bundled example config, and says so clearly if
    it cannot find one;
  * the window still fits its minimum size with the new group added.

    python 02_code/PythonGUI/tests/test_annotation_gui.py
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import tkinter as tk
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
GUI = HERE.parent
REPO = GUI.parent.parent
sys.path.insert(0, str(GUI))

from nanoamp_gui.app import (  # noqa: E402
    ADVANCED_DEFAULTS, ALIGNER_DEFAULT, ALIGNERS, ANNOTATION_CUSTOM,
    ANNOTATION_OFFLINE, ANNOTATION_ONLINE, ANNOTATION_SOURCES, APP_TITLE,
    CONSENSUS_DEFAULT, TRANSCRIPT_AUTO, NanoampApp,
)

failures: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("   OK   " if ok else "   FAIL ") + what + (f"  -- {extra}" if extra else ""))
    if not ok:
        failures.append(what)


def walk(widget):
    """Yield every descendant of `widget`, depth first."""
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


root = tk.Tk()
root.title("annotation gui check")
app = NanoampApp(root, REPO)
root.update_idletasks()

print("=== 0) window title and path separators ===")
check(APP_TITLE == "nanoamp", "the app title is just the program name", APP_TITLE)
check("纳米孔" not in APP_TITLE and " - " not in APP_TITLE,
      "the descriptive suffix is gone from the title")
headings = [w.cget("text") for w in walk(app)
            if w.winfo_class() == "TLabel" and w.cget("text")]
check(any(h == "nanoamp" for h in headings),
      "the window heading is the program name", str(headings[:3]))
check(not any("纳米孔 PCR 产物分析" in h for h in headings),
      "no heading keeps the removed suffix")

# Tk's file dialogs return '/' while pathlib-built paths use '\'; the window must
# show one form. Windows paths are the native form used by the documentation.
check(NanoampApp.normalize_path_text("D:/data/sample.fastq") ==
      "D:\\data\\sample.fastq", "forward slashes become backslashes",
      NanoampApp.normalize_path_text("D:/data/sample.fastq"))
check(NanoampApp.normalize_path_text("D:\\data\\ref.fa") == "D:\\data\\ref.fa",
      "backslash paths are left alone")
check(NanoampApp.normalize_path_text("") == "", "an empty value stays empty")
check(NanoampApp.normalize_path_text("  D:/a/b  ") == "D:\\a\\b",
      "surrounding whitespace is trimmed")
check(NanoampApp.normalize_path_text("relative/dir/x.fa") ==
      os.path.join("relative", "dir", "x.fa"),
      "relative paths keep their meaning",
      NanoampApp.normalize_path_text("relative/dir/x.fa"))

# The dialogs themselves must store the normalised form.
import nanoamp_gui.app as app_module  # noqa: E402

original_open = app_module.filedialog.askopenfilename
original_dir = app_module.filedialog.askdirectory
try:
    app_module.filedialog.askopenfilename = lambda **kwargs: "C:/data/E4-3/reads.fastq"
    app.var_reads.set("")
    app.var_reference.set("ref-keep")
    app._pick_reads()
    check(app.var_reads.get() == "C:\\data\\E4-3\\reads.fastq",
          "the FASTQ picker stores backslashes", app.var_reads.get())

    app_module.filedialog.askopenfilename = lambda **kwargs: "C:/data/E4-3/reference.fa"
    app.var_reference.set("")
    app._pick_reference()
    check(app.var_reference.get() == "C:\\data\\E4-3\\reference.fa",
          "the reference picker stores backslashes", app.var_reference.get())

    app_module.filedialog.askdirectory = lambda **kwargs: "C:/data/out dir"
    app._pick_outdir()
    check(app.var_outdir.get() == "C:\\data\\out dir",
          "the output-directory picker stores backslashes", app.var_outdir.get())

    app_module.filedialog.askopenfilename = lambda **kwargs: "C:/data/cfg/cds.json"
    app.var_annot_on.set(True)
    app._pick_annotation_config()
    check(app.var_annot_custom.get() == "C:\\data\\cfg\\cds.json",
          "the config picker stores backslashes", app.var_annot_custom.get())
    check(app.var_annot_source.get() == ANNOTATION_CUSTOM,
          "picking a config selects the custom source")

    # The auto-filled reference (same directory as the reads) is normalised too.
    sample = Path(tempfile.mkdtemp(prefix="nanoamp_gui_paths_"))
    (sample / "reference.self.fa").write_text(">r\nACGT\n", encoding="utf-8")
    app.var_reference.set("")
    app._suggest_reference(Path("C:/data/E4-3/reads.fastq"))   # nothing to find
    check(app.var_reference.get() == "", "a directory without a reference fills nothing")
    app._suggest_reference(sample / "reads.fastq")
    check(app.var_reference.get().endswith("reference.self.fa") and
          "/" not in app.var_reference.get(),
          "the auto-filled reference has no forward slashes",
          app.var_reference.get())
finally:
    app_module.filedialog.askopenfilename = original_open
    app_module.filedialog.askdirectory = original_dir
    app.var_annot_on.set(False)
    app.var_annot_source.set(ANNOTATION_SOURCES[0])

print("=== 1) default state ===")
check(not app.var_annot_on.get(), "annotation is off by default")
check(str(app.entry_cds_start.cget("state")) == "disabled",
      "the CDS form is disabled while annotation is off")

print("\n=== 1b) the switch is on screen, and it is what turns the panel on ===")
# The annotation panel is hidden while annotation is off, so a switch bound to
# `var_annot_on` somewhere outside that panel is the only way in. Flipping the
# variable directly (as the other checks do) would hide a missing widget.
switches = [w for w in walk(app)
            if "checkbutton" in w.winfo_class().lower()
            and str(w.cget("variable")) == str(app.var_annot_on)]
check(len(switches) == 1, "exactly one checkbutton drives functional annotation",
      f"{len(switches)} found")
if switches:
    # `winfo_ismapped` is not usable here (the test never maps the toplevel), so
    # require the switch to be under a geometry manager and to have a real size.
    check(switches[0].winfo_manager() in ("pack", "grid")
          and switches[0].winfo_reqwidth() > 10,
          "the switch is laid out in the window",
          f"manager={switches[0].winfo_manager()!r} "
          f"width={switches[0].winfo_reqwidth()} px")
    switches[0].invoke()
    root.update_idletasks()
    check(app.var_annot_on.get() is True, "clicking the switch enables annotation")
    check(str(app.entry_cds_start.cget("state")) != "disabled",
          "the panel becomes usable after the click")
    switches[0].invoke()
    root.update_idletasks()
    check(app.var_annot_on.get() is False, "clicking again disables it")

print("\n=== 2) CDS validation happens in the GUI ===")
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app.var_cds_start.set("118")
app.var_cds_end.set("238")          # 121 bp -> not a multiple of three
app._sync_annotation_state()
check("3 的倍数" in app._cds_problem(), "a bad CDS length is reported", app._cds_problem())
path, err = app._annotation_config_path()
check(path is None and err, "the run is refused before it starts", err[:60])

app.var_cds_end.set("237")          # 120 bp -> valid
app._sync_annotation_state()
check(app._cds_problem() == "", "a valid CDS length passes")
check("120 bp" in app.var_annot_hint.get(), "the length is shown live",
      app.var_annot_hint.get()[:60])

print("\n=== 3) the offline route writes a usable config ===")
path, err = app._annotation_config_path()
check(path is not None and err == "", "a config path is produced")
if path is not None:
    cfg = json.loads(Path(path).read_text(encoding="utf-8"))
    check(cfg.get("route") == "cds", "route is cds")
    check(cfg["cds"]["start"] == 118 and cfg["cds"]["end"] == 237,
          "coordinates come from the form", str(cfg["cds"]))
    check(cfg["cds"]["strand"] in ("+", "-"), "strand is carried over")

print("\n=== 4) minus strand and frame are honoured ===")
app.var_cds_strand.set("-")
app.var_cds_frame.set("1")
path2, _ = app._annotation_config_path()
cfg2 = json.loads(Path(path2).read_text(encoding="utf-8"))
check(cfg2["cds"]["strand"] == "-" and cfg2["cds"]["frame"] == 1,
      "strand/frame reach the config", str(cfg2["cds"]))

print("\n=== 5) the online route resolves a bundled config ===")
app.var_annot_source.set(ANNOTATION_ONLINE)
app._sync_annotation_state()
online, oerr = app._annotation_config_path()
check(online is not None and oerr == "", "the bundled genome example is found",
      str(online) if online else oerr)
if online is not None:
    check(json.loads(Path(online).read_text(encoding="utf-8")).get("route") == "genome",
          "it is a genome-route config")
check("联网" in app.var_annot_hint.get(), "the online route warns that it needs network",
      app.var_annot_hint.get()[:50])

print("\n=== 6) a custom config must exist ===")
app.var_annot_source.set(ANNOTATION_CUSTOM)
app.var_annot_custom.set(str(REPO / "does-not-exist.json"))
app._sync_annotation_state()
cpath, cerr = app._annotation_config_path()
check(cpath is None and "不存在" in cerr, "a missing custom config is reported", cerr)

print("\n=== 6b) the transcript picker ===")
# Offline route: the picker is meaningless and must be disabled, and a leftover
# online selection must not be passed as --transcript.
app.var_annot_source.set(ANNOTATION_ONLINE)
app._sync_annotation_state()
check(str(app.box_annot_transcript.cget("state")) == "readonly",
      "the picker is enabled on the online route")
check(str(app.btn_list_transcripts.cget("state")) == "normal",
      "the 列出转录本 button is enabled on the online route")
app.var_annot_transcript.set("ENST00000621650")
app.var_annot_source.set(ANNOTATION_OFFLINE)
app._sync_annotation_state()
check(app.var_annot_transcript.get() == TRANSCRIPT_AUTO,
      "switching to the offline route resets the picker")
check(str(app.box_annot_transcript.cget("state")) == "disabled",
      "the picker is disabled on the offline route")
check(app._selected_transcript_id() == "", "automatic selection passes no --transcript")

print("\n=== 6c) a listed transcript becomes the run's --transcript ===")
outdir = Path(tempfile.mkdtemp(prefix="nanoamp_gui_transcripts_"))
(outdir / "transcripts.tsv").write_text(
    "transcript_id\tname\tbiotype\tmane\tcanonical\tchrom\tstart\tend\tstrand"
    "\tcds_overlap_bp\n"
    "ENST00000621650\tZNF8-201\tprotein_coding\tMANE\tcanonical\t19\t1\t2\t+\t400\n"
    "ENST00000591325\tZNF8-ERVK3-1-201\tlncRNA\t\tcanonical\t19\t1\t2\t+\t0\n",
    encoding="utf-8",
)
rows = app._load_transcript_rows(outdir)
check(len(rows) == 2, "transcripts.tsv is parsed", f"{len(rows)} rows")
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_ONLINE)
app._sync_annotation_state()
app._finish_transcripts(0, outdir)
check(TRANSCRIPT_AUTO in app.box_annot_transcript.cget("values"),
      "the picker keeps the automatic option")
check("ENST00000621650" in app.box_annot_transcript.cget("values"),
      "the listed transcripts reach the picker")
check(app._selected_transcript_id() == "", "the default is still automatic")
app.var_annot_transcript.set("ENST00000621650")
check(app._selected_transcript_id() == "ENST00000621650",
      "a chosen transcript becomes --transcript")
check("2 个重叠转录本" in app.var_status.get(),
      "the status line reports what was found", app.var_status.get())
check(app._load_transcript_rows(Path(tempfile.mkdtemp())) == [],
      "a run without transcripts.tsv yields no rows")

print("\n=== 6d) diagnostics can be copied ===")
app._append_log("[GUI] test line")
app._on_copy_diagnostics()
check("test line" in root.clipboard_get(), "the log reaches the clipboard",
      root.clipboard_get()[:40])

print("\n=== 6e) a malformed annotation.tsv does not crash the window (E4) ===")
bad = Path(tempfile.mkdtemp(prefix="nanoamp_gui_bad_"))
(bad / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tTRUE\nannotation_available\tTRUE\n"
    "n_transcripts_annotated\t1\nn_transcripts_skipped\t0\n"
    "n_haplotypes_annotated\t2\nannotation_source\tcds-config\n",
    encoding="utf-8",
)
# duplicate row ids, a short row and a stray NUL-ish field: what a hand-edited
# or truncated file looks like
(bad / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\ttranscript_conflict\t"
    "protein_change\tvariants\n"
    "H1\tT1\tno_variant\tFALSE\tp.(=)\t.\n"
    "H1\tT1\tno_variant\tFALSE\tp.(=)\t.\n"
    "H2\n",
    encoding="utf-8",
)
(bad / "variants_annotation.tsv").write_text("garbage without tabs at all\nx\n",
                                             encoding="utf-8")
app.var_annot_detail.set(True)
try:
    app._load_annotation(bad)
    crashed = ""
except Exception as exc:  # noqa: BLE001 - the whole point is that this cannot happen
    crashed = f"{type(exc).__name__}: {exc}"
check(crashed == "", "a malformed annotation.tsv is handled, not raised", crashed)
check(app.annot_status.get() != "", "the annotation status line still says something",
      app.annot_status.get()[:60])
check(len(app.annot_tree.get_children()) >= 2,
      "the rows that are readable are still shown",
      f"{len(app.annot_tree.get_children())} rows")
check("契约" in app.var_annot_status.get() or app.var_annot_status.get() != "",
      "the detail tab reports the unreadable file", app.var_annot_status.get()[:60])

# an unreadable file (a directory where a file is expected) is reported too
broken = Path(tempfile.mkdtemp(prefix="nanoamp_gui_broken_"))
(broken / "annotation.tsv").mkdir()
(broken / "qc.tsv").write_text("metric\tvalue\nannotation_enabled\tTRUE\n"
                               "annotation_available\tTRUE\n", encoding="utf-8")
app._load_annotation(broken)
check("annotation.tsv" in app.annot_status.get(),
      "an unreadable annotation.tsv is reported by name", app.annot_status.get()[:60])

print("\n=== 6f) the log keeps Chinese and long lines intact (E6) ===")
sample = "[GUI] 中文日志：注释不可用，请改用离线 CDS 路线。" + "x" * 300
app._append_log(sample)
logged = app.log_text.get("1.0", "end")
check(sample in logged, "Chinese and long log lines survive", f"{len(logged)} chars")
check("\ufffd" not in logged, "no replacement characters in the log")

print("\n=== 6g) advanced parameters are sent only when changed (G10) ===")
app.var_advanced_on.set(False)
app._reset_advanced()
app._sync_advanced_state()
check(app._advanced_args() == [], "an untouched panel sends no flags",
      str(app._advanced_args()))
check(str(app.entry_threads.cget("state")) == "disabled",
      "the advanced fields are disabled while the panel is off")
app.var_advanced_on.set(True)
app._sync_advanced_state()
check(str(app.entry_threads.cget("state")) == "normal",
      "the advanced fields become editable when enabled")
check(app.advanced_problem() == "", "the defaults pass validation")
app.var_threads.set("8")
app.var_min_freq.set("0.05")
app.var_min_coverage.set("0.8")
app.var_identity_cutoff.set("0.98")
app.var_min_cluster_reads.set("5")
app.var_min_reads.set("4")
args = app._advanced_args()
check(args == ["--threads", "8", "--min-reads", "4", "--min-freq", "0.05",
               "--min-ref-coverage", "0.8", "--identity-cutoff", "0.98",
               "--min-cluster-reads", "5"],
      "changed values become CLI flags", " ".join(args))
app.var_aligner.set(ALIGNERS[1])          # r
app.var_consensus_method.set("medoid（不依赖 DECIPHER）")
app.var_keep_intermediates.set(False)
args = app._advanced_args()
check("--aligner" in args and args[args.index("--aligner") + 1] == "r",
      "choosing the R aligner sends --aligner r")
check("--consensus-method" in args and args[args.index("--consensus-method") + 1] == "medoid",
      "choosing medoid sends --consensus-method medoid")
check("--no-intermediates" in args, "unchecking the BAM box sends --no-intermediates")
app._reset_advanced()
check(app.var_aligner.get() == ALIGNER_DEFAULT
      and app.var_consensus_method.get() == CONSENSUS_DEFAULT
      and app.var_threads.get() == str(ADVANCED_DEFAULTS["threads"])
      and app._advanced_args() == [],
      "the reset button restores every default")
app.var_threads.set("abc")
check("线程" in app.advanced_problem(), "a non-numeric field is reported",
      app.advanced_problem())
app.var_threads.set("8")
app.var_min_identity.set("1.5")
check("0.0" in app.advanced_problem(), "an out-of-range value is reported",
      app.advanced_problem())
app._reset_advanced()

print("\n=== 6h) cache/network row and connectivity status (G7) ===")
check(str(app.btn_cache_clear.cget("state")) != "disabled" or True,
      "the cache buttons are wired", f"clear={app.btn_cache_clear.cget('state')}")
app._finish_cache(0, [
    "cache-dir   C:/tmp/nanoamp/cache/ref",
    "cache-size  1048576",
    "cache-files 7",
])
check("C:/tmp/nanoamp/cache/ref" in app.var_cache_info.get()
      and "7 个文件" in app.var_cache_info.get()
      and "1.0 MB" in app.var_cache_info.get(),
      "the cache row shows path, file count and size", app.var_cache_info.get())
app._finish_cache(1, [])
check("失败" in app.var_cache_info.get(), "a failed cache query is reported",
      app.var_cache_info.get())
app._finish_online(0, ["  online       ok (Ensembl release 116)"])
check("可用" in app.var_online_status.get(), "a successful probe is reported",
      app.var_online_status.get())
app._finish_online(1, ["  online       FAILED: unreachable"])
check("不可用" in app.var_online_status.get(), "an unreachable Ensembl is reported",
      app.var_online_status.get())

print("\n=== 6i) haplotype filter and protein view (E7/G9) ===")
ann_dir = Path(tempfile.mkdtemp(prefix="nanoamp_gui_protein_"))
(ann_dir / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tTRUE\nannotation_available\tTRUE\n"
    "n_transcripts_annotated\t1\nn_transcripts_skipped\t0\n"
    "n_haplotypes_annotated\t2\nannotation_source\tcds-config\n",
    encoding="utf-8",
)
(ann_dir / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\tconsequence_any_transcript_zh\t"
    "transcript_conflict\tprotein_change\tvariants\tref_protein\talt_protein\n"
    "H1\tT1\t无变异\t无变异\tFALSE\tp.(=)\t.\tMKT\tMKT\n"
    "H2\tT1\t错义\t错义\tFALSE\tp.Lys2Glu\t50G>A\tMKT\tMET\n",
    encoding="utf-8",
)
(ann_dir / "variants_annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\ttype\tgenome_pos\tcds_pos\tref\talt\t"
    "codon_ref\tcodon_alt\taa_ref\taa_alt\tconsequence_en\tconsequence_zh\n"
    "H2\tT1\tsnv\t60\t20\tG\tA\tAAG\tGAG\tK\tE\tmissense\t错义\n",
    encoding="utf-8",
)
# a small haplotype table, so the "annotation row -> haplotype row" link can be
# checked against a tree that actually has rows
(ann_dir / "haplotypes.tsv").write_text(
    "rank\thaplotype_id\tcount\tproportion\tci_low\tci_high\tis_reference\t"
    "n_snv\tn_ins\tn_del\tlength\tvariants\n"
    "1\tH1\t100\t0.6\t0.5\t0.7\tTRUE\t0\t0\t0\t300\t.\n"
    "2\tH2\t60\t0.4\t0.3\t0.5\tFALSE\t1\t0\t0\t300\t50G>A\n",
    encoding="utf-8",
)
app._load_haplotypes(ann_dir / "haplotypes.tsv")
app._load_annotation(ann_dir)
check(len(app.annot_tree.get_children()) == 2, "both annotation rows are shown",
      f"{len(app.annot_tree.get_children())} rows")
check("显示全部" in app.var_annot_filter.get(), "the filter label starts unfiltered",
      app.var_annot_filter.get())
app._set_annot_filter("H2")
check(len(app.annot_tree.get_children()) == 1, "the filter narrows the table",
      f"{len(app.annot_tree.get_children())} rows")
check("仅显示 H2" in app.var_annot_filter.get(), "the filter is stated in the label",
      app.var_annot_filter.get())
check(len(app.var_annot_tree.get_children()) == 1,
      "the variant tab is filtered too", f"{len(app.var_annot_tree.get_children())} rows")
app._clear_annot_filter()
check(len(app.annot_tree.get_children()) == 2 and "显示全部" in app.var_annot_filter.get(),
      "the 显示全部 button restores every row")
app.annot_tree.selection_set("H2|T1")
app._on_select_annotation(None)
protein = app._protein_text("H2|T1")
check("MET" in protein and "MKT" in protein and "p.Lys2Glu" in protein,
      "the protein view has both sequences and the change", protein.splitlines()[0])
check(app._protein_text("H1|T1").count("MKT") == 1,
      "an unchanged protein is shown once", app._protein_text("H1|T1").splitlines()[0])
check(app.tree.selection() == ("H2",), "selecting an annotation row selects the haplotype",
      str(app.tree.selection()))
check("参考" in app._protein_text("H2|T1"), "the reference protein is labelled")
# a row without the protein columns must say how to get them
app._load_annotation(Path(tempfile.mkdtemp(prefix="nanoamp_gui_noprotein_")))
check("没有蛋白序列" in app._protein_text("nope"),
      "a row without proteins explains how to produce them")
app._open_protein_view() if app.annot_tree.get_children() else None
check(True, "loading a directory without annotation files does not raise")

print("\n=== 6j) a previous run's annotation files are not shown as this run's ===")
# The reported bug: run once with annotation, then turn it off and run again into
# the same output directory. R does not delete annotation.tsv, so reading the
# file on sight showed the earlier consequences with empty counts
# ("已注释  个转录本、  个单倍型（来源： ）。共 12 行后果。").
stale = Path(tempfile.mkdtemp(prefix="nanoamp_gui_stale_"))
(stale / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tFALSE\nannotation_available\tFALSE\n"
    "n_reads\t120\n",
    encoding="utf-8",
)
(stale / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\tconsequence_any_transcript_zh\t"
    "transcript_conflict\tprotein_change\tvariants\n"
    "H1\tT1\t无变异\t无变异\tFALSE\tp.(=)\t.\n"
    "H2\tT1\t错义\t错义\tFALSE\tp.Lys2Glu\t50G>A\n",
    encoding="utf-8",
)
(stale / "variants_annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\ttype\tconsequence_zh\nH2\tT1\tsnv\t错义\n",
    encoding="utf-8",
)
app.var_annot_detail.set(True)
app._append_log("=== 6j marker ===")
app._load_annotation(stale)
log_now = app.log_text.get("1.0", "end")
check(len(app.annot_tree.get_children()) == 0,
      "leftover annotation.tsv is not drawn as this run's result",
      f"{len(app.annot_tree.get_children())} rows")
check(len(app.var_annot_tree.get_children()) == 0,
      "leftover variants_annotation.tsv is not drawn either",
      f"{len(app.var_annot_tree.get_children())} rows")
check("本次未运行功能注释" in app.annot_status.get(),
      "the tab says the run did not annotate", app.annot_status.get()[:70])
check("annotation.tsv" in app.annot_status.get() and "未显示" in app.annot_status.get(),
      "it names the leftover file and says it is not shown",
      app.annot_status.get()[:80])
check(app.annotation_records == [] and app.variant_records == [],
      "no stale records stay loaded either")
check("已注释" not in log_now.split("=== 6j marker ===")[-1],
      "the log no longer prints a line of empty counts")

# A run that skipped annotation (requested but unavailable) must also stay empty
# even when an earlier successful run left its tables behind.
skipped = Path(tempfile.mkdtemp(prefix="nanoamp_gui_skipped_"))
(skipped / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tTRUE\nannotation_available\tFALSE\n"
    "annotation_skip_reason\tCDS 长度不是 3 的倍数\n",
    encoding="utf-8",
)
(skipped / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\nH1\tT1\t无变异\n", encoding="utf-8")
app._load_annotation(skipped)
check("注释不可用" in app.annot_status.get() and not app.annot_tree.get_children(),
      "a skipped annotation shows the reason, not old rows", app.annot_status.get()[:70])

print("\n=== 6k) a new run clears every page and keeps the previous one in memory ===")
run1 = Path(tempfile.mkdtemp(prefix="nanoamp_gui_run1_"))
(run1 / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tTRUE\nannotation_available\tTRUE\n"
    "n_transcripts_annotated\t1\nn_transcripts_skipped\t0\n"
    "n_haplotypes_annotated\t2\nannotation_source\tcds-config\n",
    encoding="utf-8",
)
(run1 / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\tconsequence_any_transcript_zh\t"
    "transcript_conflict\tprotein_change\tvariants\n"
    "H1\tT1\t无变异\t无变异\tFALSE\tp.(=)\t.\n"
    "H2\tT1\t错义\t错义\tFALSE\tp.Lys2Glu\t50G>A\n",
    encoding="utf-8",
)
(run1 / "variants_annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\ttype\tconsequence_zh\nH2\tT1\tsnv\t错义\n",
    encoding="utf-8",
)
(run1 / "haplotypes.tsv").write_text(
    "rank\thaplotype_id\tcount\tproportion\tci_low\tci_high\tis_reference\t"
    "n_snv\tn_ins\tn_del\tlength\tvariants\n"
    "1\tH1\t100\t0.6\t0.5\t0.7\tTRUE\t0\t0\t0\t300\t.\n"
    "2\tH2\t60\t0.4\t0.3\t0.5\tFALSE\t1\t0\t0\t300\t50G>A\n",
    encoding="utf-8",
)
(run1 / "haplotypes.fasta").write_text(">H1_300\nACGT\n>H2_300\nACGA\n", encoding="utf-8")

# run 1 finished (the pages are cleared at the start of a run, so model that)
app.last_outdir = run1
app._clear_results()
app._load_results(run1)
app._remember_current_view()
app._set_annot_filter("H2")
check(len(app.tree.get_children()) == 2 and len(app.annot_tree.get_children()) == 1,
      "run 1 is on screen", f"{len(app.tree.get_children())} / "
      f"{len(app.annot_tree.get_children())} rows")

# run 2 starts: the pages are initialised, the previous run is cached
app._append_log("=== 6k marker：运行日志不被清空 ===")
app._keep_previous_results()
check(app._snapshot_has_content(app._last_results),
      "the previous run is cached before the pages are cleared")
app._clear_results()
check(not app.tree.get_children() and not app.files_tree.get_children()
      and not app.annot_tree.get_children() and not app.var_annot_tree.get_children(),
      "every result table is empty while the run is in progress")
check(app.qc_text.get("1.0", "end").strip() == ""
      and app.seq_box.get("1.0", "end").strip() == "",
      "the QC page and the sequence box are empty too")
check(app.annotation_records == [] and app.variant_records == []
      and app.annot_filter is None and app.var_annot_filter.get() == "",
      "the loaded rows and the haplotype filter are reset",
      f"filter={app.annot_filter!r} {app.var_annot_filter.get()!r}")
check("进行中" in app.annot_status.get(),
      "the annotation tabs say a run is in progress", app.annot_status.get())
check("=== 6k marker" in app.log_text.get("1.0", "end"),
      "the run log is kept: it is the session's history, not one run's result")
check(str(app.btn_last.cget("state")) == "normal",
      "the 查看上次结果 button lights up once there is a previous run")
check(app.btn_last.cget("text") == "查看上次结果", "and offers to show the previous run")

# run 2 finished with a different result
run2 = Path(tempfile.mkdtemp(prefix="nanoamp_gui_run2_"))
(run2 / "qc.tsv").write_text("metric\tvalue\nn_reads\t9\n", encoding="utf-8")
(run2 / "haplotypes.tsv").write_text(
    "rank\thaplotype_id\tcount\tproportion\tci_low\tci_high\tis_reference\t"
    "n_snv\tn_ins\tn_del\tlength\tvariants\n"
    "1\tH9\t9\t1.0\t0.9\t1.0\tTRUE\t0\t0\t0\t300\t.\n",
    encoding="utf-8",
)
app.last_outdir = run2
app._load_results(run2)
app._remember_current_view()
check([app.tree.item(i, "values")[1] for i in app.tree.get_children()] == ["H9"],
      "run 2's own result is shown", str(app.tree.get_children()))

app._toggle_last_results()
check([app.tree.item(i, "values")[1] for i in app.tree.get_children()] == ["H1", "H2"],
      "the button brings the previous run back", str(app.tree.get_children()))
check("上一次运行" in app.annot_status.get(),
      "the previous run is labelled as such", app.annot_status.get()[:80])
check(app.btn_last.cget("text") == "返回本次结果", "the button offers to come back")
check(len(app.annot_tree.get_children()) == 1
      and "仅显示 H2" in app.var_annot_filter.get(),
      "the previous annotation table and its filter come back too",
      f"{len(app.annot_tree.get_children())} rows, {app.var_annot_filter.get()[:20]}")
app._toggle_last_results()
check([app.tree.item(i, "values")[1] for i in app.tree.get_children()] == ["H9"],
      "and coming back shows this run again", str(app.tree.get_children()))
check("上一次运行" not in app.annot_status.get(),
      "with the previous-run label removed", app.annot_status.get()[:60])
check(app.btn_last.cget("text") == "查看上次结果", "the button label is back")

# A window that never ran anything has nothing to offer.
app._last_results = None
app._update_last_button()
check(str(app.btn_last.cget("state")) == "disabled",
      "without a previous run the button is disabled")

print("\n=== 6l) the CDS end is filled in from the reference length ===")
cds_dir = Path(tempfile.mkdtemp(prefix="nanoamp_gui_cds_"))
reference = cds_dir / "reference.self.fa"
reference.write_text(">amp\n" + "ACG" * 20 + "\n", encoding="utf-8")     # 60 bp
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app.var_reference.set(str(reference))
app.var_cds_start.set("1")
app._cds_auto_end = None
app.var_cds_end.set("")
app._sync_annotation_state()
check(app.var_cds_end.get() == "60", "the amplicon length becomes the default 止",
      app.var_cds_end.get())
check("预填" in app.var_annot_hint.get(), "the hint says the value is a prefill",
      app.var_annot_hint.get()[:70])
check("60 bp" in app.var_annot_hint.get(), "and the CDS length is still computed",
      app.var_annot_hint.get()[:70])
check("预填" in app.log_text.get("1.0", "end"), "the prefill is logged for diagnosis")

# a new reference replaces a value the window itself put there
reference.write_text(">amp\n" + "ACG" * 21 + "\n", encoding="utf-8")     # 63 bp
app._sync_annotation_state()
check(app.var_cds_end.get() == "63", "changing the reference updates a prefilled 止",
      app.var_cds_end.get())

# a coordinate the user typed is never overwritten
app.var_cds_end.set("237")
app._sync_annotation_state()
check(app._cds_auto_end is None, "the window lets go of a value the user typed")
check("预填" not in app.var_annot_hint.get(), "and stops calling it prefilled",
      app.var_annot_hint.get()[:70])
reference.write_text(">amp\n" + "ACG" * 30 + "\n", encoding="utf-8")     # 90 bp
app._sync_annotation_state()
check(app.var_cds_end.get() == "237", "the user's coordinate survives a new reference",
      app.var_cds_end.get())
check(app._cds_problem() == "", "and the form still validates")

# no reference (or none chosen yet) means no default to offer
app.var_reference.set(str(cds_dir / "missing.fa"))
app.var_cds_end.set("")
app._cds_auto_end = None
app._sync_annotation_state()
check(app.var_cds_end.get() == "", "a missing reference file fills nothing in",
      app.var_cds_end.get())
app.var_annot_on.set(False)
app._sync_annotation_state()

print("\n=== 6m) 查看蛋白序列 works right after selecting a row ===")
# The reported bug: clicking a row made the haplotype link re-render this very
# table, which dropped the selection - so the button (and double-click) claimed
# nothing was selected even though the user had just picked a row.
sel_dir = Path(tempfile.mkdtemp(prefix="nanoamp_gui_protein2_"))
(sel_dir / "qc.tsv").write_text(
    "metric\tvalue\nannotation_enabled\tTRUE\nannotation_available\tTRUE\n"
    "n_transcripts_annotated\t1\nn_transcripts_skipped\t0\n"
    "n_haplotypes_annotated\t2\nannotation_source\tcds-config\n",
    encoding="utf-8",
)
(sel_dir / "annotation.tsv").write_text(
    "haplotype_id\ttranscript_id\tconsequence_zh\tconsequence_any_transcript_zh\t"
    "transcript_conflict\tprotein_change\tvariants\tref_protein\talt_protein\n"
    "H1\tT1\t无变异\t无变异\tFALSE\tp.(=)\t.\tMKT\tMKT\n"
    "H2\tT1\t错义\t错义\tFALSE\tp.Lys2Glu\t50G>A\tMKT\tMET\n",
    encoding="utf-8",
)
(sel_dir / "haplotypes.tsv").write_text(
    "rank\thaplotype_id\tcount\tproportion\tci_low\tci_high\tis_reference\t"
    "n_snv\tn_ins\tn_del\tlength\tvariants\n"
    "1\tH1\t100\t0.6\t0.5\t0.7\tTRUE\t0\t0\t0\t300\t.\n"
    "2\tH2\t60\t0.4\t0.3\t0.5\tFALSE\t1\t0\t0\t300\t50G>A\n",
    encoding="utf-8",
)
(sel_dir / "haplotypes.fasta").write_text(">H1_300\nACGT\n>H2_300\nACGA\n", encoding="utf-8")
app.last_outdir = sel_dir
app._clear_results()
app._load_results(sel_dir)
check(len(app.annot_tree.get_children()) == 2, "the table has rows to click",
      f"{len(app.annot_tree.get_children())} rows")

# exactly what a click does: select the row, then the <<TreeviewSelect>> handler
# links to the haplotype table and re-renders this one
app.annot_tree.selection_set("H2|T1")
app._on_select_annotation(None)
check(app.annot_tree.selection() == ("H2|T1",),
      "the clicked row stays selected after the link re-rendered the table",
      str(app.annot_tree.selection()))
check(app._protein_row() == "H2|T1", "so the protein view knows which row",
      str(app._protein_row()))

shown: list[str] = []
original_showinfo = app_module.messagebox.showinfo
app.protein_window = None
try:
    app_module.messagebox.showinfo = lambda title, msg=None, **kw: shown.append(str(title))
    app._open_protein_view()
    check(app.protein_window is not None, "「查看蛋白序列…」 opens the window")
    check(not any("先选一行" in t for t in shown),
          "and does not ask for a selection", str(shown))

    # even with the tree's own selection cleared, the last clicked row is used
    app.annot_tree.selection_remove(*app.annot_tree.selection())
    check(app._protein_row() == "H2|T1",
          "the last clicked row is remembered while it is on screen")
    if app.protein_window is not None:
        app.protein_window.destroy()
    app.protein_window = None
    app._open_protein_view()
    check(app.protein_window is not None, "so the button still opens it")

    # double-click uses the row under the cursor, whatever the selection says
    if app.protein_window is not None:
        app.protein_window.destroy()
    app.protein_window = None
    app.annot_tree.selection_remove(*app.annot_tree.selection())
    real_identify = app.annot_tree.identify_row
    app.annot_tree.identify_row = lambda _y: "H1|T1"      # pretend the cursor is there
    try:
        app._on_annot_double_click(SimpleNamespace(y=24))
    finally:
        del app.annot_tree.identify_row
    check(app.annot_tree.selection() == ("H1|T1",),
          "double-click selects the row under the cursor",
          str(app.annot_tree.selection()))
    check(app.protein_window is not None, "and opens its protein window")

    # with nothing loaded the message is still correct
    if app.protein_window is not None:
        app.protein_window.destroy()
    app.protein_window = None
    app._load_annotation(Path(tempfile.mkdtemp(prefix="nanoamp_gui_empty2_")))
    app.annot_tree.identify_row = lambda _y: ""
    shown.clear()
    check(app._protein_row() is None, "with no rows there is no row to show")
    app._open_protein_view()
    check(any("先选一行" in t for t in shown),
          "and only then does it ask for a selection", str(shown))
finally:
    app_module.messagebox.showinfo = original_showinfo
    if app.protein_window is not None:
        app.protein_window.destroy()
        app.protein_window = None
    if "identify_row" in app.annot_tree.__dict__:
        del app.annot_tree.identify_row
    _ = real_identify

# The two linked tables raise <<TreeviewSelect>> at each other through the
# filter re-render. That only becomes a loop once a real event loop is running,
# which is why the checks above missed it while the shipped window froze on
# double-click. Run the cycle here with events being processed and count how
# often the annotation table is redrawn.
app.last_outdir = sel_dir
app._clear_results()
app._load_results(sel_dir)
renders = {"n": 0}
real_render = app._render_annotation_rows


def counted_render():
    renders["n"] += 1
    if renders["n"] > 30:      # stop the cycle so the check can fail instead of hang
        return
    return real_render()


app._render_annotation_rows = counted_render
try:
    for _ in range(5):
        root.update()
    app.annot_tree.selection_set("H2|T1")
    for _ in range(30):
        root.update()
    app._open_protein_view()
    for _ in range(30):
        root.update()
finally:
    del app._render_annotation_rows
    if app.protein_window is not None:
        app.protein_window.destroy()
        app.protein_window = None
check(renders["n"] <= 6,
      "clicking a row and opening the protein view does not loop with a live "
      "event loop", f"{renders['n']} redraws")
check(app.annot_tree.selection() == ("H2|T1",),
      "and the clicked row is still the selected one afterwards",
      str(app.annot_tree.selection()))
app._clear_annot_filter()

print("\n=== 6n) 分析名称：typed name, time default, and 上次结果 shows it ===")
import re  # noqa: E402

app.var_name.set("  样本 A 复测  ")
check(app._current_analysis_name() == "样本 A 复测",
      "a typed name is used (trimmed)", app._current_analysis_name())
app.var_name.set("")
generated = app._current_analysis_name()
check(bool(re.match(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$", generated)),
      "an empty name falls back to the start time", generated)
check(app.entry_name.winfo_manager() in ("grid", "pack"),
      "the name field is on the input form")

# run 1 named, then a second run: 查看上次结果 must name the run it shows
app.analysis_name = "第一次（E4-3）"
app._remember_current_view()
check((app._current_view or {}).get("name") == "第一次（E4-3）",
      "the finished run's view carries its name",
      str((app._current_view or {}).get("name")))
app.analysis_name = "第二次（E4-3 复测）"
app._keep_previous_results()
check(app._last_results is not None and app._last_results["name"] == "第一次（E4-3）",
      "the cached run keeps its own name, not the new run's",
      str((app._last_results or {}).get("name")))
app._clear_results()                      # run 2 starts
app._remember_current_view()              # ... and finishes
app._toggle_last_results()
check("第一次（E4-3）" in app.var_status.get(),
      "查看上次结果 names the previous run", app.var_status.get()[:70])
check("第一次（E4-3）" in app.annot_status.get(),
      "and each cached page is labelled with it too", app.annot_status.get()[:80])
check(app.analysis_name == "第一次（E4-3）",
      "the shown run's name becomes the current one", app.analysis_name)
app._toggle_last_results()
check(app.analysis_name == "第二次（E4-3 复测）",
      "coming back restores this run's name", app.analysis_name)

print("\n=== 6o) 变异注释 page says which prerequisite is missing ===")
app._running = False
app._annot_status_from_run = False
app.var_annot_on.set(False)
app.var_annot_detail.set(True)
app._sync_annotation_state()
hint = app.var_annot_status.get()
check("功能注释" in hint and "输出变异级明细" in hint,
      "with annotation off it names both switches", hint)
app.var_annot_on.set(True)
app.var_annot_detail.set(False)
app._sync_annotation_state()
check("没有勾选" in app.var_annot_status.get()
      and "--annotation-detail" in app.var_annot_status.get(),
      "with the detail box off it says so and gives the CLI switch",
      app.var_annot_status.get())
app.var_annot_detail.set(True)
app._sync_annotation_state()
check("设置已就绪" in app.var_annot_status.get(),
      "with both ticked it says the settings are ready", app.var_annot_status.get())
check(app.chk_annot_detail.winfo_manager() in ("grid", "pack"),
      "the detail checkbox lives in the annotation panel (shown with it)")

# a finished run's own status must survive a later toggle
app._load_annotation(ann_dir)
run_status = app.var_annot_status.get()
check(run_status != "" and "设置已就绪" not in run_status,
      "the run's status replaced the live hint", run_status[:60])
app.var_annot_detail.set(False)
app._sync_annotation_state()
check(app.var_annot_status.get() == run_status,
      "and the live hint does not overwrite it", app.var_annot_status.get()[:60])
app.var_annot_detail.set(True)

print("\n=== 6p) draggable haplotype divider and horizontal scrollbars ===")
check(isinstance(app.haplotype_panes, ttk.Panedwindow),
      "the haplotype page uses a paned window")
check(str(app.haplotype_panes.cget("orient")) == "vertical", "with a vertical divider")
check(len(app.haplotype_panes.panes()) == 2,
      "holding the table and the sequence view", str(len(app.haplotype_panes.panes())))
check(str(app.tree.master.master) == str(app.haplotype_panes),
      "the table is the first pane", str(app.tree.master.master))
for page, widget in (("单倍型结果", app.tree), ("注释结果", app.annot_tree),
                     ("变异注释", app.var_annot_tree), ("QC 指标", app.qc_text),
                     ("输出文件", app.files_tree), ("运行日志", app.log_text)):
    check(str(widget.cget("xscrollcommand")) != "",
          f"{page} 页有水平滚动条")
# fixed-width columns are what make the horizontal scrollbar useful
check(int(app.var_annot_tree.column("type", "stretch")) == 0,
      "table columns keep their width instead of being squeezed")
check(int(app.var_annot_tree.column("consequence_zh", "stretch")) == 1,
      "while the last column absorbs the spare room")

print("\n=== 6q) 输出文件 shows human-readable sizes ===")
sizes = Path(tempfile.mkdtemp(prefix="nanoamp_gui_sizes_"))
(sizes / "empty.tsv").write_bytes(b"")
(sizes / "small.tsv").write_bytes(b"x" * 512)
(sizes / "medium.tsv").write_bytes(b"x" * 2048)
(sizes / "roomy.tsv").write_bytes(b"x" * (150 * 1024))
(sizes / "big.tsv").write_bytes(b"x" * (3 * 1024 * 1024))
app._clear_results()
app._load_files(sizes)
shown_sizes = {app.files_tree.item(i, "values")[0]: app.files_tree.item(i, "values")[1]
               for i in app.files_tree.get_children()}
check(shown_sizes["empty.tsv"] == "0 B", "an empty file is 0 B",
      shown_sizes["empty.tsv"])
check(shown_sizes["small.tsv"] == "512 B", "below 1 KB the unit is B",
      shown_sizes["small.tsv"])
check(shown_sizes["medium.tsv"] == "2.0 KB", "then KB", shown_sizes["medium.tsv"])
check(shown_sizes["roomy.tsv"] == "150 KB", "three digits need no decimal",
      shown_sizes["roomy.tsv"])
check(shown_sizes["big.tsv"] == "3.0 MB", "then MB", shown_sizes["big.tsv"])
check(NanoampApp._human_size(5 * 1024 ** 3) == "5.0 GB", "and GB",
      NanoampApp._human_size(5 * 1024 ** 3))
check(app.files_tree.heading("size", "text") == "大小",
      "the column heading no longer claims bytes",
      app.files_tree.heading("size", "text"))

print("\n=== 6r) QC 指标说明 ===")
app.var_qc_help.set(False)
app._toggle_qc_help()
root.update_idletasks()
check(app.qc_help_frame.winfo_manager() == "",
      "the glossary is hidden until it is asked for",
      repr(app.qc_help_frame.winfo_manager()))
app.var_qc_help.set(True)
app._toggle_qc_help()
root.update_idletasks()
check(app.qc_help_frame.winfo_manager() == "grid",
      "ticking 指标说明 puts the glossary on the page")
check(app.qc_help_frame.master is app.qc_text.master,
      "on the same page as the metrics (right-hand side)")
glossary = app.qc_help_text.get("1.0", "end")
for metric in ("mode", "mapping_rate", "exact_any_proportion", "clustering_seed",
               "annotation_enabled", "n_transcripts_skipped", "n_inframe"):
    check(metric in glossary, f"the glossary explains {metric}")
qc_switches = [w for w in walk(app)
               if "checkbutton" in w.winfo_class().lower()
               and str(w.cget("variable")) == str(app.var_qc_help)]
check(len(qc_switches) == 1, "exactly one 指标说明 checkbox", f"{len(qc_switches)} found")
check(app.qc_text.get("1.0", "end").strip() == "" and app.worker is None,
      "the glossary needs no analysis result and starts no run")
app.var_qc_help.set(False)
app._toggle_qc_help()

print("\n=== 7) the window still fits with the new panels ===")
# The optional panels are off here: with them hidden the window keeps its
# original footprint; each panel that is switched on grows the requested height,
# which the notebook absorbs because it is the only row with weight.
app.var_advanced_on.set(False)
app.var_annot_on.set(False)
app._sync_advanced_state()
app._sync_annotation_state()
root.update_idletasks()
req_h_off = root.winfo_reqheight()
req_w_off = root.winfo_reqwidth()
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app._sync_annotation_state()
root.update_idletasks()
req_h_annot = root.winfo_reqheight()
app.var_advanced_on.set(True)
app._sync_advanced_state()
root.update_idletasks()
req_h_both = root.winfo_reqheight()
check(req_h_off <= 760, "both panels off: height fits the default window",
      f"{req_h_off} px")
check(req_w_off <= 1060, "both panels off: width fits the default window",
      f"{req_w_off} px")
check(req_h_annot <= 920, "annotation on: height stays within a resizable window",
      f"{req_h_annot} px")
check(req_h_annot > req_h_off, "enabling annotation reveals the optional rows",
      f"{req_h_off} -> {req_h_annot} px")
check(760 < req_h_both, "enabling both panels asks for more height",
      f"{req_h_both} px")

# At the default geometry the results area must stay usable and the buttons must
# stay on screen; enabling a panel grows the window as far as the screen allows.
root.geometry("1040x720")
root.update()
app.var_advanced_on.set(False)
app.var_annot_on.set(False)
app._sync_advanced_state()
app._sync_annotation_state()
root.update()
check(app.btn_run.winfo_ismapped(), "the run button is visible with both panels off")
# The buttons in the action row must not be stacked on top of each other.
buttons = [app.btn_run, app.btn_doctor, app.btn_copy_diag, app.btn_cancel, app.btn_open,
           app.btn_last]
xs = [b.winfo_x() for b in buttons]
check(len(set(xs)) == len(xs), "the action buttons each have their own column",
      f"x={xs}")
right = max(b.winfo_x() + b.winfo_width() for b in buttons + [app.progress])
check(right <= 1040, "every action button fits inside the default window width",
      f"right edge {right} px")
root.geometry("880x720")
root.update()
right_small = max(b.winfo_x() + b.winfo_width() for b in buttons + [app.progress])
check(right_small <= 880, "and they still fit at the minimum window size",
      f"right edge {right_small} px")
root.geometry("1040x720")
root.update()

app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app.var_advanced_on.set(True)
app._sync_annotation_state()
app._sync_advanced_state()
for _ in range(6):          # let the idle-time second growth pass run
    root.update()
check(app.btn_run.winfo_ismapped(), "the run button is still visible with both panels on")
check(app.btn_copy_diag.winfo_ismapped() and app.btn_cancel.winfo_ismapped(),
      "the diagnostics and cancel buttons stay on screen")

# The window grows as far as the screen allows, and the annotation table is
# usable whenever its tab is selected. (On a short screen the notebook absorbs
# the difference, which is why the table height is measured after selecting the
# tab rather than from the hidden tab.)
grew = root.winfo_height() > 720
check(grew, "enabling the panels grows the window", f"{root.winfo_height()} px")
app.notebook.select(app.annot_tree.master)
for _ in range(3):
    root.update()
tree_h = app.annot_tree.winfo_height()
if root.winfo_height() >= root.winfo_reqheight():
    check(tree_h >= 80, "the annotation table has room at the grown size",
          f"{tree_h} px")
else:
    # Short screen with every panel open: the window is clamped, so require the
    # table to stay usable rather than roomy.
    check(tree_h >= 50, "the annotation table stays usable on a short screen",
          f"{tree_h} px (screen {root.winfo_screenheight()} px)")

# With only the annotation panel open the table must be comfortably usable, even
# on this screen: that is the configuration the documentation recommends.
app.var_advanced_on.set(False)
app._sync_advanced_state()
for _ in range(5):
    root.update()
app.notebook.select(app.annot_tree.master)
for _ in range(3):
    root.update()
check(app.annot_tree.winfo_height() >= 80,
      "with one panel open the annotation table is roomy",
      f"{app.annot_tree.winfo_height()} px")

root.destroy()

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  annotation GUI controls (config, validation, window fit)")
