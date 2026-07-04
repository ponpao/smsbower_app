# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the TRAVKOD PyQt6 desktop app.
# Build:  pip install pyinstaller && pyinstaller travkod.spec
# Output: dist/TRAVKOD (onedir) — bundles Python, PyQt6 and the DSP stack.

from PyInstaller.utils.hooks import collect_submodules

hidden = (
    collect_submodules('scipy')
    + collect_submodules('soundfile')
    + collect_submodules('pyloudnorm')
    + ['numpy']
)

a = Analysis(
    ['run_app.py'],
    pathex=['python'],
    binaries=[],
    datas=[('python/travkod', 'travkod'), ('python/travkod_app', 'travkod_app'),
           ('resources/fonts', 'resources/fonts')],
    hiddenimports=hidden,
    hookspath=[],
    excludes=['tkinter', 'PySide6', 'PyQt5'],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name='TRAVKOD',
    console=False,
    icon='resources/icon.ico' if __import__('os').path.exists('resources/icon.ico') else None,
)
coll = COLLECT(exe, a.binaries, a.datas, name='TRAVKOD')
