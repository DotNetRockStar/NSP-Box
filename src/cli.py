"""NSP Box command line. Runs on Windows, macOS and Linux without loading Tk.

    python src/cli.py scan  "My Game"
    python src/cli.py build "My Game" -o "Packed/My Game.nsp"
    python src/cli.py dlc   "My Game/dlc" -o "Packed/DLC.nsp"
    python src/cli.py nup pack "My Game"
    python src/cli.py nup inspect "My Game.nup" --verify

The frozen app accepts the same commands (`NSP-Box build ...`); started without
a command it opens the GUI. The original `--package ...` and
`--nup-operation ...` forms remain supported unchanged.
"""
from pathlib import Path
import argparse, json, os, re, sys, threading, time, traceback

import engine
from artwork import ArtworkSelection

COMMANDS = ('scan', 'build', 'dlc', 'nup', 'version')
NUP_INCLUDE = {'base': (0,), 'updates': (1,), 'dlc': (2, 3)}

# ---------------------------------------------------------------------------
# Output helpers
# ---------------------------------------------------------------------------
class Progress:
    """Progress on stderr: one rewritten line on a terminal, stage changes otherwise."""
    def __init__(self, quiet=False, stream=None):
        self.stream = stream if stream is not None else sys.stderr
        self.quiet = quiet or self.stream is None
        self.tty = bool(getattr(self.stream, 'isatty', lambda: False)())
        self.stage = None;self.last = 0.0;self.width = 0
    def __call__(self, stage, value=0):
        if self.quiet:return
        now = time.monotonic()
        if self.tty:
            if stage == self.stage and now-self.last < .1 and value < 100:return
            text = f'{stage} · {max(0, min(100, value)):5.1f}%'
            self.stream.write('\r'+text.ljust(self.width));self.stream.flush()
            self.width = len(text)
        elif stage != self.stage:
            self.stream.write(f'[{max(0, min(100, value)):5.1f}%] {stage}\n');self.stream.flush()
        self.stage = stage;self.last = now
    def done(self):
        if self.tty and not self.quiet and self.width:
            self.stream.write('\r'+' '*self.width+'\r');self.stream.flush()
        self.width = 0

def safe_filename(name):
    """Filename valid on Windows, macOS and Linux (same rule as the GUI's default name)."""
    return re.sub(r'[<>:"/\\|?*\x00-\x1f]', '_', engine.clean_title(name)).rstrip('. ')[:110] or 'Game'

def human_size(n):
    for unit in ('B', 'KiB', 'MiB', 'GiB', 'TiB'):
        if abs(n) < 1024 or unit == 'TiB':return f'{n:.1f} {unit}' if unit != 'B' else f'{n} B'
        n /= 1024

def summary(result):
    """Short human-readable lines for a result dict; --json prints everything."""
    lines = []
    for key, label in (('output', 'Output'), ('title', 'Title'), ('title_id', 'Title ID'), ('size', 'Size'),
                       ('sha256', 'SHA-256'), ('verified', 'Verified'), ('packages', 'Packages'),
                       ('compression_ratio', 'Compression ratio')):
        if key in result and result[key] is not None:
            value = human_size(result[key]) if key == 'size' else result[key]
            lines.append(f'{label + ":":<19}{value}')
    if result.get('ignored_os_metadata'):
        lines.append(f'{"Ignored:":<19}{len(result["ignored_os_metadata"])} macOS metadata file(s) (.DS_Store / ._*)')
    seconds = result.get('seconds') or (result.get('timings_seconds') or {}).get('total')
    if seconds:lines.append(f'{"Time:":<19}{seconds:.1f} s')
    return '\n'.join(lines)

def emit(result, as_json, text=None):
    if sys.stdout is None:return
    if as_json:print(json.dumps(result, indent=2, default=str))
    else:print(text if text is not None else summary(result))

