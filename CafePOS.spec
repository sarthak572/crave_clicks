# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build definition for the Windows CafePOS distribution."""

from PyInstaller.utils.hooks import collect_submodules


hiddenimports = collect_submodules("app")

analysis = Analysis(
    ["app/main.py"],
    pathex=["."],
    binaries=[],
    datas=[("default_menu.json", ".")],
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(analysis.pure)
executable = EXE(
    pyz,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="CafePOS",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
)
distribution = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CafePOS",
)
