"""Optional local automation entry point, used by frozen NUP smoke checks."""
from pathlib import Path
import argparse,json,sys
import nup_tools as tools
from nup_format import PRESETS

def main(argv):
    parser=argparse.ArgumentParser(description='NSP Box NUP tools (experimental).')
    parser.add_argument('--nup-operation',required=True,choices=('pack','nsp-to-nup','extract','nup-to-nsp','inspect','verify'))
    parser.add_argument('--input',type=Path,required=True);parser.add_argument('--output',type=Path)
    parser.add_argument('--preset',choices=tuple(PRESETS),default='Balanced')
    parser.add_argument('--large-files-raw',action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument('--latest-snapshot',action=argparse.BooleanOptionalAction,default=True,help='Folder packing: keep one latest game snapshot; --no-latest-snapshot archives all game versions.')
    parser.add_argument('--verify',action=argparse.BooleanOptionalAction,default=True)
    parser.add_argument('--package-index',type=int);parser.add_argument('--result-json',type=Path)
    args=parser.parse_args(argv)
    try:
        op=args.nup_operation
        if op in ('pack','nsp-to-nup','extract','nup-to-nsp') and args.output is None:raise ValueError('Choose --output.')
        if op in ('pack','nsp-to-nup'):
            fn=tools.pack_folder if op=='pack' else tools.nsp_to_nup
            extra={'latest_snapshot':args.latest_snapshot} if op=='pack' else {}
            result=fn(args.input,args.output,level=PRESETS[args.preset],large_raw=args.large_files_raw,verify=args.verify,**extra)
        elif op=='extract':result=tools.extract(args.input,args.output,selection=None if args.package_index is None else [args.package_index])
        elif op=='nup-to-nsp':result=tools.nup_to_nsp(args.input,args.output,selection=args.package_index,verify=args.verify)
        else:result=tools.inspect(args.input,verify=op=='verify')
        code=0
    except Exception as error:result={'error':str(error)};code=1
    if args.result_json:
        with args.result_json.open('x',encoding='utf-8') as f:json.dump(result,f,indent=2)
    if sys.stdout:print(json.dumps(result,indent=2))
    return code