def run_cancellable(call, progress):
    """Run `call(notify, cancel)` on a worker so Ctrl+C uses the normal cancellation
    path: partial outputs are removed exactly as when Cancel is clicked in the GUI."""
    cancel = threading.Event();box = {}
    def work():
        try:box['result'] = call(progress, cancel)
        except BaseException as error:box['error'] = error
    worker = threading.Thread(target=work, name='nspbox-cli', daemon=True);worker.start()
    try:
        while worker.is_alive():worker.join(.2)
    except KeyboardInterrupt:
        cancel.set();progress.done()
        if progress.stream:progress.stream.write('Cancelling and removing partial output…\n')
        worker.join()
        raise
    finally:progress.done()
    if 'error' in box:raise box['error']
    return box['result']

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
def cmd_scan(args, progress):
    if args.dlc:
        import dlc
        found = dlc.find_snapshots(args.folder, args.title_id)
        rows = [{'index': i, 'kind': 'dlc', 'title_id': f'{s.title_id:016X}', 'base_title_id': f'{s.base_id:016X}',
                 'version': s.version, 'label': s.label, 'path': str(s.root)} for i, s in enumerate(found)]
        skipped = []
    else:
        found, skipped = engine.find_snapshots(args.folder)
        rows = [{'index': i, 'kind': 'game', 'title_id': f'{s.title_id:016X}', 'version': s.version, 'label': s.label,
                 'title': s.title, 'control_nacp': str(s.nacp) if s.nacp else None, 'path': str(s.root)}
                for i, s in enumerate(found)]
    result = {'folder': str(Path(args.folder).absolute()), 'snapshots': rows, 'skipped_dlc_folders': [str(p) for p in skipped]}
    lines = []
    for r in rows:
        name = r.get('title') or ''
        lines.append(f'[{r["index"]}] {r["title_id"]}  v{r["version"]:<10} {r["label"]}' + (f'  ·  {name}' if name else ''))
    if skipped:lines.append(f'Skipped {len(skipped)} DLC folder(s); package them with the "dlc" command.')
    emit(result, args.json, '\n'.join(lines))
    return result

def _artwork(args):
    if (args.artwork_fit or args.artwork_crop) and not args.artwork:
        raise ValueError('Choose --artwork before specifying its crop mode.')
    if not args.artwork:return None
    return ArtworkSelection(args.artwork, tuple(args.artwork_crop) if args.artwork_crop else None, args.artwork_fit)

def cmd_build(args, progress):
    snapshots, _ = engine.find_snapshots(args.folder)
    if not 0 <= args.snapshot < len(snapshots):
        raise ValueError(f'Snapshot index is out of range (found {len(snapshots)}; see "scan").')
    s = snapshots[args.snapshot];artwork = _artwork(args)
    output = args.output or Path(args.folder).absolute().parent/(safe_filename(args.title or s.title)+'.nsp')
    display = args.display_version or ('dump-'+str(s.version) if s.version else 'Snapshot')
    result = run_cancellable(lambda notify, cancel: engine.build(
        s, output, args.title or s.title, display, artwork, not args.no_verify, notify, cancel,
        package_folder=args.package_folder), progress)
    emit(result, args.json);return result

def cmd_dlc(args, progress):
    import dlc
    snapshots = dlc.find_snapshots(args.folder, args.title_id)
    if not 0 <= args.snapshot < len(snapshots):
        raise ValueError(f'DLC snapshot index is out of range (found {len(snapshots)}; see "scan --dlc").')
    s = snapshots[args.snapshot]
    if args.dlc_version is not None:s = dlc.DlcSnapshot(s.root, s.title_id, dlc.parse_version(args.dlc_version), s.label)
    output = args.output or Path(args.folder).absolute().parent/f'DLC [{s.title_id:016X}] v{s.version}.nsp'
    result = run_cancellable(lambda notify, cancel: dlc.build(
        s, output, 'nsp', not args.no_verify, args.base_game, notify, cancel), progress)
    emit(result, args.json);return result

def _kinds(value):
    if value is None:return None
    kinds = set()
    for name in value.split(','):
        name = name.strip().lower()
        if name not in NUP_INCLUDE:raise ValueError('--include accepts base, updates and dlc (comma separated).')
        kinds.update(NUP_INCLUDE[name])
    return kinds

