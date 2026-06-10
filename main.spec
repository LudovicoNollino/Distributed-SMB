# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for the Distributed SMB game client.
# Build with: pyinstaller main.spec
# Produces a single-file executable (smb-game / smb-game.exe).

import os

block_cipher = None

ROOT = os.path.abspath(SPECPATH)
SRC = os.path.join(ROOT, "src")
ASSETS = os.path.join(SRC, "distributed_smb", "assets")

# The lobby/game-event servers (uvicorn + FastAPI) are only run inside Docker
# containers, but main.py imports their modules for typing, so PyInstaller
# needs to resolve their lazily-loaded protocol implementations too.
hidden_imports = [
    "uvicorn.logging",
    "uvicorn.loops",
    "uvicorn.loops.auto",
    "uvicorn.protocols",
    "uvicorn.protocols.http",
    "uvicorn.protocols.http.auto",
    "uvicorn.protocols.websockets",
    "uvicorn.protocols.websockets.auto",
    "uvicorn.lifespan",
    "uvicorn.lifespan.on",
    "fastapi",
    "websockets",
    "httpx",
]

a = Analysis(
    [os.path.join(SRC, "distributed_smb", "main.py")],
    pathex=[SRC],
    binaries=[],
    datas=[
        (ASSETS, os.path.join("distributed_smb", "assets")),
    ],
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    cipher=block_cipher,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="smb-game",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon=os.path.join(ASSETS, "icon.ico"),  # add an .ico and uncomment for Windows branding
)
