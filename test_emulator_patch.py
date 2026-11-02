"""Synthetic PE transactions, forward detection and native container-probe tests."""
from pathlib import Path
import base64,ctypes,hashlib,os,struct,sys,tempfile,unittest,zlib
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
import emulator_patch as ep
import container_format as fmt

def synthetic_pe():
    b=bytearray(0xa00);b[:2]=b'MZ';struct.pack_into('<I',b,0x3c,0x80);b[0x80:0x84]=b'PE\0\0'
    struct.pack_into('<HHIIIHH',b,0x84,0x8664,2,1,0,0,240,0x22)
    opt=0x98;struct.pack_into('<H',b,opt,0x20b);struct.pack_into('<I',b,opt+16,0x1000)
    struct.pack_into('<Q',b,opt+24,0x140000000);struct.pack_into('<II',b,opt+32,4096,512)
    struct.pack_into('<II',b,opt+56,0x3000,0x400);struct.pack_into('<I',b,opt+108,16)
    struct.pack_into('<II',b,opt+112+24,0x2000,12)
    table=opt+240
    struct.pack_into('<8sIIIIIIHHI',b,table,b'.text\0\0\0',0x400,0x1000,0x400,0x400,0,0,0,0,0x60000020)
    struct.pack_into('<8sIIIIIIHHI',b,table+40,b'.rdata\0\0',0x200,0x2000,0x200,0x800,0,0,0,0,0x40000040)
    b[0x400:0x440]=bytes.fromhex('48895c2410')+b'\x90'*58+b'\xc3'
    struct.pack_into('<III',b,0x800,0x1000,0x1040,0x2010);b[0x810:0x814]=b'\x01\0\0\0'
    marker=b'main.npdm\0Switch 2 program: using the 12 GiB memory layout\0Guest counter frequency:\0'
    b[0x840:0x840+len(marker)]=marker
    return bytes(b)

def fixture_profile(name='eglantine.exe'):
    return {'name':'Synthetic test emulator','file':name,'abi':'msvc','hook':0x1000,'expected':'48895c2410','kind':'entry'}

class PatchTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='patch-',dir=scratch);self.root=Path(self.tmp.name)
        self.original=synthetic_pe();self.file=self.root/'eglantine.exe';self.file.write_bytes(self.original)
        self.profiles={ep.digest(self.original):fixture_profile()}
        self.mock=patch.object(ep,'PROFILES',self.profiles);self.mock.start()
    def tearDown(self):self.mock.stop();self.tmp.cleanup()
    def test_apply_remove_exact_and_repeat(self):
        for _ in range(2):
            self.assertTrue(ep.inspect(self.root)['can_apply'])
            self.assertTrue(ep.apply(self.root)['can_remove'])
            self.assertNotEqual(self.file.read_bytes(),self.original)
            self.assertEqual((self.root/ep.STATE_DIR/'eglantine.exe.original').read_bytes(),self.original)
            self.assertTrue(ep.remove(self.root)['can_apply'])
            self.assertEqual(self.file.read_bytes(),self.original)
    def test_unknown_loader_is_untouched(self):
        self.file.write_bytes(b'MZ'+bytes(100))
        self.assertFalse(ep.inspect(self.root)['can_apply'])
        with self.assertRaises(ValueError):ep.apply(self.root)
        self.assertEqual(self.file.read_bytes(),b'MZ'+bytes(100))
        self.assertFalse((self.root/ep.STATE_DIR).exists())
    def test_changed_executable_or_backup_is_not_overwritten(self):
        ep.apply(self.root);current=self.file.read_bytes()+b'changed'
        self.file.write_bytes(current)
        with self.assertRaises(ValueError):ep.remove(self.root)
        self.assertEqual(self.file.read_bytes(),current)
        backup=self.root/ep.STATE_DIR/'eglantine.exe.original';backup.write_bytes(b'bad backup')
        with self.assertRaises(ValueError):ep.inspect(self.root)
        self.assertEqual(backup.read_bytes(),b'bad backup')
    def test_partial_write_failure_rolls_back(self):
        cli=self.root/'eden-cli.exe';cli_data=bytearray(self.original);cli_data[0x88]^=1;cli_data=bytes(cli_data)
        cli.write_bytes(cli_data);self.profiles[ep.digest(cli_data)]=fixture_profile('eden-cli.exe')
        write=ep.atomic_write;failed=[]
        def fail_second(path,data,exclusive=False):
            if path.name=='eglantine.exe' and data!=self.original and not failed:
                failed.append(True);raise OSError('Synthetic write failure')
            return write(path,data,exclusive)
        with patch.object(ep,'atomic_write',side_effect=fail_second):
            with self.assertRaises(OSError):ep.apply(self.root)
        self.assertEqual(self.file.read_bytes(),self.original);self.assertEqual(cli.read_bytes(),cli_data)
        self.assertTrue(ep.inspect(self.root)['can_apply'])
    def test_manifest_path_injection_and_lock(self):
        state=self.root/ep.STATE_DIR
        with ep.locked(self.root):
            with self.assertRaises(ValueError):ep.apply(self.root)
        (state/'state.json').write_text('{"patch_id":"embedded-npdm-v1","files":{"../outside.exe":{}}}')
        with self.assertRaises(ValueError):ep.inspect(self.root)
    def test_forward_match_requires_unique_exact_normalized_code(self):
        mask=bytearray(b'\xff'*64);mask[24:28]=bytes(4);body=self.original[0x400:0x440]
        pattern={'name':'fixture','abi':'msvc','kind':'entry','hook_delta':0,'expected':'48895c2410',
                 'preserve_duplicate_unwind':True,
                 'anchor':body[:12].hex(),'mask':base64.b85encode(zlib.compress(mask)).decode(),
                 'normalized_sha256':ep.digest(bytes(b&m for b,m in zip(body,mask)))}
        self.profiles.clear()
        with patch.object(ep,'PATTERNS',[pattern]),patch.object(ep,'reader_abi',return_value='msvc'):
            p=ep.profile_for(self.original,'future-fork.exe');self.assertIsNotNone(p);self.assertFalse(p['verified'])
            self.assertTrue(p['preserve_duplicate_unwind'])
            relocated=bytearray(self.original);relocated[0x418:0x41c]=b'abcd'
            self.assertIsNotNone(ep.profile_for(bytes(relocated),'future-fork.exe'))
            self.file.rename(self.root/'future-fork.exe')
            view=ep.apply(self.root);self.assertEqual(view['files'][0]['status'],'patched')
            ep.remove(self.root);self.assertEqual((self.root/'future-fork.exe').read_bytes(),self.original)
            changed=bytearray(self.original);changed[0x420]^=1
            self.assertIsNone(ep.profile_for(bytes(changed),'future-fork.exe'))
            with patch.object(ep,'PATTERNS',[pattern,pattern]):self.assertIsNone(ep.profile_for(self.original,'future-fork.exe'))

    def test_reader_abi_is_derived_and_unrecognized_slots_refused(self):
        data=bytearray(self.original);call=0x1020;target=0x1100
        data[0x420:0x425]=ep.rel(0xe8,call,target)
        body=bytearray(b'\x90'*40);body[12:15]=bytes.fromhex('ff5018');body[32:35]=bytes.fromhex('ff5048')
        data[0x500:0x528]=body
        mask=bytearray(b'\xff'*40);mask[14]=mask[34]=0
        pattern={'metadata_call_delta':32,'reader':{'anchor':body[:12].hex(),
                 'mask':base64.b85encode(zlib.compress(mask)).decode(),
                 'normalized_sha256':ep.digest(bytes(b&m for b,m in zip(body,mask))),
                 'size_disp_offset':14,'read_disp_offset':34}}
        frames=[(0x1100,0x1140,0x2010)]
        self.assertEqual(ep.reader_abi(ep.PE(data),frames,0x1000,pattern),'msvc-read9')
        data[0x522]=0x40
        self.assertEqual(ep.reader_abi(ep.PE(data),frames,0x1000,pattern),'msvc')
        data[0x522]=0x70
        self.assertIsNone(ep.reader_abi(ep.PE(data),frames,0x1000,pattern))
        data[0x50f]^=1
        self.assertIsNone(ep.reader_abi(ep.PE(data),frames,0x1000,pattern))
    def test_transform_has_valid_section_and_checksum(self):
        data=ep.transform(self.original,fixture_profile());pe=ep.PE(data)
        self.assertEqual(pe.count,3);self.assertEqual(pe.sections[-1][0],b'.s2gpx\0\0')
        self.assertEqual(pe.read(0x1000,1),b'\xe9')
        rva,size=pe.directory(3);frames=list(struct.iter_unpack('<III',pe.read(rva,size)))
        self.assertGreater(len(frames),1);self.assertEqual(frames,sorted(frames))
        for first,second in zip(frames,frames[1:]):self.assertLessEqual(first[1],second[0])
        if os.name=='nt':
            imagehlp=ctypes.WinDLL('imagehlp')
            imagehlp.CheckSumMappedFile.argtypes=[ctypes.c_void_p,ctypes.c_uint32,ctypes.POINTER(ctypes.c_uint32),ctypes.POINTER(ctypes.c_uint32)]
            imagehlp.CheckSumMappedFile.restype=ctypes.c_void_p
            buffer=ctypes.create_string_buffer(data);stored=ctypes.c_uint32();calculated=ctypes.c_uint32()
            self.assertTrue(imagehlp.CheckSumMappedFile(buffer,len(data),ctypes.byref(stored),ctypes.byref(calculated)))
            self.assertEqual(stored.value,calculated.value)
    def test_duplicate_original_unwind_records_are_guarded_and_ordered(self):
        data=bytearray(self.original)
        struct.pack_into('<II',data,0x98+112+24,0x2000,24)
        original=[(0x1000,0x1040,0x2030),(0x1000,0x1040,0x2020)]
        for i,record in enumerate(original):struct.pack_into('<III',data,0x800+12*i,*record)
        data[0x820:0x824]=data[0x830:0x834]=bytes.fromhex('01000000')
        profile=fixture_profile()
        with self.assertRaisesRegex(ValueError,'Overlapping'):ep.transform(bytes(data),profile)
        profile['preserve_duplicate_unwind']=True
        changed=ep.transform(bytes(data),profile);pe=ep.PE(changed);rva,size=pe.directory(3)
        frames=list(struct.iter_unpack('<III',pe.read(rva,size)))
        self.assertEqual([f for f in frames if f[:2]==(0x1000,0x1040)],original)
        data[0x831]=1
        with self.assertRaisesRegex(ValueError,'Overlapping'):ep.transform(bytes(data),profile)
        data[0x831]=0;struct.pack_into('<I',data,0x80c,0x1010)
        with self.assertRaisesRegex(ValueError,'Overlapping'):ep.transform(bytes(data),profile)

    def test_parent_folder_selection(self):
        self.assertEqual(Path(ep.inspect(self.root.parent/self.root.name)['folder']),self.root.resolve())

    def test_legacy_patch_can_be_removed_then_updated(self):
        import json
        old=ep.transform(self.original,fixture_profile(),revision=1)
        state=self.root/ep.STATE_DIR;state.mkdir()
        (state/'eglantine.exe.original').write_bytes(self.original)
        (state/'state.json').write_text(json.dumps({'patch_id':ep.PATCH_ID,'files':{'eglantine.exe':{
            'original':ep.digest(self.original),'patched':ep.digest(old)}}}))
        self.file.write_bytes(old)
        view=ep.inspect(self.root);self.assertEqual(view['files'][0]['status'],'outdated')
        self.assertTrue(view['can_remove']);self.assertFalse(view['can_apply'])
        ep.remove(self.root);self.assertEqual(self.file.read_bytes(),self.original)
        view=ep.apply(self.root);self.assertEqual(view['files'][0]['status'],'patched')
        self.assertEqual(ep.records(state)['eglantine.exe']['revision'],2)

