"""PyInstaller runtime hook: make the shared installer modules importable.

install.exe and uninstall.exe are frozen with onedir, which puts the script in
a bundle under _internal/. They import nanoamp_common from beside the
executable, so the executable's own directory is prepended to sys.path before
the entry script runs.
"""

import os
import sys

_here = os.path.dirname(os.path.abspath(sys.executable))
if _here not in sys.path:
    sys.path.insert(0, _here)
