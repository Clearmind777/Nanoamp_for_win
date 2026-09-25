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
    ANNOTATION_CUSTOM, ANNOTATION_OFFLINE, ANNOTATION_ONLINE, TRANSCRIPT_AUTO,
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

print("\n=== 7) the window still fits with the new group ===")
root.update_idletasks()
# With annotation off the optional rows are hidden, so the window keeps its
# original footprint; enabling it grows the requested height, which the
# notebook absorbs because it is the only row with weight.
app.var_annot_on.set(False)
app._sync_annotation_state()
root.update_idletasks()
req_h_off = root.winfo_reqheight()
req_w_off = root.winfo_reqwidth()
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app._sync_annotation_state()
root.update_idletasks()
req_h_on = root.winfo_reqheight()
check(req_h_off <= 760, "annotation off: height fits the default window",
      f"{req_h_off} px")
check(req_w_off <= 1060, "annotation off: width fits the default window",
      f"{req_w_off} px")
check(req_h_on <= 920, "annotation on: height stays within a resizable window",
      f"{req_h_on} px")
check(req_h_on > req_h_off, "enabling annotation reveals the optional rows",
      f"{req_h_off} -> {req_h_on} px")

# At the default geometry the results area must stay usable and the buttons
# must stay on screen; enabling annotation grows the window when needed.
root.geometry("1040x720")
root.update()
app.var_annot_on.set(False)
app._sync_annotation_state()
root.update()
check(app.btn_run.winfo_ismapped(), "the run button is visible with annotation off")
app.var_annot_on.set(True)
app.var_annot_source.set(ANNOTATION_OFFLINE)
app._sync_annotation_state()
for _ in range(4):          # let the idle-time second growth pass run
    root.update()
check(app.btn_run.winfo_ismapped(), "the run button is still visible with annotation on")

# The window grows as far as the screen allows, and the annotation table is
# usable whenever its tab is selected. (On a short screen the notebook absorbs
# the difference, which is why the table height is measured after selecting the
# tab rather than from the hidden tab.)
grew = root.winfo_height() > 720
check(grew, "enabling annotation grows the window", f"{root.winfo_height()} px")
app.notebook.select(app.annot_tree.master)
for _ in range(3):
    root.update()
tree_h = app.annot_tree.winfo_height()
if root.winfo_height() >= root.winfo_reqheight():
    check(tree_h >= 80, "the annotation table has room at the grown size",
          f"{tree_h} px")
else:
    # short screen: the window is clamped, so require the table to stay usable
    check(tree_h >= 60, "the annotation table stays usable on a short screen",
          f"{tree_h} px (screen {root.winfo_screenheight()} px)")

root.destroy()

print()
if failures:
    print(f"FAIL  {len(failures)} check(s) failed:")
    for f in failures:
        print("   -", f)
    raise SystemExit(1)
print("PASS  annotation GUI controls (config, validation, window fit)")