def metadata(switch2):
    b=bytearray(0x480);b[:4]=b'META';struct.pack_into('<IIII',b,0x70,0x80,0x80,0x100,0x380)
    b[0x80:0x84]=b'ACI0';b[0x400 if switch2 else 0x300:0x404 if switch2 else 0x304]=b'ACID'
    return b

@unittest.skipUnless(sys.platform=='win32','Native probe uses the Windows x64 ABI')
class NativeProbeTests(unittest.TestCase):
    def test_selevet_hook_uses_live_file_and_r13_mode_flag(self):
        data=bytearray(synthetic_pe());saved=bytes.fromhex('4c8bbdb0030000')
        data[0x400:0x407]=saved
        profile={'name':'Synthetic Selevet','file':'eglantine.exe','abi':'msvc-read9',
                 'hook':0x1000,'expected':saved.hex(),'kind':'inline-selevet'}
        changed=ep.transform(bytes(data),profile);pe=ep.PE(changed)
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32]
        kernel.VirtualAlloc.restype=ctypes.c_void_p
        kernel.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
        memory=kernel.VirtualAlloc(None,struct.unpack_from('<I',changed,pe.optional+56)[0],0x3000,0x40)
        self.assertTrue(memory)
        try:
            for _,_,va,size,offset in pe.sections:ctypes.memmove(memory+va,changed[offset:offset+size],size)
            ending=bytes.fromhex('4489e84881c400060000415f415d5dc3')
            ctypes.memmove(memory+0x1000+len(saved),ending,len(ending))
            stub=bytearray.fromhex('55415541574881ec00060000488dac24800000004189d5')
            stub.extend(bytes.fromhex('488b014889842428040000488b41084889842430040000'))
            stub.extend(bytes.fromhex('48b8')+struct.pack('<Q',memory+0x1000)+bytes.fromhex('ffe0'))
            ctypes.memmove(memory+0x1100,bytes(stub),len(stub))
            invoke=ctypes.CFUNCTYPE(ctypes.c_uint32,ctypes.c_void_p,ctypes.c_uint32)(memory+0x1100)
            Size=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_void_p)
            Read=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint64,ctypes.c_uint64)
            for switch2 in (False,True):
                program=fmt.nca([fmt.pfs_section(fmt.filesystem([('main',b'NSO0'+bytes(256)),('main.npdm',metadata(switch2))]))],0x0400111122220000,0)
                sample=b''.join(fmt.filesystem([('program.nca',program)]).chunks())
                @Size
                def size(_):return len(sample)
                @Read
                def read(_,out,n,off):
                    chunk=sample[off:off+n];ctypes.memmove(out,chunk,len(chunk));return len(chunk)
                table=(ctypes.c_void_p*12)();table[3]=ctypes.cast(size,ctypes.c_void_p);table[9]=ctypes.cast(read,ctypes.c_void_p)
                file=(ctypes.c_void_p*1)(ctypes.addressof(table));shared=(ctypes.c_void_p*2)(ctypes.addressof(file),0)
                for original_mode in (0,1):
                    self.assertEqual(invoke(shared,original_mode),int(switch2 or original_mode))
        finally:kernel.VirtualFree(memory,0,0x8000)

    def test_native_switch1_switch2_and_corrupt_containers(self):
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.VirtualAlloc.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32,ctypes.c_uint32];kernel.VirtualAlloc.restype=ctypes.c_void_p
        kernel.VirtualFree.argtypes=[ctypes.c_void_p,ctypes.c_size_t,ctypes.c_uint32]
        Read=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_void_p,ctypes.c_void_p,ctypes.c_uint64,ctypes.c_uint64)
        Size=ctypes.CFUNCTYPE(ctypes.c_uint64,ctypes.c_void_p)
        for abi,payload in ep.PAYLOADS.items():
            code=zlib.decompress(base64.b85decode(payload['image']));self.assertEqual(ep.digest(code),payload['sha256'])
            memory=kernel.VirtualAlloc(None,len(code),0x3000,0x40);self.assertTrue(memory)
            try:
                ctypes.memmove(memory,code,len(code));invoke=ctypes.CFUNCTYPE(ctypes.c_int,ctypes.c_void_p)(memory+payload['entry'])
                samples=[]
                for switch2 in (False,True):
                    program=fmt.nca([fmt.pfs_section(fmt.filesystem([('main',b'NSO0'+bytes(256)),('main.npdm',metadata(switch2))]))],0x0400111122220000,0)
                    nsp=fmt.filesystem([('program.nca',program)])
                    header=bytearray(0xf000);header[0x100:0x104]=b'HEAD';struct.pack_into('<Q',header,0x130,0xf000)
                    xci=fmt.Blob(header,fmt.filesystem([('secure',fmt.filesystem([('program.nca',program)],True))],True))
                    for blob in (program,nsp,xci):samples.append((b''.join(blob.chunks(1048576)),int(switch2)))
                samples.extend([(b'',0),(bytes(100),0),(b'PFS0'+b'\xff'*100,0),(samples[-1][0][:0xf100],0)])
                for data,expected in samples:
                    trace=[]
                    @Size
                    def size(_):return len(data)
                    @Read
                    def read(_,out,n,off):
                        trace.append((off,n));chunk=data[off:off+n];ctypes.memmove(out,chunk,len(chunk));return len(chunk)
                    vt=(ctypes.c_void_p*12)();vt[payload['size_slot']]=ctypes.cast(size,ctypes.c_void_p);vt[payload['read_slot']]=ctypes.cast(read,ctypes.c_void_p)
                    file=(ctypes.c_void_p*1)(ctypes.addressof(vt));shared=(ctypes.c_void_p*2)(ctypes.addressof(file),0)
                    self.assertEqual(invoke(shared),expected,(abi,len(data)))
                    self.assertLessEqual(len(trace),8192);self.assertLessEqual(sum(n for _,n in trace),1048576)
                    self.assertTrue(all(off+n<=len(data) for off,n in trace))
            finally:kernel.VirtualFree(memory,0,0x8000)

if __name__=='__main__':unittest.main(verbosity=2)
