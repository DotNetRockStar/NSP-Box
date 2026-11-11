"""Assemble an allowlisted portable release for GitHub, without game content."""
from pathlib import Path
from importlib.metadata import version
import argparse,datetime,hashlib,json,os,platform,re,shutil,ssl,subprocess,sys,tarfile,zipfile
import tkinter

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import engine

DOCS=('README.md','BUILD.md','TECHNICAL_NOTES.md','PERFORMANCE_NOTES.md','CHANGELOG.md',
      'LICENSE.txt','THIRD_PARTY_NOTICES.md','RELEASE_VALIDATION.md','GITHUB_RELEASES.md','DISCLAIMER.md','EMULATOR_PATCH.md','DLC.md','NUP.md','CLI.md')
SOURCE=('Packager.spec','app.ico','requirements-build.txt','package_release.py','frozen_smoke.py',
        'test_engine.py','test_ui.py','test_artwork.py','test_performance_safety.py','test_nsp.py','test_compatibility.py',
        'test_emulator_patch.py','test_dlc.py','test_file_drops.py','test_nup.py','test_nup_ui.py','test_nup_optimization.py','test_nup_polish.py','frozen_nup_smoke.py','frozen_cli_smoke.py','test_portable.py','native/container_probe.c','native/build_probe.py','native/build_patterns.py','native/check_emulator_startup.py','packaging/macos/entitlements.plist','.gitignore')

def source_files():
    paths=[ROOT/p for p in DOCS+SOURCE]
    paths+=sorted((ROOT/'src').glob('*.py'))
    paths+=sorted(p for p in (ROOT/'src'/'assets').rglob('*') if p.is_file())
    paths+=sorted(p for p in (ROOT/'licenses').rglob('*') if p.is_file())
    paths+=sorted((ROOT/'.github/workflows').glob('*.yml'))
    for path in paths:
        if not path.is_file():raise FileNotFoundError(path.name)
        if path.is_symlink():raise ValueError('Linked release input: '+path.name)
    return paths

def notes():
    text=(ROOT/'CHANGELOG.md').read_text(encoding='utf-8')
    match=re.search(r'^## '+re.escape(engine.VERSION)+r'[^\n]*\n(.*?)(?=^## |\Z)',text,re.M|re.S)
    if not match:raise ValueError('Add changelog notes for '+engine.VERSION)
    heading=match.group(0).splitlines()[0].removeprefix('## ').strip()
    return ('# NSP Box '+heading+'\n\n'+match.group(1).strip()+
            '\n\nPiracy is not supported. This independent project is not affiliated with Nintendo. '
            'Nintendo and other rights holders retain ownership of their content and marks. '
            'No games, firmware or retail keys are included. See DISCLAIMER.md.\n')


ARCH={'x86_64':'x64','amd64':'x64','aarch64':'arm64','arm64':'arm64'}

def platform_layout():
    """(release target, GUI artifact name, CLI binary name, GUI main executable inside the artifact)."""
    arch=ARCH.get(platform.machine().lower(),platform.machine())
    if sys.platform=='win32':return 'Windows-x64','NSP-Box.exe','nspbox.exe',Path('NSP-Box.exe')
    if sys.platform=='darwin':return 'macOS-'+arch,'NSP-Box.app','nspbox',Path('NSP-Box.app/Contents/MacOS/NSP-Box')
    return 'Linux-'+arch,'NSP-Box','nspbox',Path('NSP-Box')

def release_files(release):
    """Regular files in a release folder; symlinks inside a macOS bundle are listed once by target."""
    return [p for p in sorted(release.rglob('*')) if p.is_file() and not p.is_symlink()]

