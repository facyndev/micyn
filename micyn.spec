# -*- mode: python ; coding: utf-8 -*-

import os

# Recolectar todos los sub-paquetes del proyecto como source trees
# para que PyInstaller los incluya correctamente
project_packages = [
    'audio', 'backends', 'ui', 'updater', 'utils'
]

datas = [('icon.png', '.')]
for pkg in project_packages:
    datas.append((pkg, pkg))

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Sub-módulos explícitos para que PyInstaller los empaquete
        'audio.buffer',
        'audio.callbacks',
        'audio.loop',
        'backends.base',
        'backends.linux',
        'backends.windows',
        'ui.main_window',
        'ui.manual',
        'ui.splash',
        'ui.vumeters',
        'updater.updater',
        'utils.devices',
        'utils.resources',
        # Dependencias externas que pueden no detectarse solas
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'sounddevice',
        'numpy',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    # Excluir el módulo local (ya no existe, pero por seguridad)
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='micyn',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['icon.png'],
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='micyn',
)
