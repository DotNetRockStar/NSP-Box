from pathlib import Path
import sys,tempfile,time,unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
from app import App
from nup_panel import OPERATIONS
from test_nup import snapshot

class NupInterfaceTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch);self.root=Path(self.tmp.name)
        self.game=snapshot(self.root/'Game',{'data':bytes(100000)})
        self.app=App(show_startup=False,preferences_path=self.root/'prefs.json');self.errors=[]
        self.app.report_callback_exception=lambda *a:self.errors.append(a);self.app.show_tab('nup');self.pump(.3)
    def tearDown(self):self.app.close();self.tmp.cleanup()
    def pump(self,seconds=.04):
        end=time.monotonic()+seconds
        while time.monotonic()<end:self.app.update();time.sleep(.005)
    def until(self,condition):
        end=time.monotonic()+15
        while not condition() and time.monotonic()<end:self.pump()
        self.assertTrue(condition())
    def test_drop_pack_inspect_extract_and_old_tabs(self):
        app=self.app;p=app.nup_panel;self.assertEqual(p.preset.get(),'Balanced');self.assertTrue(p.large_raw.get());self.assertTrue(p.latest_snapshot.get())
        app.receive_drop([str(self.game)]);self.until(lambda:not p.busy);self.assertEqual(len(p.catalog),1)
        out=self.root/'Game.nup';p.start();self.assertTrue(p.busy);app.show_tab('game');self.assertEqual(app.active_tab,'nup')
        self.until(lambda:not p.busy);self.assertTrue(out.exists());self.assertIn('Bytes saved',p.report.get('1.0','end'))
        p.operation.set(OPERATIONS[4]);p.changed();app.receive_drop([str(out)]);self.until(lambda:not p.busy);p.start();self.until(lambda:not p.busy)
        self.assertIn('Integrity: verified',p.report.get('1.0','end'))
        p.operation.set(OPERATIONS[2]);p.changed();p.scan();self.until(lambda:not p.busy)
        destination=self.root/'Game-extracted';p.start();self.until(lambda:not p.busy)
        self.assertEqual((destination/'base/exefs/main.npdm').read_bytes(),(self.game/'exefs/main.npdm').read_bytes())
        app.show_tab('game');self.pump();self.assertTrue(app.content_area.winfo_ismapped());app.show_tab('dlc');self.pump();self.assertTrue(app.dlc_panel.winfo_ismapped())
        self.assertFalse(self.errors)

    def test_checkbox_filtered_extraction_without_save_prompt(self):
        import nup_tools as nt
        p=self.app.nup_panel
        bundle=self.root/'Bundle';snapshot(bundle/'base',{'base':b'base'})
        addon=bundle/'dlc/0400111122221001/romfs';addon.mkdir(parents=True);(addon/'addon').write_bytes(b'dlc')
        archive=self.root/'Bundle.nup';nt.pack_folder(bundle,archive,latest_snapshot=False)
        p.operation.set(OPERATIONS[2]);p.input.set(str(archive));p.changed()
        p.scan();self.until(lambda:not p.busy)
        p.includes['Base'].set(False);p.includes['Updates'].set(False)
        with patch('nup_panel.filedialog.askdirectory',side_effect=AssertionError('Must not prompt')):
            p.start();self.until(lambda:not p.busy)
        output=self.root/'Bundle-extracted';self.assertTrue(output.is_dir(),p.status.get())
        self.assertFalse((output/'base').exists())
        self.assertEqual(list(output.rglob('addon'))[0].read_bytes(),b'dlc')
        self.assertFalse(self.errors)
    def test_minimum_layout_and_operation_controls(self):
        app=self.app;p=app.nup_panel;app.geometry('1010x830');self.pump(.2)
        self.assertFalse(p.include_area.winfo_ismapped());self.assertFalse(p.snapshot_check.winfo_ismapped())
        for widget in (p.start_button,p.cancel_button,p.open_button,p.input_entry,p.verify_check,p.large_check,p.report,p.title_entry,p.art_button,*p.op_buttons):
            self.assertTrue(widget.winfo_ismapped(),str(widget))
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.winfo_rooty()+app.winfo_height(),str(widget))
        import tkinter as tk
        def labels_fit():
            for widget in p.panels[-1].inner.winfo_children():
                # Optional tips are hidden (not clipped) when the panel is too short.
                if isinstance(widget,tk.Label) and widget.winfo_ismapped():
                    self.assertGreaterEqual(widget.winfo_height(),widget.winfo_reqheight(),widget.cget('text')[:40])
        labels_fit()
        app.geometry('1280x1000');self.pump(.3);labels_fit()
        if app.winfo_height()>=990:  # macOS clamps windows to small screens.
            self.assertTrue(p.compat_tip.winfo_ismapped(),'Tip returns when there is room')
        app.geometry('1010x830');self.pump(.3);labels_fit()
        for op in OPERATIONS:
            p.operation.set(op);p.changed();self.pump()
            self.assertEqual(p.preset_buttons[0].enabled,op in OPERATIONS[:2])
        self.assertFalse(self.errors)

    def test_source_specific_choices_and_stale_scan_cleanup(self):
        import nup_tools as nt
        p=self.app.nup_panel
        def shown():
            self.pump();return {name for name,control in zip(p.includes,p.include_checks) if control.winfo_ismapped()}
        self.assertEqual(shown(),set())
        p.receive_drop(self.game);self.until(lambda:not p.busy)
        self.assertEqual(shown(),{'Base'});self.assertEqual(p.selected_kinds(),{0})
        self.assertFalse(p.snapshot_check.winfo_ismapped())
        bundle=self.root/'Bundle';snapshot(bundle/'base',{'base':b'base'})
        snapshot(bundle/'updates/65536',{'update':b'update'},1)
        addon=bundle/'dlc/0400111122221001/romfs';addon.mkdir(parents=True);(addon/'addon').write_bytes(b'dlc')
        p.receive_drop(bundle);self.until(lambda:not p.busy)
        self.assertEqual(shown(),{'Base','Updates','DLC'});self.assertTrue(p.snapshot_check.winfo_ismapped())
        self.assertIn('Merge base',p.snapshot_hint.cget('text'))
        for item in p.snapshot_check.find_all():
            if p.snapshot_check.type(item)=='text':self.assertLessEqual(p.snapshot_check.bbox(item)[2],p.snapshot_check.winfo_width())
        p.includes['Base'].set(False);self.assertIn('no base fallback',p.snapshot_hint.cget('text'));p.includes['Base'].set(True)
        archive=self.root/'Bundle.nup';nt.pack_folder(bundle,archive,latest_snapshot=False)
        p.operation.set(OPERATIONS[2]);p.input.set(str(archive));p.changed()
        self.assertEqual(shown(),set());p.scan();self.until(lambda:not p.busy)
        self.assertEqual(shown(),{'Base','Updates','DLC'});self.assertFalse(p.snapshot_check.winfo_ismapped())
        p.receive_drop(addon.parent);self.until(lambda:not p.busy)
        self.assertEqual(shown(),{'DLC'});self.assertEqual(p.selected_kinds(),{2})
        p.input.set(str(self.root/'missing'));self.assertEqual(shown(),set())
        p.scan();self.until(lambda:not p.busy);self.assertEqual(shown(),set())
        p.input.set('');self.assertEqual(shown(),set());self.assertFalse(self.errors)

    def test_automatic_outputs_reveal_and_artwork_crop(self):
        from PIL import Image
        from artwork import ArtworkSelection
        import nup_format as nf
        p=self.app.nup_panel
        self.app.geometry('950x760');self.pump(.5)
        self.assertIsNone(self.app._startup_job)
        self.assertFalse(hasattr(p,'op_combo'));self.assertFalse(hasattr(p,'selection_combo'));self.assertFalse(hasattr(p,'save_button'))
        self.assertAlmostEqual(p.reveal_height,104)
        self.app.motion.enabled=True
        p.operation.set(OPERATIONS[1]);p.changed()
        self.assertIn((id(p),'presentation'),self.app.motion.jobs)
        self.pump(.5);self.assertEqual(p.reveal_height,0)
        p.operation.set(OPERATIONS[0]);p.changed();self.pump(.4)
        art=self.root/'cover.webp';Image.new('RGB',(400,300),'red').save(art)
        selection=ArtworkSelection(art,(.125,0,.875,1))
        with patch('nup_panel.CropDialog') as dialog:
            dialog.return_value.show.return_value=selection;p.set_art(art)
        self.assertIsNotNone(p.art_bytes);self.assertEqual(p.art_button.text,'Edit cover')
        p.title_text.set('Custom NUP title');p.input.set(str(self.game))
        p.scan();self.until(lambda:not p.busy)
        with patch('nup_panel.filedialog.asksaveasfilename',side_effect=AssertionError('Must not prompt')):
            p.start();self.until(lambda:not p.busy)
            first=self.root/'Game.nup';self.assertTrue(first.exists(),p.status.get());original=first.read_bytes()
            with nf.Archive(first) as a:
                metadata=dict(a.packages[0].metadata);self.assertEqual(metadata[5],b'Custom NUP title');self.assertEqual(metadata[3],p.art_bytes)
            p.start();self.until(lambda:not p.busy);self.assertTrue((self.root/'Game (2).nup').exists());self.assertEqual(first.read_bytes(),original)
        for var in p.includes.values():var.set(False)
        p.start();self.assertFalse(p.busy);self.assertIn('Select at least one',p.status.get())
        self.assertFalse(self.errors)
