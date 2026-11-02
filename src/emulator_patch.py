"""Offline, exact-build, reversible Windows emulator container-detection patch.

No external patch manifests or executables are downloaded or trusted. The native
probe and its source are included. Never mutate an unrecognized executable.
"""
from pathlib import Path
import base64,contextlib,hashlib,json,os,struct,sys,tempfile,zlib
from emulator_profiles import PROFILES
from emulator_payloads import PAYLOADS,LEGACY_PAYLOADS
from emulator_patterns import PATTERNS

PATCH_ID='embedded-npdm-v1'
PATCH_REVISION=2
STATE_DIR='.s2gp-patch'
NAMES=('eglantine.exe','pokedinner.exe','PokeDinner.exe','eden.exe','eden-cli.exe')

def digest(data):return hashlib.sha256(data).hexdigest()
def align(n,a):return (n+a-1)//a*a
def linked(path):
    return path.is_symlink() or bool(getattr(path.lstat(),'st_file_attributes',0)&0x400)

class PE:
    def __init__(self,data):
        self.data=data
        if len(data)<0x100 or data[:2]!=b'MZ':raise ValueError('Not a Windows executable.')
        self.pe=struct.unpack_from('<I',data,0x3c)[0]
        if data[self.pe:self.pe+4]!=b'PE\0\0':raise ValueError('Invalid PE header.')
        machine,self.count=struct.unpack_from('<HH',data,self.pe+4)
        self.optional=self.pe+24;size=struct.unpack_from('<H',data,self.pe+20)[0]
        if machine!=0x8664 or struct.unpack_from('<H',data,self.optional)[0]!=0x20b or size<240:
            raise ValueError('Only verified Windows x64 builds are supported.')
        self.table=self.optional+size
        if not 1<=self.count<=32 or self.table+40*self.count>len(data):raise ValueError('Invalid section table.')
        self.sections=[]
        for i in range(self.count):
            off=self.table+40*i
            name,vs,va,rs,rp=struct.unpack_from('<8sIIII',data,off)
            if rp+rs>len(data):raise ValueError('Section extends past the executable.')
            self.sections.append((name,vs,va,rs,rp))
        self.section_align,self.file_align=struct.unpack_from('<II',data,self.optional+32)
        if self.section_align!=4096 or self.file_align not in (512,4096):raise ValueError('Unsupported section alignment.')
        cert,cert_size=self.directory(4)
        if cert_size:raise ValueError('Signed executables are not supported by this patch.')
    def directory(self,index):return struct.unpack_from('<II',self.data,self.optional+112+8*index)
    def offset(self,rva,size=1):
        for _,vs,va,rs,rp in self.sections:
            if va<=rva and rva+size<=va+rs:return rp+rva-va
        raise ValueError('Patch location is outside a file-backed section.')
    def read(self,rva,size):
        off=self.offset(rva,size);return self.data[off:off+size]

def rel(opcode,source,target):return bytes([opcode])+struct.pack('<i',target-source-5)

