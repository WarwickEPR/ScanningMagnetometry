# -*- mode: python ; coding: utf-8 -*-

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata


PROJECT_ROOT = os.path.abspath(os.path.join(os.getcwd(), ".."))
MAIN_SCRIPT = os.path.join(PROJECT_ROOT, "main.py")
ICON_PATH = os.path.join(PROJECT_ROOT, "software_icon.ico")

# Bundle all runtime configs so settings/default files are available in the executable.
datas = [
    (os.path.join(PROJECT_ROOT, "configs"), "configs"),
]
datas += collect_data_files("pyvisa")
datas += collect_data_files("pyvisa_py")
datas += copy_metadata("PyVISA")
datas += copy_metadata("PyVISA-py")

hiddenimports = []
hiddenimports += collect_submodules("pyqtgraph")
hiddenimports += collect_submodules("pyvisa")
hiddenimports += collect_submodules("pyvisa_py")
hiddenimports += collect_submodules("scipy.ndimage")
hiddenimports += collect_submodules("serial.tools")
hiddenimports += collect_submodules("zhinst")

a = Analysis(
    [MAIN_SCRIPT],
    pathex=[PROJECT_ROOT],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='ScanningMagnetometry',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=[ICON_PATH] if os.path.exists(ICON_PATH) else None,
)
