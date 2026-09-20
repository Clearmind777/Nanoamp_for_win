# PyInstaller spec for the nanoamp installer.
#
# Build:
#   python release\_installer\build_exe.py
#
# Output: release\install.exe
#
# onedir, windowed (no console). The ~250 MB offline payload is deliberately
# NOT bundled: it ships next to the executable, so the .exe stays ~10 MB and
# starts instantly instead of self-extracting on every run.

from pathlib import Path

PROJECT_DIR = Path(SPECPATH).resolve()

a = Analysis(
    [str(PROJECT_DIR / "install_nanoamp.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[],
    # nanoamp_common lives next to the executable at runtime; rthook_paths
    # puts that directory on sys.path, and it is listed here so PyInstaller
    # bundles it into the frozen app as well.
    hiddenimports=["install_nanoamp", "nanoamp_common"],
    hookspath=[],
    runtime_hooks=[str(PROJECT_DIR / "rthook_paths.py")],
    # Keep it small: stdlib + tkinter only. winreg is a stdlib module on
    # Windows and is imported lazily, so it is listed explicitly.
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
    name="install",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,          # windowed: a biologist should never see a console
    disable_windowed_traceback=False,
    icon=None,
    onefile=False,          # onedir: see the note above
)
