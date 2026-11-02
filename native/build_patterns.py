"""Generate compiler-shape signatures from reviewed emulator executables.

Development only: pip install pefile==2024.8.26 capstone==5.0.9
Supply --msvc, --pgo, --pokedinner and --selevet paths to the reviewed GUI executables.
Relative calls, branches leaving the signature, and RIP-relative addresses are
masked. Stack layout, detection logic and instruction shape remain exact; a match
must begin at a PE unwind-function boundary. The metadata-reader fingerprint
selects only supported GetSize/Read slots rather than assuming a fork's VFS ABI.
"""
from pathlib import Path
import argparse,base64,hashlib,zlib
import pefile,capstone

def signature(cs,pe,start,end,zero=()):
    body=pe.get_data(start,end-start);mask=bytearray(b'\xff'*len(body));end_seen=start
    for ins in cs.disasm(body,start):
        end_seen=ins.address+ins.size;position=ins.address-start
        if any(op.type==capstone.x86.X86_OP_MEM and op.mem.base==capstone.x86.X86_REG_RIP for op in ins.operands):
            mask[position+ins.disp_offset:position+ins.disp_offset+ins.disp_size]=bytes(ins.disp_size)
        if ins.group(capstone.CS_GRP_CALL) or ins.group(capstone.CS_GRP_JUMP):
            if ins.operands and ins.operands[0].type==capstone.x86.X86_OP_IMM and not start<=ins.operands[0].imm<end:
                mask[position+ins.imm_offset:position+ins.imm_offset+ins.imm_size]=bytes(ins.imm_size)
    for pos,n in zero:mask[pos:pos+n]=bytes(n)
    assert end_seen==end and mask[:12]==b'\xff'*12
    normalized=bytes(b&m for b,m in zip(body,mask))
    return {'anchor':body[:12].hex(),'normalized_sha256':hashlib.sha256(normalized).hexdigest(),
            'mask':base64.b85encode(zlib.compress(mask,9)).decode('ascii')}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('msvc','pgo','pokedinner','selevet'):parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args();root=Path(__file__).resolve().parents[1];patterns=[]
    specs=[('msvc',0x459c40,0x459f08,0x459c40,'entry','msvc','48895c2410',0x459e60),
           ('pgo',0x1f560,0x1f7e7,0x1f6ea,'inline','gnu','488d8c2480010000',0x1f68f),
           ('pokedinner',0x2fe4d0,0x2fe6d9,0x2fe638,'inline-pokedinner','msvc-read9','4c8d7dc04c89f9',0x2fe620),
           ('selevet',0x191ef50,0x191f0e6,0x191f0df,'inline-selevet','msvc-read9','4c8bbdb0030000',0x191f06f)]
    cs=capstone.Cs(capstone.CS_ARCH_X86,capstone.CS_MODE_64);cs.detail=True
    for name,start,end,hook,kind,abi,expected,metadata_call in specs:
        pe=pefile.PE(str(getattr(args,name)))
        assert pe.get_data(hook,len(bytes.fromhex(expected))).hex()==expected
        pattern=signature(cs,pe,start,end)
        load_call=next(cs.disasm(pe.get_data(metadata_call,5),metadata_call))
        assert load_call.mnemonic=='call' and load_call.operands[0].type==capstone.x86.X86_OP_IMM
        meta=load_call.operands[0].imm;instructions=list(cs.disasm(pe.get_data(meta,256),meta))
        sizes=[ins for ins in instructions if ins.mnemonic=='call' and ins.operands[0].type==capstone.x86.X86_OP_MEM
               and ins.operands[0].mem.base==capstone.x86.X86_REG_RAX and ins.operands[0].mem.disp in (24,32)]
        reads=[]
        for i,ins in enumerate(instructions):
            if ins.mnemonic!='call' or ins.operands[0].type!=capstone.x86.X86_OP_MEM or ins.operands[0].mem.base!=capstone.x86.X86_REG_RAX:continue
            if any(p.mnemonic=='mov' and len(p.operands)==2 and p.operands[0].type==capstone.x86.X86_OP_REG
                   and p.operands[0].reg==capstone.x86.X86_REG_R8D and p.operands[1].type==capstone.x86.X86_OP_IMM
                   and p.operands[1].imm==128 for p in instructions[max(0,i-4):i]):reads.append(ins)
        assert sizes and reads
        size_call,read_call=sizes[0],reads[0]
        size_pos=size_call.address-meta+size_call.disp_offset;read_pos=read_call.address-meta+read_call.disp_offset
        assert size_call.disp_size==read_call.disp_size==1
        reader=signature(cs,pe,meta,read_call.address+read_call.size,((size_pos,1),(read_pos,1)))
        reader.update(size_disp_offset=size_pos,read_disp_offset=read_pos)
        pattern.update(name=name,abi=abi,kind=kind,hook_delta=hook-start,expected=expected,
                       metadata_call_delta=metadata_call-start,reader=reader)
        if name=='selevet':pattern['preserve_duplicate_unwind']=True
        patterns.append(pattern);pe.close()
    (root/'src/emulator_patterns.py').write_text('# Generated from reviewed loader and metadata-reader fingerprints. SPDX-License-Identifier: MIT\n'
                                               'PATTERNS = '+repr(patterns)+'\n',encoding='utf-8')

if __name__=='__main__':main()
