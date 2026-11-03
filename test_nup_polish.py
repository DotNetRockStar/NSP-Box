"""Selection must exclude content before snapshot merging; overrides are metadata-only."""
from pathlib import Path
import itertools,struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).parent/'src'))
import nup_tools as nt,nup_format as nf
from test_nup import snapshot,TID

class NupPolishTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch);self.root=Path(self.tmp.name);self.bundle=self.root/'Bundle'
        snapshot(self.bundle/'base',{'base-only':b'base','shared':b'old'})
        snapshot(self.bundle/'updates/65536',{'update-only':b'update','shared':b'new'},1)
        dlc=self.bundle/f'dlc/{TID+0x1001:016X}/romfs';dlc.mkdir(parents=True);(dlc/'addon').write_bytes(b'dlc')
    def tearDown(self):self.tmp.cleanup()
    def test_all_kind_combinations_filter_before_snapshot(self):
        prepared=nt.prepare_folder(self.bundle)
        for mask in range(1,8):
            kinds={i for i in range(3) if mask&(1<<i)};out=self.root/f'{mask}.nup'
            nt.pack_folder(self.bundle,out,include_kinds=kinds,prepared=prepared)
            with nf.Archive(out) as a:
                a.verify();self.assertEqual(any(p.kind==2 for p in a.packages),2 in kinds)
                game=next((p for p in a.packages if p.kind==0),None)
                if kinds&{0,1}:
                    self.assertIsNotNone(game);self.assertEqual('romfs/base-only' in game.files,0 in kinds)
                    self.assertEqual('romfs/update-only' in game.files,1 in kinds)
                    shared=game.files['romfs/shared'].read_small();self.assertEqual(shared,b'new' if 1 in kinds else b'old')
                else:self.assertIsNone(game)
        with self.assertRaisesRegex(ValueError,'No matching'):nt.pack_folder(self.bundle,self.root/'empty.nup',include_kinds=set())
    def test_original_package_flags_and_custom_metadata(self):
        packages=nt.discover(self.bundle);update=next(p for p in packages if p.kind==1)
        out=self.root/'update.nup';nt.pack_folder(self.bundle,out,include_kinds={1},latest_snapshot=False)
        self.assertEqual(update.flags,0)
        with nf.Archive(out) as a:self.assertEqual(a.packages[0].kind,1);self.assertEqual(a.packages[0].flags,1)
        nacp=bytearray(0x4000);nacp[:4]=b'Base';struct.pack_into('<Q',nacp,0x3038,TID)
        base=packages[0];base.metadata.append((2,bytes(nacp)))
        result=nt.presentation(packages,'New title',b'new cover')
        self.assertNotEqual(dict(base.metadata).get(5),b'New title');self.assertEqual(dict(base.metadata)[2],bytes(nacp))
        for p in result:
            if p.kind in (0,1):self.assertEqual(dict(p.metadata)[5],b'New title');self.assertEqual(dict(p.metadata)[3],b'new cover')
            else:self.assertNotEqual(dict(p.metadata).get(5),b'New title')
        self.assertEqual(dict(result[0].metadata)[2][:9],b'New title')
    def test_nsp_export_uses_only_selected_records(self):
        nup=self.root/'all.nup';nt.pack_folder(self.bundle,nup,latest_snapshot=False)
        for kinds in ({0},{1},{2},{0,1,2}):
            dest=self.root/('export-'+''.join(map(str,sorted(kinds))))
            nt.nup_to_nsp(nup,dest,include_kinds=kinds)
            paths=list(dest.glob('*.nsp'));self.assertEqual(len(paths),int(bool(kinds&{0,1}))+int(2 in kinds))
            for path in paths:
                with nt.nsp_packages(path) as packages:
                    p=packages[0]
                    if p.kind==0:
                        self.assertEqual('romfs/base-only' in p.files,0 in kinds);self.assertEqual('romfs/update-only' in p.files,1 in kinds)
                    converted=self.root/(path.stem+'-'+dest.name+'.nup')
                    nt.nsp_to_nup(path,converted,include_kinds={p.kind})
                    with nf.Archive(converted) as a:self.assertEqual(a.packages[0].kind,p.kind)

    def test_title_cover_overrides_survive_existing_control_conversion(self):
        import io
        from PIL import Image
        from artwork import ArtworkSelection,artwork_bytes
        control=self.bundle/'base/data/control';control.mkdir(parents=True)
        nacp=bytearray(0x4000);nacp[:8]=b'Original';(control/'control.nacp').write_bytes(nacp)
        art=self.root/'new.webp';Image.new('RGB',(300,300),'blue').save(art)
        cover=artwork_bytes(ArtworkSelection(art));(control/'icon_AmericanEnglish.dat').write_bytes(b'old icon')
        nup=self.root/'custom.nup';nt.pack_folder(self.bundle,nup,include_kinds={0},title='New Title',artwork=cover)
        with nf.Archive(nup) as a:
            self.assertEqual(a.packages[0].files['data/control/control.nacp'].read_small(),bytes(nacp))
            self.assertEqual(a.packages[0].files['data/control/icon_AmericanEnglish.dat'].read_small(),b'old icon')
        nsp=self.root/'custom.nsp';nt.nup_to_nsp(nup,nsp)
        with nt.nsp_packages(nsp) as packages:
            metadata=dict(packages[0].metadata);self.assertEqual(metadata[5],b'New Title');self.assertEqual(metadata[3],cover)
        self.assertEqual((control/'control.nacp').read_bytes(),bytes(nacp))
