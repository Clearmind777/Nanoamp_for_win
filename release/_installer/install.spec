# PyInstaller spec for the nanoamp installer.
#
# Build:
#   python release\_installer\build_installer_exe.py
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
    hiddenimports=["install_nanoamp"],
    hookspath=[],
    runtime_hooks=[],
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
