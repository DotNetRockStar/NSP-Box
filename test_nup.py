"""NUP interoperability, conversion semantics and hostile-input failure tests."""
from pathlib import Path
import hashlib, io, json, os, struct, sys, tempfile, threading, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
import nup_format as nf, nup_tools as nt, engine

TID=0x0400111122220000

def snapshot(root,romfs,version=0):
    (root/'exefs').mkdir(parents=True);(root/'romfs').mkdir()
    npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80)
    npdm[0x80:0x84]=b'ACI0';struct.pack_into('<Q',npdm,0x90,TID)
    (root/'exefs/main.npdm').write_bytes(npdm);(root/'exefs/main').write_bytes(b'NSO0'+bytes([version])*256)
    for name,data in romfs.items():
        p=root/'romfs'/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return root

class NupTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch);self.root=Path(self.tmp.name)
        self.game=snapshot(self.root/'Game [0400111122220000]',{'zero.bin':bytes(200000),'random.bin':os.urandom(100000),'empty':b'','日本語/あ.txt':'Hello 日本語'.encode()})
        (self.game/'romfs/empty-dir').mkdir();(self.game/'romfs/.listing').write_bytes(b'dump artifact')
        (self.game/'romfs/copy.bin').write_bytes((self.game/'romfs/zero.bin').read_bytes())
    def tearDown(self):self.tmp.cleanup()
    def pack(self,**kw):
        path=self.root/'game.nup';nt.pack_folder(self.game,path,**kw);return path
    def test_presets_raw_fallback_dedup_and_unicode_round_trip(self):
        for level in (1,3,9):
            path=self.root/f'level{level}.nup';nt.pack_folder(self.game,path,level=level)
            with nf.Archive(path) as a:
                a.verify();self.assertEqual(a.packages[0].title_id,TID)
                tree=a.trees[0];self.assertNotIn('romfs/.listing',tree)
                zero=a.files[tree['romfs/zero.bin']];copy=a.files[tree['romfs/copy.bin']]
                self.assertEqual(zero[2:4],copy[2:4]);self.assertEqual(zero[5],1)
                self.assertEqual(a.files[tree['romfs/random.bin']][5],0)
                self.assertIn('romfs/empty-dir',a.packages[0].directories)
            out=self.root/f'level{level}';nf.extract(path,out)
            for p in self.game.rglob('*'):
                if p.is_file() and p.name!='.listing':self.assertEqual(p.read_bytes(),(out/'base'/p.relative_to(self.game)).read_bytes())
    def test_threshold_uses_strict_greater_than(self):
        packages=nt.discover(self.game)
        with patch.object(nf,'LARGE_FILE',100000):
            nf.pack(packages,self.root/'raw.nup')
        with nf.Archive(self.root/'raw.nup') as a:
            self.assertEqual(a.files[a.trees[0]['romfs/zero.bin']][5],0)
        with patch.object(nf,'LARGE_FILE',100000):nf.pack(packages,self.root/'compressed.nup',large_raw=False)
        with nf.Archive(self.root/'compressed.nup') as a:self.assertEqual(a.files[a.trees[0]['romfs/zero.bin']][5],1)
    def test_cancel_removes_partial_and_preserves_input(self):
        event=threading.Event();out=self.root/'cancel.nup'
        def notify(s,v):
            if v>4:event.set()
        with self.assertRaises(InterruptedError):nt.pack_folder(self.game,out,notify=notify,cancel=event)
        self.assertFalse(out.exists());self.assertFalse(list(self.root.glob('*.partial')));self.assertTrue((self.game/'exefs/main').exists())
    def test_output_refuses_overwrite_and_inside_source(self):
        with self.assertRaises(ValueError):nt.pack_folder(self.game,self.game/'bad.nup')
        path=self.pack();old=path.read_bytes()
        with self.assertRaises(ValueError):nt.pack_folder(self.game,path)
        self.assertEqual(path.read_bytes(),old)
        out=self.root/'existing';out.mkdir();(out/'keep').write_text('keep')
        with self.assertRaises(ValueError):nf.extract(path,out)
        self.assertEqual((out/'keep').read_text(),'keep')
    def test_toc_corruption_and_file_corruption_rejected(self):
        path=self.pack();original=path.read_bytes();b=bytearray(original);b[140]^=1;path.write_bytes(b)
        with self.assertRaisesRegex(ValueError,'SHA-256'):nf.Archive(path)
        path.write_bytes(original)
        with nf.Archive(path) as a:off=next(f[2] for f in a.files if f[5]==0 and f[1]>1000)
        b=bytearray(original);b[off+50]^=1;path.write_bytes(b)
        with nf.Archive(path) as a:
            with self.assertRaisesRegex(ValueError,'SHA-256'):a.verify()
        with self.assertRaises(ValueError):nf.extract(path,self.root/'bad-extract')
        self.assertFalse((self.root/'bad-extract').exists());self.assertFalse(list(self.root.glob('.nup-extract-*')))
    def mutate_toc(self,path,edit):
        b=bytearray(path.read_bytes());size=struct.unpack_from('<Q',b,16)[0];toc=bytearray(b[128:128+size]);edit(toc);b[128:128+size]=toc;b[24:56]=hashlib.sha256(toc).digest();path.write_bytes(b)
    def test_unknown_codec_and_unsafe_labels(self):
        path=self.pack()
        def edit(t):
            pc,nd=struct.unpack_from('<IQ',t,4);off=48+pc*64+nd*24;t[off+64]=2
        self.mutate_toc(path,edit)
        with self.assertRaisesRegex(ValueError,'codec'):nf.Archive(path)
        with self.assertRaises(ValueError):nf.pack([nf.Package(TID,0,0,{'../escape':nf.Source.data(b'x')})],self.root/'unsafe.nup')
    def test_source_changes_abort(self):
        packages=nt.discover(self.game);(self.game/'romfs/empty').write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError,'changed'):nf.pack(packages,self.root/'changed.nup')
        self.assertFalse((self.root/'changed.nup').exists())
    def bundle(self):
        bundle=self.root/'bundle';snapshot(bundle/'base',{'shared':b'base','base-only':b'base retained','sub/a':b'old'})
        snapshot(bundle/'updates/65536',{'shared':b'older','old-update-only':b'do not cumulatively layer'},1)
        snapshot(bundle/'updates/131072',{'shared':b'latest','sub/a':b'new','new-only':b'new'},2)
        dlc=bundle/'dlc'/f'{TID+0x1001:016X}'/'65536'/'romfs';dlc.mkdir(parents=True);(dlc/'addon').write_bytes(b'addon data')
        return bundle
    def test_bundle_update_semantics_and_multi_nsp_conversion(self):
        bundle=self.bundle();path=self.root/'bundle.nup';nt.pack_folder(bundle,path,latest_snapshot=False)
        self.assertEqual([p.kind for p in nt.discover(bundle/'dlc')],[2])
        self.assertTrue(all(p.flags==1 for p in nt.discover(bundle/'updates')))
        with nf.Archive(path) as a:
            self.assertEqual([p.kind for p in a.packages],[0,1,1,2]);self.assertFalse(a.packages[1].flags)
            merged=nt.merge_game(a.packages)
            self.assertEqual(merged.version,131072);self.assertEqual(merged.files['romfs/shared'].read_small(),b'latest')
            self.assertIn('romfs/base-only',merged.files);self.assertNotIn('romfs/old-update-only',merged.files)
            self.assertEqual(merged.files['exefs/main'].read_small(),(bundle/'updates/131072/exefs/main').read_bytes())
        out=self.root/'converted';result=nt.nup_to_nsp(path,out)
        self.assertEqual(result['packages'],2)
        game=next(out.glob('Game*.nsp'));addon=next(out.glob('DLC*.nsp'))
        with nt.nsp_packages(game) as packages:
            self.assertEqual(packages[0].title_id,TID);self.assertEqual(packages[0].version,131072)
            self.assertEqual(packages[0].files['romfs/shared'].read_small(),b'latest')
            self.assertIn('romfs/base-only',packages[0].files)
        with nt.nsp_packages(addon) as packages:
            self.assertEqual(packages[0].title_id,TID+0x1001);self.assertEqual(packages[0].kind,2)
            self.assertEqual(packages[0].files['romfs/addon'].read_small(),b'addon data')
        # Select the older update explicitly: retain base-only files, use its ExeFS.
        selected=self.root/'older.nsp';nt.nup_to_nsp(path,selected,selection=1)
        with nt.nsp_packages(selected) as packages:self.assertEqual(packages[0].files['romfs/shared'].read_small(),b'older');self.assertEqual(packages[0].version,65536)
    def test_empty_base_update_only_and_partial_refusal(self):
        root=self.root/'update-only';(root/'base').mkdir(parents=True)
        snapshot(root/'updates/327680',{'updated':b'complete'},3)
        path=self.root/'update.nup';nt.pack_folder(root,path,latest_snapshot=False)
        with nf.Archive(path) as a:self.assertEqual(a.packages[0].flags,1)
        nt.nup_to_nsp(path,self.root/'standalone.nsp')
        bad=nf.Package(TID,1,1,{'romfs/data':nf.Source.data(b'delta')},flags=1)
        nf.pack([bad],self.root/'partial.nup')
        with self.assertRaisesRegex(ValueError,'ExeFS'):nt.nup_to_nsp(self.root/'partial.nup',self.root/'not.nsp')
        self.assertFalse((self.root/'not.nsp').exists())
    def test_plaintext_nsp_nup_nsp_exact_contents_control_and_ids(self):
        s=engine.find_snapshots(self.game)[0][0];original=self.root/'original.nsp';engine.build(s,original,'Title 日本語','1.2.3')
        path=self.root/'converted.nup';nt.nsp_to_nup(original,path)
        rebuilt=self.root/'rebuilt.nsp';nt.nup_to_nsp(path,rebuilt)
        with nt.nsp_packages(original) as before,nt.nsp_packages(rebuilt) as after:
            self.assertEqual(before[0].title_id,after[0].title_id);self.assertEqual(before[0].version,after[0].version)
            self.assertEqual(set(before[0].files),set(after[0].files))
            for name,source in before[0].files.items():
                if not name.startswith('data/nsp/'):self.assertEqual(source.read_small(),after[0].files[name].read_small(),name)
    def test_metadata_unknown_tlv_and_selected_extraction_repack(self):
        bundle=self.bundle();packages=nt.discover(bundle);packages[2].metadata.append((0x8001,b'private opaque metadata'))
        path=self.root/'meta.nup';nf.pack(packages,path);out=self.root/'extracted';nf.extract(path,out,selection=[2])
        restored=nt.discover(out)
        # Extracted update is now standalone because no base was selected.
        self.assertEqual(restored[0].metadata,packages[2].metadata)
        self.assertEqual(restored[0].flags,1);nf.pack(restored,self.root/'selected-repacked.nup')
        self.assertFalse((out/'base').exists());self.assertTrue((out/'updates/131072/exefs/main.npdm').exists())
    def test_unrelated_updates_and_ambiguous_duplicate_rejected(self):
        a=nf.Package(TID,0,0,{'romfs/x':nf.Source.data(b'x')})
        b=nf.Package(TID+0x2000,1,1,{'romfs/x':nf.Source.data(b'x')})
        with self.assertRaisesRegex(ValueError,'different game'):nf.pack([a,b],self.root/'unrelated.nup')
        with self.assertRaises(ValueError):nf.pack([a,a],self.root/'duplicate.nup')

    def test_corrupt_compression_and_cancelled_conversion_cleanup(self):
        path=self.pack();original=path.read_bytes()
        with nf.Archive(path) as a:offset=next(f[2] for f in a.files if f[5]==1 and f[1]>10000)
        b=bytearray(original);b[offset+8]^=0xff;path.write_bytes(b)
        with self.assertRaises((ValueError,nf.zstd.ZstdError)):
            with nf.Archive(path) as a:a.verify()
        path.write_bytes(original);event=threading.Event();event.set()
        with self.assertRaises(InterruptedError):nt.nup_to_nsp(path,self.root/'cancelled',cancel=event)
        self.assertFalse((self.root/'cancelled').exists());self.assertFalse(list(self.root.glob('.nup-convert-*')))

if __name__=='__main__':unittest.main()
