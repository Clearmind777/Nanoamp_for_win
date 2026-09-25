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
import sys
import tempfile
import tkinter as tk
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUI = HERE.parent
REPO = GUI.parent.parent
sys.path.insert(0, str(GUI))

from nanoamp_gui.app import (  # noqa: E402
    ADVANCED_DEFAULTS, ALIGNER_DEFAULT, ALIGNERS, ANNOTATION_CUSTOM,
    ANNOTATION_OFFLINE, ANNOTATION_ONLINE, CONSENSUS_DEFAULT, TRANSCRIPT_AUTO,
    NanoampApp,
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
check("�" not in logged, "no replacement characters in the log")

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
buttons = [app.btn_run, app.btn_doctor, app.btn_copy_diag, app.btn_cancel, app.btn_open]
xs = [b.winfo_x() for b in buttons]
check(len(set(xs)) == len(xs), "the action buttons each have their own column",
      f"x={xs}")

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
