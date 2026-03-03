# -*- mode: python ; coding: utf-8 -*-

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# Recolectar todos los sub-paquetes del proyecto
project_packages = [
    'audio', 'backends', 'ui', 'updater', 'utils'
]

datas = [('icon.png', '.')]
for pkg in project_packages:
    datas.append((pkg, pkg))

# Incluir icon.ico solo en Windows
if sys.platform == 'win32' and os.path.exists('icon.ico'):
    datas.append(('icon.ico', '.'))

# Recolectar datos de customtkinter y certifi (certificados SSL)
datas += collect_data_files('customtkinter')
datas += collect_data_files('certifi')

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=datas,
    hiddenimports=[
        # Sub-módulos explícitos
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
        # Dependencias externas
        'customtkinter',
        'PIL',
        'PIL.Image',
        'PIL.ImageTk',
        'PIL.ImageDraw',
        'PIL._tkinter_finder',
        'sounddevice',
        'numpy',
        'certifi',
        # pkg_resources / jaraco (necesarios para pyi_rth_pkgres)
        *collect_submodules('jaraco'),
        *collect_submodules('pkg_resources'),
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

# ─────────────────────────────────────────────────────────────
#  Windows → onefile (un solo .exe portátil)
#  Linux   → onedir  (carpeta, necesaria para empaquetar .deb)
# ─────────────────────────────────────────────────────────────
if sys.platform == 'win32':
    exe = EXE(
        pyz,
        a.scripts,
        a.binaries,   # incluir binaries dentro del exe
        a.datas,      # incluir datos dentro del exe
        [],
        name='micyn',
        debug=False,
        bootloader_ignore_signals=False,
        strip=False,
        upx=True,
        upx_exclude=[],
        console=False,
        disable_windowed_traceback=False,
        argv_emulation=False,
        target_arch=None,
        codesign_identity=None,
        entitlements_file=None,
        icon=['icon.ico'] if os.path.exists('icon.ico') else [],
    )
    # Sin COLLECT — todo va dentro del .exe
else:
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
        icon=[],
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
