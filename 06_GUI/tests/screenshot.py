"""Capture a screenshot of the desktop so the rendered GUI can be inspected."""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from PIL import ImageGrab
except ImportError:
    print("Pillow not available", file=sys.stderr)
    raise SystemExit(2)

out = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("shot.png")
img = ImageGrab.grab()
img.save(out)
print(f"saved {out}  {img.size[0]}x{img.size[1]}")
