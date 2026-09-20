"""Entry point for the nanoamp GUI.

Run it directly:

    python 06_GUI\\run_gui.py

or, once frozen, double-click ``06_GUI\\dist\\nanoamp.exe``.
"""

from __future__ import annotations

import sys
import traceback
from pathlib import Path

# Allow running this file directly from a checkout, and from a PyInstaller
# bundle whose sys.path does not contain the 06_GUI directory.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))


def _show_fatal(message: str) -> None:
    """Report a startup failure in a GUI dialog, falling back to the console."""
    try:
        import tkinter as tk
        from tkinter import messagebox

        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("nanoamp - 启动失败", message)
        root.destroy()
    except Exception:
        print(message, file=sys.stderr)


def main() -> int:
    try:
        from nanoamp_gui.app import main as gui_main
    except Exception:
        _show_fatal("加载界面代码失败：\n\n" + traceback.format_exc())
        return 1
    try:
        return gui_main()
    except Exception:
        _show_fatal("界面运行出错：\n\n" + traceback.format_exc())
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