def cmd_nup(args, progress):
    import nup_tools as tools
    from nup_format import PRESETS, Archive
    source = Path(args.input).absolute();kinds = _kinds(getattr(args, 'include', None))
    op = args.nup_command;level = PRESETS[getattr(args, 'preset', 'Balanced')]
    if op in ('inspect', 'verify'):
        result = run_cancellable(lambda notify, cancel: tools.inspect(
            source, verify=op == 'verify' or args.verify, notify=notify, cancel=cancel), progress)
        emit(result, args.json, json.dumps(result, indent=2, default=str));return result
    if args.output is None:
        if op == 'pack':
            folder = source.parent if source.name.lower() in ('exefs', 'romfs') else source
            output = tools.beside_source(folder, folder.name, '.nup')
        else:output = tools.beside_source(source, source.stem, {'from-nsp': '.nup', 'extract': '-extracted', 'to-nsp': '-NSP'}[op])
    else:output = Path(args.output)
    def call(notify, cancel):
        common = {'notify': notify, 'cancel': cancel}
        if op == 'pack':
            artwork = None
            if args.artwork or args.artwork_fit or args.artwork_crop:artwork = engine.artwork_bytes(_artwork(args))
            return tools.pack_folder(source, output, latest_snapshot=args.latest_snapshot, include_kinds=kinds,
                                     title=args.title or '', artwork=artwork, level=level,
                                     large_raw=args.large_files_raw, verify=not args.no_verify, **common)
        if op == 'from-nsp':
            return tools.nsp_to_nup(source, output, include_kinds=kinds, level=level,
                                    large_raw=args.large_files_raw, verify=not args.no_verify, **common)
        if op == 'extract':
            selection = None
            if args.package is not None:selection = args.package
            elif kinds is not None:
                with Archive(source, cancel) as archive:
                    selection = [i for i, p in enumerate(archive.packages) if p.kind in kinds]
            return tools.extract(source, output, selection=selection, **common)
        if op == 'to-nsp':
            if args.package is not None and len(args.package) != 1:raise ValueError('to-nsp converts one --package index, or all when omitted.')
            return tools.nup_to_nsp(source, output, selection=args.package[0] if args.package else None,
                                    include_kinds=kinds, verify=not args.no_verify, **common)
        raise ValueError('Unknown NUP command.')
    result = run_cancellable(call, progress)
    emit(result, args.json);return result

# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------
def _common(parser):
    parser.add_argument('--json', action='store_true', help='Print the full result as JSON on stdout.')
    parser.add_argument('-q', '--quiet', action='store_true', help='Hide progress (errors are still shown).')

def _artwork_options(parser):
    parser.add_argument('--artwork', type=Path, help='Cover artwork (PNG, JPG, WEBP, GIF, TIFF, ICO, ICNS, AVIF …). Center-cropped by default.')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--artwork-fit', action='store_true', help='Keep the whole image instead of center-cropping it.')
    group.add_argument('--artwork-crop', nargs=4, type=float, metavar=('LEFT', 'TOP', 'RIGHT', 'BOTTOM'),
                       help='Square crop box in normalized 0–1 coordinates of the EXIF-oriented image.')