def main():
    target,gui_name,cli_name,gui_main=platform_layout()
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'release')
    parser.add_argument('--executable',type=Path,default=ROOT/'dist'/gui_name,help='GUI build (an .app folder on macOS).')
    parser.add_argument('--cli-executable',type=Path,default=ROOT/'dist'/cli_name,help='Console nspbox build.')
    parser.add_argument('--skip-source',action='store_true',help='Omit the source ZIP (built once, by the Windows job).')
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',engine.VERSION):raise ValueError('Invalid release version')
    tag='v'+engine.VERSION
    if os.environ.get('GITHUB_REF_TYPE')=='tag' and os.environ.get('GITHUB_REF_NAME')!=tag:
        raise ValueError('Git tag must match engine.VERSION: '+tag)
    files=source_files();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    name='NSP-Box-'+tag+'-'+target;release=out/name
    release.mkdir()  # Refuse to overwrite an existing assembled release.
    if args.executable.is_dir():shutil.copytree(args.executable,release/gui_name,symlinks=True)
    else:shutil.copy2(args.executable,release/gui_name)
    shutil.copy2(args.cli_executable,release/cli_name)
    # Source and icon masters have their own ZIP. The portable download only
    # carries runtime, user documentation and required third-party notices.
    for path in files:
        relative=path.relative_to(ROOT)
        if relative.parts[0]!='licenses' and relative.as_posix() not in DOCS:continue
        dest=release/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    (release/'compatibility').mkdir()
    (release/'compatibility/plaintext-repack.keys').write_text(engine.placeholder_keys(),encoding='utf-8')
    signed=bool(os.environ.get('NSPBOX_CODESIGN_IDENTITY')) if sys.platform=='darwin' else False
    info={'app_name':'NSP Box','app_version':engine.VERSION,'build_date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'platform':target.replace('-',' '),'python':platform.python_version(),'pillow':version('Pillow'),
          'pyinstaller':version('PyInstaller'),'pyinstaller_hooks':version('pyinstaller-hooks-contrib'),
          'tcl':tkinter.Tcl().eval('info patchlevel'),'openssl':ssl.OPENSSL_VERSION,
          'source_commit':os.environ.get('GITHUB_SHA'),'code_license':'MIT','ai_assisted':True,'signed':signed,
          'zstandard':version('zstandard'),
          'executable_sha256':hashlib.sha256((release/gui_main).read_bytes()).hexdigest(),
          'cli_executable_sha256':hashlib.sha256((release/cli_name).read_bytes()).hexdigest()}
    if sys.platform!='win32':info['tkinterdnd2']=version('tkinterdnd2')
    (release/'BUILD_INFO.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(release).as_posix()+'\n'
                     for p in release_files(release))
    (release/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8')
    linux=sys.platform.startswith('linux')
    portable=out/(name+('.tar.gz' if linux else '.zip'));source=out/('NSP-Box-'+tag+'-source.zip')
    if linux:
        # tar keeps the executable bits that a ZIP extracted on Linux would lose.
        with tarfile.open(portable,'x:gz') as archive:archive.add(release,arcname=name)
        with tarfile.open(portable,'r:gz') as archive:
            for member in archive.getmembers():
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        if hashlib.sha256(stream.read()).digest()!=hashlib.sha256((release/Path(member.name).relative_to(name)).read_bytes()).digest():
                            raise ValueError('Archive integrity failed: '+member.name)
    elif sys.platform=='darwin':
        # ditto keeps the bundle's symlinks, permissions and code signature intact
        # (Python's zipfile would flatten symlinks and break the signature).
        if portable.exists():raise FileExistsError(portable)
        subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(release),str(portable)],check=True)
        check=out/('.verify-'+name)
        subprocess.run(['ditto','-x','-k',str(portable),str(check)],check=True)
        try:
            for p in release_files(release):
                if hashlib.sha256(p.read_bytes()).digest()!=hashlib.sha256((check/name/p.relative_to(release)).read_bytes()).digest():
                    raise ValueError('Archive integrity failed: '+p.name)
            subprocess.run(['codesign','--verify','--deep','--strict',str(check/name/gui_name)],check=True)
        finally:shutil.rmtree(check)
    else:
        with zipfile.ZipFile(portable,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for p in release_files(release):archive.write(p,Path(name)/p.relative_to(release))
    outputs=[portable]
    if not args.skip_source:
        with zipfile.ZipFile(source,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for p in files:archive.write(p,Path('nsp-box-'+tag)/p.relative_to(ROOT))
        outputs.append(source)
    for p in outputs:
        if p.suffix!='.zip':continue
        with zipfile.ZipFile(p) as archive:
            if archive.testzip() is not None:raise ValueError('Archive integrity failed: '+p.name)
    sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in outputs)
    (out/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    (out/'RELEASE_NOTES.md').write_text(notes(),encoding='utf-8')
    print(json.dumps({'version':engine.VERSION,'portable':portable.name,'source':None if args.skip_source else source.name}))

if __name__=='__main__':main()
