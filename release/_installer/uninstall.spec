# PyInstaller spec for uninstall.exe.
#
# Build:
#   python release\_installer\build_exe.py uninstall
#
# Output: release\uninstall.exe
#
# Same shape as install.spec: onedir, windowed, no payload bundled. The
# uninstaller only needs to read config.ini and delete files, so nothing from
# _offline/ is required.

from pathlib import Path

PROJECT_DIR = Path(SPECPATH).resolve()

a = Analysis(
    [str(PROJECT_DIR / "uninstall_nanoamp.py")],
    pathex=[str(PROJECT_DIR)],
    binaries=[],
    datas=[],
    hiddenimports=["uninstall_nanoamp", "nanoamp_common"],
    hookspath=[],
    runtime_hooks=[str(PROJECT_DIR / "rthook_paths.py")],
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
    name="uninstall",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    icon=None,
    onefile=False,
)
