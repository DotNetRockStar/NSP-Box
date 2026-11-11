"""DLC round trips, identity mapping, cleanup and real-widget integration."""
from pathlib import Path
import mmap, struct, sys, tempfile, threading, time, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
import dlc, engine, container_format as fmt, verify_format as reader
from cli import package_cli as cli
try:
    from app import App
except ImportError:  # Python built without Tk: the GUI test is skipped, CLI tests still run.
    App=None

BASE=0x0400111122220000
DLC=BASE+0x1001


class DlcTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='dlc-',dir=scratch);self.root=Path(self.temp.name)
        self.source=self.root/'dlc'/f'{DLC:016x}'/'65536'
        (self.source/'romfs/日本語').mkdir(parents=True)
        (self.source/'romfs/日本語/data.bin').write_bytes(bytes(range(256))*257)
        (self.source/'romfs/empty').write_bytes(b'')
        self.snapshot=dlc.find_snapshots(self.root/'dlc')[0]
        self.output=self.root/'DLC.nsp'
    def tearDown(self):
        fmt.configure();reader.checkpoint=lambda:None;self.temp.cleanup()
    def base(self):
        root=self.root/'game';(root/'exefs').mkdir(parents=True);(root/'romfs').mkdir()
        npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80)
        npdm[0x80:0x84]=b'ACI0';struct.pack_into('<Q',npdm,0x90,BASE)
        (root/'exefs/main.npdm').write_bytes(npdm);(root/'exefs/main').write_bytes(b'NSO0'+bytes(256))
        (root/'romfs/data').write_bytes(b'Base game')
        s=engine.find_snapshots(root)[0][0];dest=self.root/'Base.nsp';engine.build(s,dest,'Sample Game','1.0')
        return dest
    def test_data_only_nsp_round_trip(self):
        for kind in ('nsp',):
            output=self.output.with_suffix('.'+kind)
            result=dlc.build(self.snapshot,output)
            self.assertTrue(result['verified']);self.assertEqual(result['source_file_count'],2)
            self.assertEqual(result['base_title_id'],f'{BASE:016X}')
            self.assertEqual(dlc.verify(output,self.snapshot,dlc.inventory(self.snapshot)),2)
            with output.open('rb') as f,mmap.mmap(f.fileno(),0,access=mmap.ACCESS_READ) as m:
                files,_=dlc.container_files(reader.Region(m))
                self.assertEqual({b[0x205] for b in files.values()},{1,4})
            self.assertFalse((output.parent/'main.npdm').exists())
            self.assertFalse(output.with_suffix(output.suffix+'.report.json').exists())
    def test_xci_output_is_rejected(self):
        with self.assertRaisesRegex(ValueError,'NSP Box supports .nsp output only'):
            dlc.build(self.snapshot,self.output.with_suffix('.xci'))
        self.assertFalse(self.output.with_suffix('.xci').exists())
    def test_scan_nested_and_direct_and_manual_identity(self):
        self.assertEqual(self.snapshot.title_id,DLC);self.assertEqual(self.snapshot.version,65536)
        self.assertEqual(dlc.find_snapshots(self.source/'romfs')[0].title_id,DLC)
        other=self.root/'dlc'/f'{DLC+1:016x}'/'0'/'romfs';other.mkdir(parents=True)
        self.assertEqual(len(dlc.find_snapshots(self.root/'dlc',f'{DLC:016X}')),2)
        plain=self.root/'plain';(plain/'romfs').mkdir(parents=True)
        with self.assertRaisesRegex(ValueError,'title ID'):dlc.find_snapshots(plain)
        self.assertEqual(dlc.find_snapshots(plain,f'{DLC:016X}')[0].title_id,DLC)
        with self.assertRaisesRegex(ValueError,'differs'):dlc.find_snapshots(self.source,f'{DLC+1:016X}')
    def test_reject_game_and_update_ids_and_bad_versions(self):
        for tid in (BASE,BASE+0x800,BASE+0x1801,-1,1<<64):
            with self.assertRaises(ValueError):dlc.parse_id(tid)
        for version in ('-1','v1','4294967296','١'):
            with self.assertRaises(ValueError):dlc.parse_version(version)
        (self.source/'exefs').mkdir();(self.source/'exefs/main').write_bytes(b'NSO0')
        with self.assertRaisesRegex(ValueError,'Game tab'):dlc.find_snapshots(self.source)
    def test_base_mapping_checked_without_changing_base(self):
        base=self.base();before=reader.file_digest(base);info=dlc.base_game_info(base)
        self.assertEqual(info['title_id'],BASE);self.assertEqual(info['dlc_base_id'],BASE+0x1000)
        self.assertTrue(dlc.build(self.snapshot,self.output,base_game=base)['base_validated'])
        self.assertEqual(reader.file_digest(base),before)
        with self.assertRaisesRegex(ValueError,'does not match'):
            dlc.validate_base(self.snapshot,{'title_id':BASE+0x2000,'dlc_base_id':BASE+0x3000})
    def test_no_overwrite_cancel_source_change_and_output_inside_source(self):
        self.output.write_bytes(b'keep')
        with self.assertRaises(FileExistsError):dlc.build(self.snapshot,self.output)
        self.assertEqual(self.output.read_bytes(),b'keep');self.output.unlink()
        event=threading.Event()
        def cancel(stage,value):
            if stage.startswith('Writing'):event.set()
        with self.assertRaises(InterruptedError):dlc.build(self.snapshot,self.output,notify=cancel,cancel=event)
        self.assertFalse(self.output.exists());self.assertEqual(list(self.root.glob('*.partial')),[])
        fmt.configure()
        def change(stage,value):
            if stage=='Writing DLC NSP':(self.source/'romfs/empty').write_bytes(b'changed')
        with self.assertRaises((ValueError,AssertionError,OSError)):dlc.build(self.snapshot,self.output,notify=change)
        self.assertFalse(self.output.exists());self.assertEqual(list(self.root.glob('*.partial')),[])
        with self.assertRaisesRegex(ValueError,'outside'):dlc.build(self.snapshot,self.source/'inside.nsp')
    def test_corrupt_content_detected(self):
        dlc.build(self.snapshot,self.output)
        with self.output.open('r+b') as f:f.seek(-100,2);f.write(b'bad corruption')
        with self.assertRaises((AssertionError,ValueError)):dlc.verify(self.output,self.snapshot,dlc.inventory(self.snapshot))
    def test_cli_and_version_override(self):
        result=cli(['--dlc','--package',str(self.root/'dlc'),'--output',str(self.output),'--dlc-version','131072'])
        self.assertEqual(result['dlc_version'],131072);self.assertEqual(result['output_format'],'NSP')
    def test_exclusive_commit_race_preserves_other_output(self):
        def race(stage,value):
            if stage=='Comparing DLC source files' and not self.output.exists():self.output.write_bytes(b'other writer')
        with self.assertRaises(FileExistsError):dlc.build(self.snapshot,self.output,notify=race)
        self.assertEqual(self.output.read_bytes(),b'other writer');self.assertEqual(list(self.root.glob('*.partial')),[])

    @unittest.skipIf(App is None,'Tk is not available')
    def test_tab_scan_build_switch_and_layout(self):
        app=App(show_startup=False,preferences_path=self.root/'prefs.json');errors=[]
        app.report_callback_exception=lambda *a:errors.append(a)
        def pump_until(condition,timeout=8):
            end=time.monotonic()+timeout
            while not condition() and time.monotonic()<end:app.update();time.sleep(.01)
            self.assertTrue(condition())
        try:
            app.update();app.show_tab('dlc');app.update();panel=app.dlc_panel
            self.assertEqual(app.active_tab,'dlc');self.assertTrue(panel.winfo_ismapped())
            app.receive_drop([str(self.root/'dlc')]);pump_until(lambda:len(panel.snapshots)==1 and not panel.busy)
            self.assertEqual(panel.title_id.get(),f'{DLC:016X}')
            panel.output.set(str(self.output));panel.start();app.show_tab('game')
            self.assertEqual(app.active_tab,'dlc')
            pump_until(lambda:not panel.busy);self.assertTrue(self.output.exists())
            self.assertIn('ready',panel.status.get())
            for geometry in ('1160x880','1010x830'):
                app.geometry(geometry);app.update()
                for widget in (panel.folder_entry,panel.base_entry,panel.output_entry,panel.verify_check,panel.build_button):
                    self.assertGreater(widget.winfo_height(),20)
                    self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.winfo_rooty()+app.winfo_height())
            app.show_tab('game');app.update();self.assertTrue(app.content_area.winfo_ismapped())
            self.assertFalse(panel.winfo_ismapped());self.assertEqual(errors,[])
        finally:app.close()


if __name__=='__main__':unittest.main()
