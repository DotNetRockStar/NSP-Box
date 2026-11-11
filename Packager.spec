# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller build for Windows, macOS and Linux.

dist/ after `python -m PyInstaller --noconfirm --clean Packager.spec`:
  Windows  NSP-Box.exe   windowed GUI (also accepts the legacy --package/--nup-operation flags)
           nspbox.exe    console command line
  macOS    NSP-Box.app   GUI application bundle
           nspbox        console command line
  Linux    NSP-Box       GUI
           nspbox        console command line

The command-line binary never loads Tk, so it also runs on headless machines.
"""
from pathlib import Path
import os, re, sys

project = Path(SPECPATH)
src = project/'src'
WINDOWS = sys.platform == 'win32'
MACOS = sys.platform == 'darwin'
VERSION = re.search(r"^VERSION\s*=\s*'([^']+)'", (src/'engine.py').read_text(encoding='utf-8'), re.M).group(1)
EXCLUDES = ['numpy', 'scipy', 'matplotlib', 'pandas', 'pytest']

def without_windows_runtime(binaries):
    # Windows 10/11 supplies the Universal CRT/API-set DLLs. Do not collect copies
    # accidentally discovered in unrelated PATH directories on the build machine.
    if not WINDOWS:
        return binaries
    return [item for item in binaries
            if not Path(item[0]).name.lower().startswith('api-ms-win-')
            and Path(item[0]).name.lower() != 'ucrtbase.dll']

def macos_icon():
    """Build the .icns from the reviewed 1254 px app artwork (Pillow writes ICNS)."""
    from PIL import Image
    target = Path(workpath)/'NSP-Box.icns'  # PyInstaller's --workpath (default build/Packager)
    target.parent.mkdir(parents=True, exist_ok=True)
    with Image.open(src/'assets'/'icons'/'app.png') as image:
        image.convert('RGBA').resize((1024, 1024), Image.Resampling.LANCZOS).save(target, format='ICNS')
    return str(target)

# --- GUI -------------------------------------------------------------------
# Windows drops use the native shell hook; macOS/Linux use tkdnd from the
# optional tkinterdnd2 package (its own PyInstaller hook bundles the library).
gui = Analysis([str(src/'app.py')], pathex=[str(src)], binaries=[],
               datas=[(str(src/'assets'), 'assets')],
               # PIL.ImageTk loads _tkinter_finder dynamically; Linux builds miss it otherwise.
               hiddenimports=[] if WINDOWS else ['tkinterdnd2', 'PIL._tkinter_finder'], hookspath=[], hooksconfig={},
               runtime_hooks=[], excludes=EXCLUDES + (['tkinterdnd2'] if WINDOWS else []),
               noarchive=False, optimize=0)
gui.binaries = without_windows_runtime(gui.binaries)
gui_pyz = PYZ(gui.pure)

if MACOS:
    # Onefile is unsuitable inside an .app bundle; use onedir + BUNDLE.
    gui_exe = EXE(gui_pyz, gui.scripts, [], exclude_binaries=True, name='NSP-Box',
                  debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
                  console=False, argv_emulation=False, target_arch=None,
                  codesign_identity=os.environ.get('NSPBOX_CODESIGN_IDENTITY') or None,
                  entitlements_file=os.environ.get('NSPBOX_ENTITLEMENTS') or None)
    gui_files = COLLECT(gui_exe, gui.binaries, gui.datas, strip=False, upx=False, name='NSP-Box')
    app = BUNDLE(gui_files, name='NSP-Box.app', icon=macos_icon(),
                 bundle_identifier='io.github.smarkyie.nsp-box', version=VERSION,
                 info_plist={
                     'CFBundleName': 'NSP Box',
                     'CFBundleDisplayName': 'NSP Box',
                     'CFBundleShortVersionString': VERSION,
                     'CFBundleVersion': VERSION,
                     'LSMinimumSystemVersion': '11.0',
                     'NSHighResolutionCapable': True,
                     'NSRequiresAquaSystemAppearance': False,
                     'LSApplicationCategoryType': 'public.app-category.utilities',
                     # Folders, packages and artwork dropped on the Dock icon
                     # arrive through ::tk::mac::OpenDocument (see app.py).
                     'CFBundleDocumentTypes': [{
                         'CFBundleTypeName': 'Game folder, package or artwork',
                         'CFBundleTypeRole': 'Viewer',
                         'LSHandlerRank': 'Alternate',
                         'LSItemContentTypes': ['public.folder', 'public.image', 'public.data'],
                     }],
                 })
else:
    gui_exe = EXE(gui_pyz, gui.scripts, gui.binaries, gui.datas, [], name='NSP-Box',
                  debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
                  console=False, disable_windowed_traceback=False,
                  icon=str(project/'app.ico') if WINDOWS and (project/'app.ico').exists() else None)

# --- Command line ----------------------------------------------------------
cli = Analysis([str(src/'cli.py')], pathex=[str(src)], binaries=[], datas=[],
               hiddenimports=[], hookspath=[], hooksconfig={}, runtime_hooks=[],
               excludes=EXCLUDES + ['tkinter', '_tkinter', 'tkinterdnd2', 'PIL.ImageTk'],
               noarchive=False, optimize=0)
cli.binaries = without_windows_runtime(cli.binaries)
cli_exe = EXE(PYZ(cli.pure), cli.scripts, cli.binaries, cli.datas, [], name='nspbox',
              debug=False, bootloader_ignore_signals=False, strip=False, upx=False,
              console=True, target_arch=None,
              codesign_identity=os.environ.get('NSPBOX_CODESIGN_IDENTITY') or None,
              entitlements_file=os.environ.get('NSPBOX_ENTITLEMENTS') or None,
              icon=str(project/'app.ico') if WINDOWS and (project/'app.ico').exists() else None)