def reader_abi(pe,frames,start,pattern):
    """Validate the metadata reader too: a loader match alone cannot prove VFS ABI."""
    call=start+pattern['metadata_call_delta'];code=pe.read(call,5)
    if code[0]!=0xe8:return None
    target=call+5+struct.unpack_from('<i',code,1)[0]
    spec=pattern['reader'];mask=zlib.decompress(base64.b85decode(spec['mask']))
    if not any(a==target and b-a>=len(mask) for a,b,_ in frames):return None
    body=pe.read(target,len(mask))
    if not body.startswith(bytes.fromhex(spec['anchor'])) or digest(bytes(b&m for b,m in zip(body,mask)))!=spec['normalized_sha256']:return None
    size=body[spec['size_disp_offset']];read=body[spec['read_disp_offset']]
    if size%8 or read%8:return None
    return next((key for key,value in PAYLOADS.items() if value['size_slot']==size//8 and value['read_slot']==read//8),None)

def profile_for(data,name,legacy=False):
    """Known build or a unique normalized loader-code fingerprint, never an offset guess."""
    known=PROFILES.get(digest(data))
    if known and known['file'].lower()==name.lower():return dict(known,verified=True)
    markers=(b'main.npdm\0',b'Switch 2 program: using the 12 GiB memory layout',b'Guest counter frequency:')
    if not all(marker in data for marker in markers):return None
    try:
        pe=PE(data);rva,size=pe.directory(3)
        if not size or size%12:return None
        frames=list(struct.iter_unpack('<III',pe.read(rva,size)))
        matches=[]
        for pattern in PATTERNS:
            mask=zlib.decompress(base64.b85decode(pattern['mask']));anchor=bytes.fromhex(pattern['anchor'])
            for start,end,_ in frames:
                if end-start<len(mask) or pe.read(start,len(anchor))!=anchor:continue
                body=pe.read(start,len(mask))
                if digest(bytes(b&m for b,m in zip(body,mask)))!=pattern['normalized_sha256']:continue
                hook=start+pattern['hook_delta'];expected=pattern['expected']
                if pe.read(hook,len(bytes.fromhex(expected))).hex()!=expected:continue
                abi=('gnu' if pattern['kind']=='inline' else 'msvc') if legacy else reader_abi(pe,frames,start,pattern)
                if abi is None:continue
                match={'name':'Compatible loader · experimental build','file':name,'abi':abi,
                       'hook':hook,'expected':expected,'kind':pattern['kind'],'verified':False}
                if pattern.get('preserve_duplicate_unwind'):match['preserve_duplicate_unwind']=True
                matches.append(match)
        return matches[0] if len(matches)==1 else None
    except (ValueError,struct.error,zlib.error,KeyError):return None

def transform(data,profile,revision=PATCH_REVISION):
    """Pure transform; caller handles verified backups and atomic file replacement."""
    pe=PE(data);hook=profile['hook'];saved=bytes.fromhex(profile['expected'])
    if pe.read(hook,len(saved))!=saved:raise ValueError('Expected patch instructions do not match.')
    first_raw=min(rp for _,_,_,rs,rp in pe.sections if rs)
    if pe.table+40*(pe.count+1)>first_raw:raise ValueError('No room for the patch section header.')
    end=max(va+max(vs,rs) for _,vs,va,rs,_ in pe.sections)
    base=align(end,pe.section_align)
    if revision not in (1,PATCH_REVISION):raise ValueError('Unsupported patch revision.')
    legacy_abi='gnu' if profile['kind']=='inline' else 'msvc'
    payload=LEGACY_PAYLOADS[legacy_abi] if revision==1 else PAYLOADS[profile['abi']]
    blob=bytearray(zlib.decompress(base64.b85decode(payload['image'])))
    if digest(blob)!=payload['sha256']:raise ValueError('Included native probe failed its integrity check.')
    functions=[(base+a,base+b,base+c) for a,b,c in payload['unwind']]
    original_rva,original_size=pe.directory(3)
    if not original_size or original_size%12:raise ValueError('Invalid executable unwind table.')
    original=pe.read(original_rva,original_size)
    original_functions=list(struct.iter_unpack('<III',original))
    def put(value,a=4):
        blob.extend(bytes(align(len(blob),a)-len(blob)));off=len(blob);blob.extend(value);return base+off
    wrapper=base+len(blob);code=bytearray()
    def call(target):code.extend(rel(0xe8,wrapper+len(code),target))
    if profile['kind']=='entry':
        code.extend(bytes.fromhex('4883ec3848894c2420')) # stack + shared_ptr save
        call(base+payload['entry']);code.extend(bytes.fromhex('85c074054883c438c3'))
        code.extend(bytes.fromhex('488b4c2420'))
        trampoline_call=len(code);code.extend(bytes(5));code.extend(bytes.fromhex('4883c438c3'))
        trampoline=wrapper+len(code)
        code[trampoline_call:trampoline_call+5]=rel(0xe8,wrapper+trampoline_call,trampoline)
        code.extend(saved);code.extend(rel(0xe9,wrapper+len(code),hook+len(saved)))
        blob.extend(code)
        uw=put(bytes.fromhex('0104010004620000')) # ALLOC_SMALL 56
        tuw=put(bytes.fromhex('0105020005340200')) # original SAVE_NONVOL RBX, +16
        functions.extend([(wrapper,trampoline,uw),(trampoline,wrapper+len(code),tuw)])
    elif profile['kind'] in ('inline','inline-pokedinner','inline-selevet'):
        # PGO inlines the original function into System::Load. Its file shared_ptr
        # remains alive at rsp+0x108 here, and the original result is in EBP.
        frame=next((f for f in original_functions if f[0]<=hook<f[1]),None)
        if frame is None:raise ValueError('Original PGO unwind frame not found.')
        # Reuse System::Load's existing 32-byte outgoing-call shadow space.
        # RSP does not change, so the chained original unwind frame remains exact.
        pokedinner=profile['kind']=='inline-pokedinner'
        selevet=profile['kind']=='inline-selevet'
        # Selevet keeps the live file in the same RBP-relative slot, but its
        # hardware-mode result is R13D instead of PokeDinner's R12D.
        code.extend(bytes.fromhex('488d8da8030000' if pokedinner or selevet else '488d8c2408010000'))
        call(base+payload['entry']);code.extend(bytes.fromhex('4109c5' if selevet else '4109c4' if pokedinner else '09c5'))
        code.extend(saved);code.extend(rel(0xe9,wrapper+len(code),hook+len(saved)));blob.extend(code)
        frame_register=pe.read(frame[2],4)[3]
        uw=put(bytes([0x21,0,0,frame_register])+struct.pack('<III',*frame))
        functions.append((wrapper,wrapper+len(code),uw))
    else:raise ValueError('Unknown patch profile kind.')
    # Keep equal-start original records in their existing order. Selevet's
    # linker emits one folded funclet twice, with identical stack-unwind codes.
    functions=sorted(original_functions+functions,key=lambda f:f[0])
    original_set=set(original_functions)
    for a,b in zip(functions,functions[1:]):
        if a[1]<=b[0]:continue
        duplicate=(profile.get('preserve_duplicate_unwind') and a[:2]==b[:2]
                   and a in original_set and b in original_set)
        if duplicate:
            first,second=pe.read(a[2],4),pe.read(b[2],4)
            duplicate=(first[0]&7==second[0]&7==1 and first[1:]==second[1:]
                       and not (first[0]|second[0])&0x20
                       and pe.read(a[2]+4,first[2]*2)==pe.read(b[2]+4,second[2]*2))
        if not duplicate:raise ValueError('Overlapping unwind functions.')
    exception=put(b''.join(struct.pack('<III',*f) for f in functions))
    raw=align(len(data),pe.file_align);raw_size=align(len(blob),pe.file_align)
    result=bytearray(data);result.extend(bytes(raw-len(result)));result.extend(blob)
    result.extend(bytes(raw_size-len(blob)))
    struct.pack_into('<H',result,pe.pe+6,pe.count+1)
    struct.pack_into('<8sIIIIIIHHI',result,pe.table+40*pe.count,b'.s2gpx\0\0',len(blob),base,raw_size,raw,0,0,0,0,0x60000020)
    struct.pack_into('<I',result,pe.optional+56,align(base+len(blob),pe.section_align))
    struct.pack_into('<I',result,pe.optional+4,struct.unpack_from('<I',data,pe.optional+4)[0]+raw_size)
    struct.pack_into('<II',result,pe.optional+112+3*8,exception,len(functions)*12)
    off=pe.offset(hook,len(saved));result[off:off+len(saved)]=rel(0xe9,hook,wrapper)+b'\x90'*(len(saved)-5)
    struct.pack_into('<I',result,pe.optional+64,0)
    checksum=sum(memoryview(result).cast('H')) if sys.byteorder=='little' else sum(v[0] for v in struct.iter_unpack('<H',result))
    while checksum>>16:checksum=(checksum&0xffff)+(checksum>>16)
    struct.pack_into('<I',result,pe.optional+64,checksum+len(result))
    return bytes(result)

def root_folder(folder):
    root=Path(folder).resolve(strict=True)
    if not root.is_dir():raise ValueError('Choose an emulator folder.')
    if not any(root.glob('*.exe')):
        children=[p for p in root.iterdir() if p.is_dir() and not linked(p) and any(p.glob('*.exe'))]
        if len(children)==1:root=children[0].resolve()
    state=root/STATE_DIR
    if state.exists() and (linked(state) or not state.is_dir()):raise ValueError('Patch backup folder is linked or invalid.')
    return root,state

def records(state):
    path=state/'state.json'
    if not path.exists():return {}
    if linked(path):raise ValueError('Linked patch manifest refused.')
    value=json.loads(path.read_text(encoding='utf-8'))
    if value.get('patch_id')!=PATCH_ID or not isinstance(value.get('files'),dict):raise ValueError('Unrecognized patch manifest.')
    files=value['files']
    for name,info in files.items():
        if Path(name).name!=name or any(c in name for c in '/\\:') or not name.lower().endswith('.exe') or not isinstance(info,dict):
            raise ValueError('Invalid backup filename.')
        if info.get('revision',1) not in (1,PATCH_REVISION):raise ValueError('Unsupported saved patch revision.')
        for field in ('original','patched'):
            value=info.get(field)
            if not isinstance(value,str) or len(value)!=64 or any(c not in '0123456789abcdef' for c in value):
                raise ValueError('Invalid backup fingerprint.')
    return files

def inspect(folder):
    root,state=root_folder(folder);saved=records(state);files=[];seen=set()
    candidates=sorted(root.glob('*.exe'),key=lambda p:p.name.lower())
    for file in candidates:
        if not file.is_file() or file.resolve() in seen:continue
        seen.add(file.resolve())
        if linked(file):raise ValueError('Linked emulator executables are not supported.')
        data=file.read_bytes();sha=digest(data);info=saved.get(file.name)
        profile=None if info and sha==info['patched'] else profile_for(data,file.name)
        if not profile and not info and file.name.lower() not in {n.lower() for n in NAMES}:continue
        status=('supported' if profile['verified'] else 'experimental') if profile else 'unsupported'
        if info:
            backup=state/(file.name+'.original')
            if not backup.is_file() or linked(backup) or digest(backup.read_bytes())!=info['original']:
                raise ValueError('Original backup is missing or changed; no files will be modified.')
            if sha==info['patched']:
                revision=info.get('revision',1)
                original=backup.read_bytes();known=profile_for(original,file.name,legacy=revision==1)
                if known is None:raise ValueError('Original backup loader is not recognized.')
                if digest(transform(original,known,revision))!=sha:raise ValueError('Patch manifest does not match this patch version.')
                status='outdated' if revision<PATCH_REVISION else 'patched';profile=known
            elif sha==info['original']:
                status=('supported' if profile['verified'] else 'experimental') if profile else 'unsupported'
            else:status='changed'
        files.append({'file':file.name,'sha256':sha,'status':status,'build':profile['name'] if profile else 'Unknown build'})
    if not files:raise ValueError('No compatible Switch 2 loader was recognized. Select the folder containing the emulator EXE.')
    blocked=any(f['status']=='changed' for f in files)
    return {'folder':str(root),'files':files,'can_apply':not blocked and any(f['status'] in ('supported','experimental') for f in files),
            'can_remove':not blocked and any(f['status'] in ('patched','outdated') for f in files)}

def atomic_write(path,data,exclusive=False):
    if path.exists() and linked(path):raise ValueError('Linked output refused.')
    if exclusive:
        with path.open('xb') as stream:stream.write(data);stream.flush();os.fsync(stream.fileno())
        return
    with tempfile.NamedTemporaryFile(prefix='.s2gp-',suffix='.tmp',dir=path.parent,delete=False) as stream:
        tmp=Path(stream.name);stream.write(data);stream.flush();os.fsync(stream.fileno())
    try:os.replace(tmp,path)
    finally:
        if tmp.exists():tmp.unlink()

@contextlib.contextmanager
def locked(folder):
    root,state=root_folder(folder);state.mkdir(exist_ok=True);lock=state/'operation.lock'
    if lock.exists() and linked(lock):raise ValueError('Linked operation lock refused.')
    # OS locks are released on process exit, so a patcher crash cannot leave a
    # stale directory lock preventing recovery on the next launch.
    with lock.open('a+b') as stream:
        if not os.fstat(stream.fileno()).st_size:stream.write(b'\0');stream.flush()
        stream.seek(0)
        try:
            if os.name=='nt':
                import msvcrt
                msvcrt.locking(stream.fileno(),msvcrt.LK_NBLCK,1)
            else:
                import fcntl
                fcntl.flock(stream.fileno(),fcntl.LOCK_EX|fcntl.LOCK_NB)
        except OSError:raise ValueError('A patch operation is already running. Try again when it finishes.') from None
        try:yield root,state
        finally:
            if os.name=='nt':stream.seek(0);msvcrt.locking(stream.fileno(),msvcrt.LK_UNLCK,1)
            else:fcntl.flock(stream.fileno(),fcntl.LOCK_UN)

def apply(folder):
    if not inspect(folder)['can_apply']:raise ValueError('No recognizable unpatched loader found, or executable files changed after patching.')
    with locked(folder) as (root,state):
        view=inspect(root)
        if not view['can_apply']:raise ValueError('This folder is patched, changed, or contains an unsupported build.')
        saved=records(state);pending=[]
        for item in view['files']:
            if item['status'] not in ('supported','experimental'):continue
            file=root/item['file'];data=file.read_bytes()
            if digest(data)!=item['sha256']:raise ValueError('Emulator changed while checking. Try again.')
            profile=profile_for(data,file.name)
            if profile is None:raise ValueError('Loader code is no longer recognized.')
            patched=transform(data,profile);backup=state/(file.name+'.original')
            if backup.exists():
                if linked(backup) or backup.read_bytes()!=data:raise ValueError('An unrelated backup already exists; it was preserved.')
            else:atomic_write(backup,data,True)
            saved[file.name]={'original':digest(data),'patched':digest(patched),'revision':PATCH_REVISION}
            pending.append((file,data,patched))
        # Persist recovery data before replacing anything. A crash midway leaves
        # every file independently recognizable and removable on the next run.
        atomic_write(state/'state.json',json.dumps({'patch_id':PATCH_ID,'files':saved},indent=2).encode())
        changed=[]
        try:
            for file,data,patched in pending:
                if digest(file.read_bytes())!=digest(data):raise ValueError('Emulator changed while applying. Try again.')
                atomic_write(file,patched);changed.append((file,data))
        except Exception:
            for file,data in reversed(changed):atomic_write(file,data)
            raise
        return inspect(root)

def remove(folder):
    if not inspect(folder)['can_remove']:raise ValueError('No safely removable patch found, or the emulator changed after patching.')
    with locked(folder) as (root,state):
        view=inspect(root)
        if not view['can_remove']:raise ValueError('No safely removable patch found, or the emulator changed after patching.')
        saved=records(state);changed=[]
        try:
            for item in view['files']:
                if item['status'] not in ('patched','outdated'):continue
                file=root/item['file'];current=file.read_bytes()
                if digest(current)!=item['sha256']:raise ValueError('Emulator changed while restoring. Try again.')
                original=(state/(file.name+'.original')).read_bytes()
                atomic_write(file,original);changed.append((file,current))
        except Exception:
            for file,data in reversed(changed):atomic_write(file,data)
            raise
        return inspect(root)
