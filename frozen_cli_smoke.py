"""Exercise the frozen `nspbox` command line with synthetic content on any platform."""
from pathlib import Path
import argparse,json,os,struct,subprocess,sys,tempfile

ROOT=Path(__file__).resolve().parent

def main():
    default='dist/nspbox.exe' if sys.platform=='win32' else 'dist/nspbox'
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--executable',type=Path,default=ROOT/default)
    exe=parser.parse_args().executable.resolve()
    scratch=ROOT/'test-work';scratch.mkdir(exist_ok=True)
    env=dict(os.environ);env.pop('DISPLAY',None);env.pop('WAYLAND_DISPLAY',None)  # Must not need a desktop.
    def run(*argv,expect=0):
        result=subprocess.run([str(exe),*map(str,argv)],capture_output=True,text=True,encoding='utf-8',timeout=120,env=env)
        assert result.returncode==expect,(argv,result.returncode,result.stdout,result.stderr)
        return result
    def run_json(*argv):
        return json.loads(run(*argv,'--json','-q').stdout)
    with tempfile.TemporaryDirectory(prefix='frozen-cli-',dir=scratch) as tmp:
        root=Path(tmp);game=root/'My Game';(game/'exefs').mkdir(parents=True);(game/'romfs'/'data').mkdir(parents=True)
        npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80);npdm[0x80:0x84]=b'ACI0'
        struct.pack_into('<Q',npdm,0x90,0x0400111122220000)
        (game/'exefs/main.npdm').write_bytes(npdm);(game/'exefs/main').write_bytes(b'NSO0'+bytes(256))
        (game/'romfs/data/content.bin').write_bytes(bytes(range(256))*4096)
        (game/'romfs/.DS_Store').write_bytes(b'\x00\x00\x00\x01Bud1'+bytes(32))
        assert 'NSP Box' in run('--version').stdout
        assert 'build' in run('--help').stdout
        scan=run_json('scan',game);assert scan['snapshots'][0]['title_id']=='0400111122220000',scan
        built=run_json('build',game,'-o',root/'Out.nsp','--no-package-folder')
        assert built['verified'] and built['ignored_os_metadata']==['romfs/.DS_Store'],built
        assert 'already exists' in run('build',game,'-o',root/'Out.nsp','--no-package-folder','-q',expect=1).stderr
        folder=run_json('build',game,'-o',root/'Pkg'/'Game.nsp')
        assert Path(folder['output']).parent.name=='Game' and (Path(folder['output']).parent/'main.npdm').is_file()
        dlc=root/'dlc'/'0400111122221001'/'0'/'romfs';dlc.mkdir(parents=True);(dlc/'d.bin').write_bytes(b'dlc'*1000)
        assert run_json('scan',dlc,'--dlc')['snapshots'][0]['title_id']=='0400111122221001'
        assert run_json('dlc',dlc,'-o',root/'DLC.nsp')['verified']
        packed=run_json('nup','pack',game,'--preset','Fast');nup=Path(packed['output'])
        assert nup.name=='My Game.nup' and nup.is_file(),packed
        assert run_json('nup','verify',nup)['verified']
        assert run_json('nup','to-nsp',nup,'-o',root/'Back.nsp')['verified']
        run_json('nup','extract',nup,'-o',root/'Extracted')
        assert (root/'Extracted/base/romfs/data/content.bin').read_bytes()==(game/'romfs/data/content.bin').read_bytes()
        assert run_json('nup','from-nsp',root/'Back.nsp','-o',root/'Again.nup')['output'].endswith('Again.nup')
        assert run('scan',root/'missing',expect=1).stderr.startswith('error:')
        # The original single-command interface still works from the CLI binary.
        legacy=subprocess.run([str(exe),'--package',str(game),'--output',str(root/'Legacy.nsp'),'--no-package-folder'],
                              capture_output=True,text=True,timeout=120,env=env)
        assert legacy.returncode==0 and json.loads(legacy.stdout)['verified'],legacy.stderr
    print(json.dumps({'frozen_cli_smoke':'passed','executable':exe.name}))
    return 0

if __name__=='__main__':sys.exit(main())
