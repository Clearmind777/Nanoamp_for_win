"""Launch the window pre-filled with a finished run, so the result views can be
inspected. Used for screenshots; not part of the shipped app."""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

import tkinter as tk  # noqa: E402
from tkinter import ttk  # noqa: E402

from nanoamp_gui.app import APP_TITLE, NanoampApp, find_repo_root, resource_base  # noqa: E402

root_dir = find_repo_root(resource_base())
sample = root_dir / "01_data" / "ln_test_data" / "TSM20260826" / "E4-3"
outdir = root_dir / "04_results" / "gui" / "E4-3"

root = tk.Tk()
root.title(APP_TITLE)
root.geometry("1040x720")
try:
    ttk.Style().theme_use("vista")
except tk.TclError:
    pass

app = NanoampApp(root, root_dir)
app.var_reads.set(str(sample / "reads.fastq"))
app.var_reference.set(str(sample / "reference.self.fa"))
app.var_outdir.set(str(outdir))
app.var_mode.set("A")

# Populate the result views exactly as a finished run would.
if (outdir / "haplotypes.tsv").is_file():
    app.last_outdir = outdir
    app._load_results(outdir)
    app.btn_open.configure(state="normal")
    n = len(app.tree.get_children())
    app.var_status.set(f"分析完成，输出目录：{outdir}（{n} 条单倍型）")
    kids = app.tree.get_children()
    if kids:
        app.tree.selection_set(kids[0])
        app.tree.focus(kids[0])
        app._on_select_haplotype(None)

root.after(4000, root.destroy)
root.mainloop()
print("result view populated and closed")
