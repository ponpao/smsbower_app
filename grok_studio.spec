# PyInstaller spec for Grok Studio — equivalent to:
#   pyinstaller --onefile --windowed --icon assets/icons/grok_studio.ico \
#       --add-data "assets;assets" --name GrokStudio main.py
#
# Build with:  pyinstaller grok_studio.spec

a = Analysis(
    ["main.py"],
    pathex=[],
    binaries=[],
    datas=[("assets", "assets")],
    hiddenimports=[
        # keyring's Windows Credential Manager backend is loaded dynamically
        "keyring.backends.Windows",
        "win32ctypes.core",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GrokStudio",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,            # --windowed
    icon="assets/icons/grok_studio.ico",
)
