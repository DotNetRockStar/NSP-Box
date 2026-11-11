"""NSP container, common-pipeline efficiency and failure regression tests."""
from pathlib import Path
from collections import Counter
from unittest.mock import patch
import json,mmap,struct,sys,tempfile,threading,unittest
sys.path.insert(0,str(Path(__file__).parent/'src'))
import engine,verify_format as reader
from cli import package_cli as cli
from PIL import Image

class NspTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='nsp-',dir=scratch);self.root=Path(self.tmp.name)
        self.game=self.root/'Example Game'
        (self.game/'exefs').mkdir(parents=True);(self.game/'romfs'/'日本語').mkdir(parents=True)
        npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80)
        npdm[0x80:0x84]=b'ACI0';struct.pack_into('<Q',npdm,0x90,0x0400111122220000)
        (self.game/'exefs/main.npdm').write_bytes(npdm);(self.game/'exefs/main').write_bytes(b'NSO0'+bytes(512))
        (self.game/'romfs'/'日本語/data.bin').write_bytes(bytes(range(256))*1000)
        (self.game/'romfs/empty').write_bytes(b'')
        self.snapshot=engine.find_snapshots(self.game)[0][0];self.output=self.root/'Game.nsp'
        self.art=self.root/'art.webp';Image.new('RGB',(400,200),'#3388ee').save(self.art)
    def tearDown(self):self.tmp.cleanup()
    def build(self,**kw):return engine.build(self.snapshot,self.output,'Example 日本語','1.0',self.art,**kw)
    def test_nsp_round_trip_metadata_art_and_standalone_readback(self):
        report=self.build()
        self.assertEqual(report['output_format'],'NSP');self.assertTrue(report['verified'])
        self.assertEqual(report['source_file_count'],4)
        self.assertFalse(self.output.with_suffix('.nsp.report.json').exists())
        with self.output.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as mm:
            contents=reader.partition(reader.Region(mm));self.assertEqual(len(contents),3)
            self.assertEqual({b[0x205] for b in contents.values()},{0,1,2})
            self.assertTrue(all(b[0x204]==0 for b in contents.values()))
            control=next(reader.nca_sections(b) for b in contents.values() if b[0x205]==2)
            files=reader.romfs_files(control[2][0][1])
            self.assertEqual(bytes(files['icon_AmericanEnglish.dat']),engine.artwork_bytes(self.art))
            nacp=bytes(files['control.nacp'])
            self.assertEqual(nacp[:0x200].split(b'\0')[0].decode(),'Example 日本語')
            self.assertEqual(nacp[0x3060:0x3070].split(b'\0')[0],b'1.0')
        checked=engine.verify_image(self.output,self.snapshot,engine.source_inventory(self.snapshot.root),lambda *a:None,None)
        self.assertEqual(len(checked),4)
    def test_nsp_streaming_has_bounded_reads_and_no_intermediate_container(self):
        inputs=set(engine.source_inventory(self.snapshot.root));original=Path.open
        reads=Counter();created=[]
        def tracked(path,*args,**kw):
            mode=args[0] if args else kw.get('mode','r')
            if path in inputs and 'r' in mode:reads[path]+=1
            if 'x' in mode or 'w' in mode:created.append(path)
            return original(path,*args,**kw)
        with patch.object(Path,'open',tracked):self.build()
        self.assertEqual(set(reads),inputs)
        self.assertTrue(all(n<=4 for n in reads.values()),reads)
        self.assertFalse(any(p.suffix.lower() in ('.xci','.nca') for p in created))
    def test_nsp_cancel_cleans_partial(self):
        event=threading.Event()
        def notify(stage,value):
            if stage=='Writing NSP':event.set()
        with self.assertRaises(InterruptedError):self.build(notify=notify,cancel=event)
        self.assertFalse(self.output.exists());self.assertFalse(list(self.root.glob('*.partial')))
    def test_nsp_corruption_rejected(self):
        def notify(stage,value):
            if stage=='Verifying container integrity':
                partial=next(self.root.glob('*.partial'))
                with partial.open('r+b') as f:
                    f.seek(-1,2);b=f.read(1);f.seek(-1,2);f.write(bytes([b[0]^1]))
        with self.assertRaises(AssertionError):self.build(notify=notify)
        self.assertFalse(self.output.exists());self.assertFalse(list(self.root.glob('*.partial')))
    def test_nsp_existing_output_and_format_mismatch(self):
        self.output.write_bytes(b'original')
        with self.assertRaises(FileExistsError):self.build()
        self.assertEqual(self.output.read_bytes(),b'original')
        with self.assertRaisesRegex(ValueError,'NSP output only'):self.build(output_format='xci')
        with self.assertRaisesRegex(ValueError,'NSP output only'):self.build(output_format='zip')
    def test_cli_infers_nsp_and_accepts_explicit_format(self):
        for explicit in (False,True):
            output=self.root/('CLI-'+str(explicit)+'.nsp')
            args=['--package',str(self.game),'--output',str(output)]
            if explicit:args+=['--format','nsp','--skip-verification']
            result=cli(args)
            self.assertEqual(result['output_format'],'NSP');self.assertEqual(result['verified'],not explicit)

    def test_nsp_keeps_exact_switch2_companion(self):
        original=(self.game/'exefs/main.npdm').read_bytes()
        for kind in ('nsp',):
            out=self.root/('Companion.'+kind)
            report=engine.build(self.snapshot,out,'Example','1',package_folder=True)
            actual=out.parent/out.stem/out.name
            self.assertEqual(Path(report['output']),actual)
            self.assertEqual((actual.parent/'main.npdm').read_bytes(),original)
            self.assertTrue(actual.with_suffix('.'+kind+'.report.json').is_file())
            self.assertEqual(report['switch2_companion']['file'],'main.npdm')

    def test_companion_conflict_is_refused_without_overwrite(self):
        companion=self.root/self.output.stem/'main.npdm';companion.parent.mkdir();companion.write_bytes(b'existing metadata')
        with self.assertRaisesRegex(ValueError,'separate folder'):self.build(package_folder=True)
        self.assertEqual(companion.read_bytes(),b'existing metadata');self.assertFalse(self.output.exists())

    def test_cancellation_does_not_leave_companion(self):
        event=threading.Event()
        def notify(stage,value):
            if stage=='Writing NSP':event.set()
        with self.assertRaises(InterruptedError):self.build(notify=notify,cancel=event,package_folder=True)
        self.assertFalse((self.root/self.output.stem/'main.npdm').exists())

    def test_companion_created_during_build_is_preserved(self):
        companion=self.root/self.output.stem/'main.npdm'
        def notify(stage,value):
            if stage=='Verifying container integrity':companion.write_bytes(b'external metadata')
        with self.assertRaisesRegex(ValueError,'changed during packaging'):self.build(notify=notify,package_folder=True)
        self.assertEqual(companion.read_bytes(),b'external metadata');self.assertFalse(self.output.exists())
        self.assertFalse(list(self.root.glob('*.partial')))

    def test_default_outputs_only_game_file_with_either_verification_setting(self):
        for kind in ('nsp',):
            for verified in (True,False):
                folder=self.root/(kind+str(verified));folder.mkdir()
                out=folder/('Only.'+kind)
                report=engine.build(self.snapshot,out,'Example','1',verify=verified)
                self.assertEqual(list(folder.iterdir()),[out])
                self.assertFalse(report['package_folder']);self.assertIsNone(report['switch2_companion'])
                self.assertEqual(report['verified'],verified)

    def test_cli_package_folder_default_and_single_file_override(self):
        out=self.root/'CLI folder.nsp'
        report=cli(['--package',str(self.game),'--output',str(out)])
        actual=out.parent/out.stem/out.name
        self.assertTrue(actual.is_file());self.assertFalse(out.exists())
        self.assertEqual(Path(report['output']),actual);self.assertTrue(report['package_folder'])
        self.assertTrue(actual.with_suffix('.nsp.report.json').is_file())
        bare=self.root/'Single CLI.nsp'
        result=cli(['--package',str(self.game),'--output',str(bare),'--no-package-folder'])
        self.assertTrue(bare.is_file());self.assertFalse(result['package_folder'])
        self.assertFalse(bare.with_suffix('.nsp.report.json').exists())

if __name__=='__main__':unittest.main(verbosity=2)
