"""Assemble an allowlisted portable release for GitHub, without game content."""
from pathlib import Path
from importlib.metadata import version
import argparse,datetime,hashlib,json,os,platform,re,shutil,ssl,sys,tarfile,zipfile
import tkinter

ROOT=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'src'))
import engine

DOCS=('README.md','BUILD.md','TECHNICAL_NOTES.md','PERFORMANCE_NOTES.md','CHANGELOG.md',
      'LICENSE.txt','THIRD_PARTY_NOTICES.md','RELEASE_VALIDATION.md','GITHUB_RELEASES.md','DISCLAIMER.md','EMULATOR_PATCH.md','DLC.md','NUP.md')
SOURCE=('Packager.spec','app.ico','requirements-build.txt','package_release.py','frozen_smoke.py',
        'test_engine.py','test_ui.py','test_artwork.py','test_performance_safety.py','test_nsp.py','test_compatibility.py',
        'test_emulator_patch.py','test_dlc.py','test_file_drops.py','test_nup.py','test_nup_ui.py','test_nup_optimization.py','test_nup_polish.py','frozen_nup_smoke.py','native/container_probe.c','native/build_probe.py','native/build_patterns.py','native/check_emulator_startup.py','.gitignore')

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


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',type=Path,default=ROOT/'release')
    linux=sys.platform.startswith('linux')
    binary='NSP-Box'+('' if linux else '.exe')
    parser.add_argument('--executable',type=Path,default=ROOT/'dist'/binary)
    args=parser.parse_args()
    if not re.fullmatch(r'\d+\.\d+\.\d+',engine.VERSION):raise ValueError('Invalid release version')
    tag='v'+engine.VERSION
    if os.environ.get('GITHUB_REF_TYPE')=='tag' and os.environ.get('GITHUB_REF_NAME')!=tag:
        raise ValueError('Git tag must match engine.VERSION: '+tag)
    files=source_files();out=args.output_dir.resolve();out.mkdir(parents=True,exist_ok=True)
    target=('Linux-'+{'x86_64':'x64','aarch64':'arm64'}.get(platform.machine(),platform.machine())) if linux else 'Windows-x64'
    name='NSP-Box-'+tag+'-'+target;release=out/name
    release.mkdir()  # Refuse to overwrite an existing assembled release.
    shutil.copy2(args.executable,release/binary)
    # Source and icon masters have their own ZIP. The portable download only
    # carries runtime, user documentation and required third-party notices.
    for path in files:
        relative=path.relative_to(ROOT)
        if relative.parts[0]!='licenses' and relative.as_posix() not in DOCS:continue
        dest=release/relative
        dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(path,dest)
    (release/'compatibility').mkdir()
    (release/'compatibility/plaintext-repack.keys').write_text(engine.placeholder_keys(),encoding='utf-8')
    info={'app_name':'NSP Box','app_version':engine.VERSION,'build_date':datetime.datetime.now(datetime.timezone.utc).isoformat(),
          'platform':target.replace('-',' '),'python':platform.python_version(),'pillow':version('Pillow'),
          'pyinstaller':version('PyInstaller'),'pyinstaller_hooks':version('pyinstaller-hooks-contrib'),
          'tcl':tkinter.Tcl().eval('info patchlevel'),'openssl':ssl.OPENSSL_VERSION,
          'source_commit':os.environ.get('GITHUB_SHA'),'code_license':'MIT','ai_assisted':True,'signed':False,
          'zstandard':version('zstandard'),
          'executable_sha256':hashlib.sha256((release/binary).read_bytes()).hexdigest()}
    (release/'BUILD_INFO.json').write_text(json.dumps(info,indent=2),encoding='utf-8')
    manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.relative_to(release).as_posix()+'\n'
                     for p in sorted(release.rglob('*')) if p.is_file())
    (release/'SHA256SUMS.txt').write_text(manifest,encoding='utf-8')
    portable=out/(name+('.tar.gz' if linux else '.zip'));source=out/('NSP-Box-'+tag+'-source.zip')
    if linux:
        with tarfile.open(portable,'x:gz') as archive:archive.add(release,arcname=name)
        with tarfile.open(portable,'r:gz') as archive:
            for member in archive.getmembers():
                if member.isfile():
                    with archive.extractfile(member) as stream:
                        if hashlib.sha256(stream.read()).digest()!=hashlib.sha256((release/Path(member.name).relative_to(name)).read_bytes()).digest():
                            raise ValueError('Archive integrity failed: '+member.name)
    else:
        with zipfile.ZipFile(portable,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
            for p in sorted(release.rglob('*')):
                if p.is_file():archive.write(p,Path(name)/p.relative_to(release))
    with zipfile.ZipFile(source,'x',zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for p in files:archive.write(p,Path('nsp-box-'+tag)/p.relative_to(ROOT))
    for p in (portable,source):
        if p.suffix!='.zip':continue
        with zipfile.ZipFile(p) as archive:
            if archive.testzip() is not None:raise ValueError('Archive integrity failed: '+p.name)
    sums=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+p.name+'\n' for p in (portable,source))
    (out/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    (out/'RELEASE_NOTES.md').write_text(notes(),encoding='utf-8')
    print(json.dumps({'version':engine.VERSION,'portable':portable.name,'source':source.name}))

if __name__=='__main__':main()
