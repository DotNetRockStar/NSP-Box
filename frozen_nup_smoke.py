"""Exercise every NUP operation using the frozen app and synthetic game data."""
from pathlib import Path
import argparse,json,subprocess,tempfile,struct,sys

def main():
    default={'win32':'dist/NSP-Box.exe','darwin':'dist/NSP-Box.app/Contents/MacOS/NSP-Box'}.get(sys.platform,'dist/NSP-Box')
    parser=argparse.ArgumentParser();parser.add_argument('--executable',type=Path,default=Path(default));args=parser.parse_args()
    executable=args.executable.resolve();scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='frozen-nup-',dir=scratch) as tmp:
        root=Path(tmp);game=root/'Game';(game/'exefs').mkdir(parents=True);(game/'romfs').mkdir()
        npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80);npdm[0x80:0x84]=b'ACI0';struct.pack_into('<Q',npdm,0x90,0x0400111122220000)
        (game/'exefs/main.npdm').write_bytes(npdm);(game/'exefs/main').write_bytes(b'NSO0'+bytes(256));(game/'romfs/synthetic.bin').write_bytes(bytes(10*1024*1024))
        def run(operation,source,output=None):
            report=root/(operation+'.json');cmd=[str(executable),'--nup-operation',operation,'--input',str(source),'--result-json',str(report)]
            if output:cmd+=['--output',str(output)]
            result=subprocess.run(cmd,capture_output=True,timeout=90)
            assert report.is_file(),(operation,result.returncode,result.stderr)
            info=json.loads(report.read_text(encoding='utf-8'));assert result.returncode==0,(operation,info)
            print(json.dumps({'frozen_nup':operation,'passed':True}));return info
        nup=root/'Game.nup';run('pack',game,nup);run('inspect',nup);run('verify',nup)
        extracted=root/'extracted';run('extract',nup,extracted)
        assert (extracted/'base/exefs/main.npdm').read_bytes()==bytes(npdm)
        nsp=root/'Game.nsp';run('nup-to-nsp',nup,nsp)
        run('nsp-to-nup',nsp,root/'Repacked.nup')
    return 0

if __name__=='__main__':sys.exit(main())