def parser():
    root = argparse.ArgumentParser(prog='nspbox', description='NSP Box: package extracted Switch 2 games, DLC and NUP archives.',
                                   epilog='Run "nspbox <command> -h" for command options. Without a command the app opens its window.')
    root.add_argument('--version', action='version', version='NSP Box '+engine.VERSION)
    sub = root.add_subparsers(dest='command', metavar='<command>')

    p = sub.add_parser('scan', help='List the game snapshots (or DLC) found in a folder.')
    p.add_argument('folder', type=Path);p.add_argument('--dlc', action='store_true', help='Look for extracted DLC instead of games.')
    p.add_argument('--title-id', help='DLC title ID when absent from folder names (with --dlc).');_common(p)

    p = sub.add_parser('build', help='Package a complete ExeFS/RomFS game snapshot as NSP.')
    p.add_argument('folder', type=Path, help='Snapshot folder, or the main game folder containing several.')
    p.add_argument('-o', '--output', type=Path, help='Output .nsp (default: "<title>.nsp" beside the folder).')
    p.add_argument('-s', '--snapshot', type=int, default=0, help='Index from "scan" (default 0: highest version).')
    p.add_argument('--title', help='Game title when the dump has no control.nacp title.')
    p.add_argument('--display-version', help='NACP display version label (max 15 UTF-8 bytes).')
    p.add_argument('--package-folder', action=argparse.BooleanOptionalAction, default=True,
                   help='Save in a folder with main.npdm and a JSON report (default). --no-package-folder saves only the NSP.')
    p.add_argument('--no-verify', action='store_true', help='Skip the full readback verification.')
    _artwork_options(p);_common(p)

    p = sub.add_parser('dlc', help='Package extracted DLC RomFS as NSP.')
    p.add_argument('folder', type=Path);p.add_argument('-o', '--output', type=Path, help='Output .nsp (default: beside the folder).')
    p.add_argument('-s', '--snapshot', type=int, default=0, help='Index from "scan --dlc".')
    p.add_argument('--title-id', help='Original DLC title ID when absent from folder names.')
    p.add_argument('--dlc-version', help='Numeric DLC version; otherwise detected from the version folder.')
    p.add_argument('--base-game', type=Path, help='Optional base-game NSP for DLC mapping validation.')
    p.add_argument('--no-verify', action='store_true', help='Skip the full readback verification.');_common(p)

    p = sub.add_parser('nup', help='NUP archive tools: pack, from-nsp, extract, to-nsp, inspect, verify.')
    nup = p.add_subparsers(dest='nup_command', metavar='<operation>', required=True)
    def compression(q):
        q.add_argument('--preset', choices=('Fast', 'Balanced', 'Smaller'), default='Balanced')
        q.add_argument('--large-files-raw', action=argparse.BooleanOptionalAction, default=True,
                       help='Store very large already-compressed files without recompressing (default on).')
    def include(q):
        q.add_argument('--include', metavar='KINDS', help='Comma list of base, updates, dlc (default: all present).')
    q = nup.add_parser('pack', help='Folder → NUP.');q.add_argument('input', type=Path)
    q.add_argument('-o', '--output', type=Path, help='Output .nup (default: beside the source, numbered if taken).')
    q.add_argument('--latest-snapshot', action=argparse.BooleanOptionalAction, default=True,
                   help='Keep one latest game snapshot (default); --no-latest-snapshot archives every version.')
    q.add_argument('--title', help='Custom title for the game record.')
    q.add_argument('--no-verify', action='store_true');compression(q);include(q);_artwork_options(q);_common(q)
    q = nup.add_parser('from-nsp', help='NSP → NUP.');q.add_argument('input', type=Path)
    q.add_argument('-o', '--output', type=Path);q.add_argument('--no-verify', action='store_true');compression(q);include(q);_common(q)
    q = nup.add_parser('extract', help='NUP → folder.');q.add_argument('input', type=Path)
    q.add_argument('-o', '--output', type=Path, help='New folder (default: "<name>-extracted" beside the archive).')
    q.add_argument('--package', type=int, nargs='+', help='Package indexes from "nup inspect" (default: all).');include(q);_common(q)
    q = nup.add_parser('to-nsp', help='NUP → NSP (game + latest update, DLC as separate NSPs).');q.add_argument('input', type=Path)
    q.add_argument('-o', '--output', type=Path, help='.nsp for one package, or a new folder for several.')
    q.add_argument('--package', type=int, nargs=1, help='Convert only this package index.')
    q.add_argument('--no-verify', action='store_true');include(q);_common(q)
    q = nup.add_parser('inspect', help='Show archive contents.');q.add_argument('input', type=Path)
    q.add_argument('--verify', action='store_true', help='Also verify every block.');_common(q)
    q = nup.add_parser('verify', help='Verify archive integrity.');q.add_argument('input', type=Path);_common(q)

    sub.add_parser('version', help='Print the app version.')
    return root

# ---------------------------------------------------------------------------
# Entry points
# ---------------------------------------------------------------------------
def wants_cli(argv):
    """True when argv asks for a command-line operation instead of the GUI."""
    if not argv:return False
    return (argv[0] in COMMANDS or argv[0] in ('-h', '--help', '--version')
            or '--package' in argv or '--nup-operation' in argv)

def _utf8_pipes():
    """Pipes/redirects on Windows default to the ANSI code page; write UTF-8 so
    titles and help text never raise UnicodeEncodeError."""
    for stream in (sys.stdout, sys.stderr):
        try:
            if stream is not None and not stream.isatty() and (stream.encoding or '').lower().replace('-', '') != 'utf8':
                stream.reconfigure(encoding='utf-8', errors='replace')
        except (AttributeError, ValueError, OSError):
            pass

def run(argv):
    """Execute a CLI invocation and return its exit code."""
    _utf8_pipes()
    if '--nup-operation' in argv:
        import nup_cli
        return nup_cli.main(argv)
    if '--package' in argv and (not argv or argv[0] not in COMMANDS):return legacy_main(argv)
    args = parser().parse_args(argv)
    if args.command in (None, 'version'):
        if args.command is None:parser().print_help()
        else:print('NSP Box '+engine.VERSION)
        return 0
    progress = Progress(getattr(args, 'quiet', False))
    handler = {'scan': cmd_scan, 'build': cmd_build, 'dlc': cmd_dlc, 'nup': cmd_nup}[args.command]
    try:
        handler(args, progress);return 0
    except KeyboardInterrupt:
        if sys.stderr:print('Cancelled. Partial output was removed; your source files are unchanged.', file=sys.stderr)
        return 130
    except InterruptedError:
        if sys.stderr:print('Cancelled.', file=sys.stderr)
        return 130
    except Exception as error:
        if getattr(args, 'json', False) and sys.stdout:print(json.dumps({'error': str(error)}, indent=2))
        if sys.stderr:
            print(f'error: {error}', file=sys.stderr)
            if os.environ.get('NSPBOX_DEBUG'):traceback.print_exc()
        return 1

