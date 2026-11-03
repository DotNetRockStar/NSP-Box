"""Read/compression-count regressions, decoder windows and 64-bit format sizes."""
from pathlib import Path
from unittest.mock import patch
from types import SimpleNamespace
import hashlib,io,struct,sys,tempfile,unittest
sys.path.insert(0,str(Path(__file__).parent/'src'))
import nup_format as nf,nup_tools as nt,container_format as fmt,engine
from test_nup import snapshot,TID

class NupOptimizationTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch);self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()
    def test_decoder_accepts_writer_frames_above_old_1mib_cap(self):
        data=b'abcde'*2000000;path=self.root/'window.nup'
        nf.pack([nf.Package(TID,0,0,{'romfs/data':nf.Source.data(data)})],path)
        with nf.Archive(path) as a:
            f=a.files[0];params=nf.zstd.get_frame_parameters(a.read_at(f[2],18));self.assertGreater(params.window_size,1<<20)
            a.verify();self.assertEqual(a.packages[0].files['romfs/data'].read_small(),data)
        nf.extract(path,self.root/'extracted');self.assertEqual((self.root/'extracted/base/romfs/data').read_bytes(),data)
    def test_duplicate_not_compressed_or_verified_twice_and_false_prefix_not_shared(self):
        first=b'a'*(1024*1024);different=first[:65536]+b'b'*(len(first)-65536)
        files={'romfs/a':nf.Source.data(first),'romfs/b':nf.Source.data(first),'romfs/c':nf.Source.data(different)}
        compressor=nf.zstd.ZstdCompressor;calls=[]
        def factory(*a,**kw):calls.append(kw.get('level'));return compressor(*a,**kw)
        path=self.root/'duplicates.nup'
        with patch.object(nf.zstd,'ZstdCompressor',factory):result=nf.pack([nf.Package(TID,0,0,files)],path)
        self.assertEqual(len(calls),2);self.assertEqual(result['duplicate_files_skipped'],1)
        with nf.Archive(path) as a:
            called=[];original=a.file_chunks
            def chunks(index):called.append(index);yield from original(index)
            with patch.object(a,'file_chunks',chunks):a.verify()
            self.assertEqual(len(called),2)
            self.assertEqual(a.packages[0].files['romfs/c'].read_small(),different)
    def test_small_snapshot_keeps_base_only_and_discards_old_replacements(self):
        root=self.root/'Bundle';snapshot(root/'base',{'same':b'old','needed':b'keep'})
        snapshot(root/'updates/65536',{'same':b'older update','obsolete':b'old update only'},1)
        snapshot(root/'updates/131072',{'same':b'latest','new':b'latest only'},2)
        npdm=root/'updates/131072/exefs/main.npdm';data=bytearray(npdm.read_bytes());data[0x50]=1;npdm.write_bytes(data)
        output=self.root/'small.nup';result=nt.pack_folder(root,output)
        with nf.Archive(output) as a:
            self.assertEqual(len(a.packages),1);p=a.packages[0];self.assertEqual(p.kind,0);self.assertEqual(p.version,131072)
            self.assertEqual(p.files['romfs/same'].read_small(),b'latest');self.assertEqual(p.files['romfs/needed'].read_small(),b'keep')
            self.assertNotIn('romfs/obsolete',p.files);self.assertEqual(p.files['exefs/main'].read_small(),(root/'updates/131072/exefs/main').read_bytes())
            self.assertEqual(dict(p.metadata)[1],npdm.read_bytes());self.assertEqual(dict(p.metadata)[7],bytes([2])*32)
        self.assertGreater(result['omitted_version_bytes'],0)
        nt.pack_folder(root,self.root/'archive.nup',latest_snapshot=False)
        with nf.Archive(self.root/'archive.nup') as a:self.assertEqual(len(a.packages),3)
    def test_nsp_inspection_avoids_payload_hashing_but_conversion_checks_it(self):
        game=snapshot(self.root/'Game',{'payload':b'12345'*400000});s=engine.find_snapshots(game)[0][0]
        path=self.root/'game.nsp';engine.build(s,path,'Example','1')
        original=nt.vf.digest;hashed=[]
        def spy(buf):hashed.append(len(buf));return original(buf)
        with patch.object(nt.vf,'digest',spy):
            with nt.nsp_packages(path,deep=False) as p:self.assertEqual(p[0].title_id,TID)
        self.assertLess(max(hashed),1<<20)
        hashed.clear()
        with patch.object(nt.vf,'digest',spy):nt.nsp_to_nup(path,self.root/'game.nup')
        self.assertGreater(max(hashed),1<<20)
        with path.open('r+b') as f:f.seek(-1,2);last=f.read(1);f.seek(-1,2);f.write(bytes([last[0]^1]))
        with self.assertRaises(ValueError):nt.nsp_to_nup(path,self.root/'corrupt.nup')
        self.assertFalse((self.root/'corrupt.nup').exists())
    def test_folder_inspection_reused_and_directory_changes_refused(self):
        game=snapshot(self.root/'Game',{'data':b'original'});prepared=nt.prepare_folder(game)
        with patch.object(nt,'discover',side_effect=AssertionError('Repeated folder discovery')):
            nt.pack_folder(game,self.root/'cached.nup',prepared=prepared)
        (game/'romfs/new').write_bytes(b'new file')
        with self.assertRaisesRegex(ValueError,'folder changed'):nt.pack_folder(game,self.root/'stale.nup',prepared=prepared)
        self.assertFalse((self.root/'stale.nup').exists())
    def test_changed_cached_file_refused_and_partial_removed(self):
        game=snapshot(self.root/'Game',{'data':b'original'});prepared=nt.prepare_folder(game)
        (game/'romfs/data').write_bytes(b'modified')
        with self.assertRaisesRegex(ValueError,'changed'):nt.pack_folder(game,self.root/'stale.nup',prepared=prepared)
        self.assertFalse((self.root/'stale.nup').exists());self.assertFalse(list(self.root.glob('*.partial')))
    def test_nsp_headers_support_40_and_96_gib_without_allocating_payloads(self):
        for size in (40<<30,96<<30):
            nca=fmt.nca([(bytes(512),fmt.Blob(size))],TID,0,0)
            hdr=nca.read_head(0xc00);start,end=struct.unpack_from('<II',hdr,0x240)
            self.assertGreater(end*512,32<<30);self.assertEqual(end*512,nca.size)
            package=fmt.package([('large.nca',nca)]);head=package.read_head(128)
            self.assertEqual(struct.unpack_from('<Q',head,24)[0],nca.size);self.assertGreater(package.size,size)
        with self.assertRaisesRegex(ValueError,'2 TiB'):fmt.nca([(bytes(512),fmt.Blob(2<<40))],TID,0,0)
    def test_nup_reader_uses_64_bit_offsets_and_lengths(self):
        # A virtual archive exercises the real parser at 40 GiB without a huge file.
        path=self.root/'virtual.nup';path.write_bytes(b'fixture')
        size=40<<30;pool=b'romfshuge.bin';po=48+64+2*24+80+2*4;ts=nf.align(po+len(pool));bo=nf.align(128+ts);fs=bo+size
        toc=bytearray(ts);nf.TOC.pack_into(toc,0,b'TOC\1',1,2,1,po,len(pool),0)
        nf.PKG.pack_into(toc,48,TID,0,nf.NONE,1,0,0,0,0,0,0,0,bytes(20))
        nf.DIR.pack_into(toc,112,0,0,0,1,0);nf.DIR.pack_into(toc,136,0,5,1,1,0)
        nf.FILE.pack_into(toc,160,5,8,size,bo,size,bytes(32),0,0,0,bytes(12))
        struct.pack_into('<II',toc,240,1,2);toc[po:po+len(pool)]=pool
        identity=hashlib.sha256(struct.pack('<QIB',TID,0,0)).digest()[:16]
        header=nf.SUPER.pack(b'NUP\1',128,1,128,ts,hashlib.sha256(toc).digest(),bo,fs,1,0,identity,bytes(32))
        def read_at(a,off,n):
            if off==0 and n==128:return header
            if off==128 and n==ts:return toc
            raise AssertionError('Unexpected payload read during structural inspection')
        with patch.object(Path,'stat',return_value=SimpleNamespace(st_size=fs,st_mtime_ns=0)),patch.object(nf.Archive,'read_at',read_at):
            with nf.Archive(path) as a:self.assertEqual(a.files[0][1],size);self.assertEqual(a.stats['archive_size'],fs)

if __name__=='__main__':unittest.main()
