# -*- mode: python ; coding: utf-8 -*-
# PyInstaller Build Specification for Valorant Voice AI Companion
# Targets: Windows 10/11 x64 standalone executable

import sys
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect custom assets, templates, web files and integrated driver installer
datas = [
    ('config.yaml', '.'),
    ('web_control/templates', 'web_control/templates'),
    ('web_control/static', 'web_control/static'),
    ('drivers/vbcable', 'drivers/vbcable'),
]

# Collect customtkinter and other dynamic package assets
datas += collect_data_files('customtkinter')
datas += collect_data_files('qrcode')

# Comprehensive hidden imports
hiddenimports = [
    'customtkinter',
    'PyQt6',
    'PyQt6.QtCore',
    'PyQt6.QtGui',
    'PyQt6.QtWidgets',
    'pystray',
    'PIL',
    'PIL.Image',
    'PIL.ImageDraw',
    'sounddevice',
    'pyaudiowpatch',
    'scipy',
    'scipy.signal',
    'fastapi',
    'uvicorn',
    'uvicorn.loops',
    'uvicorn.loops.auto',
    'uvicorn.protocols',
    'uvicorn.protocols.http',
    'uvicorn.protocols.http.auto',
    'uvicorn.protocols.websockets',
    'uvicorn.protocols.websockets.auto',
    'uvicorn.lifespan',
    'uvicorn.lifespan.on',
    'websockets',
    'jinja2',
    'yaml',
    'psutil',
    'pyautogui',
    'pyperclip',
    'google.genai',
    'google.genai.types',
    'openwakeword',
    'onnxruntime',
]

# Windows-specific system imports
if sys.platform == 'win32' or True:
    hiddenimports += [
        'win32api',
        'win32con',
        'win32gui',
        'win32process',
        'comtypes',
        'pycaw',
        'pycaw.pycaw',
        'pydirectinput',
        'dxcam',
    ]

hiddenimports += collect_submodules('uvicorn')
hiddenimports += collect_submodules('google.genai')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter.test',
        'unittest',
        'test',
        'matplotlib',
        'IPython',
        'jupyter',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='ValorantVoiceAI',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=None,
)