def main(argv=None):
    argv = sys.argv[1:] if argv is None else list(argv)
    if not wants_cli(argv) and argv:
        # GUI-only options (--folder/--artwork) need the app window.
        print('Run "app.py" for the GUI, or see "nspbox -h" for commands.', file=sys.stderr);return 2
    return run(argv)

# ---------------------------------------------------------------------------
# Original single-command interface (kept for compatibility).
# ---------------------------------------------------------------------------
def legacy_main(argv):
    try:
        result = package_cli(argv);print(json.dumps(result, indent=2));return 0
    except Exception as e:
        if sys.stderr:print(str(e), file=sys.stderr)
        # Windowed EXEs have no console; retain a diagnostic next to the requested output.
        try:
            if '--package-folder' in argv:
                dest = Path(argv[argv.index('--output')+1]);dest.with_suffix('.error.txt').write_text(traceback.format_exc(), encoding='utf-8')
        except Exception:pass
        return 1

def package_cli(argv):
    """Original `--package` interface (JSON result), used by the frozen smoke tests."""
    parser=argparse.ArgumentParser(description='Package a complete extracted ExeFS/RomFS snapshot into NSP.')
    parser.add_argument('--package',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--artwork',type=Path);parser.add_argument('--title');parser.add_argument('--snapshot',type=int,default=0)
    parser.add_argument('--display-version');parser.add_argument('--skip-verification',action='store_true')
    parser.add_argument('--format',choices=('nsp',),help=argparse.SUPPRESS)
    parser.add_argument('--package-folder',action=argparse.BooleanOptionalAction,default=True,help='Create a folder including metadata and a JSON report (default). Use --no-package-folder for only the NSP.')
    parser.add_argument('--dlc',action='store_true',help='Package extracted DLC RomFS instead of a complete game; always single-file output.')
    parser.add_argument('--dlc-title-id',help='Original DLC title ID when it is absent from folder names.')
    parser.add_argument('--dlc-version',help='Numeric DLC version; otherwise detected from the version folder.')
    parser.add_argument('--base-game',type=Path,help='Optional base-game plaintext NSP for DLC mapping validation.')
    art_options=parser.add_mutually_exclusive_group()
    art_options.add_argument('--artwork-fit',action='store_true')
    art_options.add_argument('--artwork-crop',nargs=4,type=float,metavar=('LEFT','TOP','RIGHT','BOTTOM'))
    args=parser.parse_args(argv)
    if args.dlc:
        import dlc
        if args.artwork or args.artwork_fit or args.artwork_crop:
            raise ValueError('DLC is data-only and does not use game cover artwork.')
        snapshots=dlc.find_snapshots(args.package,args.dlc_title_id)
        if not 0<=args.snapshot<len(snapshots):raise ValueError('DLC snapshot index is out of range.')
        s=snapshots[args.snapshot]
        if args.dlc_version is not None:s=dlc.DlcSnapshot(s.root,s.title_id,dlc.parse_version(args.dlc_version),s.label)
        return dlc.build(s,args.output,args.format,not args.skip_verification,args.base_game)
    if args.dlc_title_id or args.dlc_version is not None or args.base_game:
        raise ValueError('DLC options require --dlc.')
    snapshots,_=engine.find_snapshots(args.package)
    if not 0<=args.snapshot<len(snapshots):raise ValueError('Snapshot index is out of range.')
    s=snapshots[args.snapshot]
    if (args.artwork_fit or args.artwork_crop) and not args.artwork:raise ValueError('Choose --artwork before specifying its crop mode.')
    artwork=ArtworkSelection(args.artwork,tuple(args.artwork_crop) if args.artwork_crop else None,args.artwork_fit) if args.artwork else None
    result=engine.build(s,args.output,args.title or s.title,args.display_version or ('dump-'+str(s.version) if s.version else 'Snapshot'),artwork,not args.skip_verification,output_format=args.format,package_folder=args.package_folder)
    return result

if __name__ == '__main__':
    sys.exit(main())
