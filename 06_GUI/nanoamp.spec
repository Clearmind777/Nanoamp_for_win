# PyInstaller spec for the nanoamp GUI.
#
# Build:
#   pyinstaller 06_GUI\nanoamp.spec --noconfirm
# or simply:
#   python 06_GUI\build_exe.py
#
# Output: 06_GUI\dist\nanoamp.exe  (windowed, no console)
#
# The result is a self-contained GUI shell. It still needs R + the nanoamp
# package at runtime, because the analysis lives in R; see README.md.

from pathlib import Path

# __file__ is not defined while PyInstaller executes a spec, but SPECPATH is.
PROJECT_DIR = Path(SPECPATH).resolve()

a = Analysis(
    [str(PROJECT_DIR / "run_gui.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=["nanoamp_gui", "nanoamp_gui.app", "nanoamp_gui.r_runner"],
    hookspath=[],
    runtime_hooks=[],
    # Keep the bundle lean: stdlib + tkinter only.
    excludes=[
        "numpy", "pandas", "scipy", "matplotlib", "PIL",
        "pytest", "setuptools", "pip", "sqlite3", "unittest",
    ],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name="nanoamp",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed app: no console window
    disable_windowed_traceback=False,
    icon=None,
    onefile=True,
)
