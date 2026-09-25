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
import tkinter as tk
from pathlib import Path

HERE = Path(__file__).resolve().parent
GUI = HERE.parent
REPO = GUI.parent.parent
sys.path.insert(0, str(GUI))

from nanoamp_gui.app import (  # noqa: E402
    ANNOTATION_CUSTOM, ANNOTATION_OFFLINE, ANNOTATION_ONLINE, NanoampApp,
)

failures: list[str] = []


def check(ok: bool, what: str, extra: str = "") -> None:
    print(("   OK   " if ok else "   FAIL ") + what + (f"  -- {extra}" if extra else ""))
    if not ok:
        failures.append(what)


root = tk.Tk()
root.title("annotation gui check")
app = NanoampApp(root, REPO)
root.update_idletasks()

print("=== 1) default state ===")
check(not app.var_annot_on.get(), "annotation is off by default")
check(str(app.entry_cds_start.cget("state")) == "disabled",
      "the CDS form is disabled while annotation is off")

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
