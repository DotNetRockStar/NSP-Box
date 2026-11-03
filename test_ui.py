"""UI integration checks using synthetic content and the app's own widgets."""
from pathlib import Path
import ctypes, io, json, struct, sys, tempfile, time, unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).parent/'src'))
from app import App
from crop_dialog import CropDialog
from PIL import Image

class InterfaceTests(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(prefix='ui-',dir=scratch);self.root=Path(self.tmp.name)
        self.game=self.root/'Sample Game'
        for version in (65536,131072):
            p=self.game/'updates'/str(version);(p/'exefs').mkdir(parents=True);(p/'romfs').mkdir()
            npdm=bytearray(0x100);npdm[:4]=b'META';struct.pack_into('<II',npdm,0x70,0x80,0x80)
            npdm[0x80:0x84]=b'ACI0';struct.pack_into('<Q',npdm,0x90,0x0400111122220000)
            (p/'exefs/main.npdm').write_bytes(npdm);(p/'exefs/main').write_bytes(b'NSO0'+bytes(256))
            (p/'romfs/content.bin').write_bytes(bytes(range(256))*81)
        self.art=self.root/'cover.png';Image.new('RGB',(320,240),'#55aaff').save(self.art)
        self.app=App(show_startup=False,preferences_path=self.root/'preferences.json');self.errors=[]
        self.app.report_callback_exception=lambda *args:self.errors.append(args)
        self.pump(.5)
    def tearDown(self):
        if self.app is not None:self.app.close()
        self.tmp.cleanup()
    def pump(self,seconds):
        end=time.monotonic()+seconds
        while time.monotonic()<end:self.app.update();time.sleep(.008)
    def until(self,condition,timeout=8):
        end=time.monotonic()+timeout
        while not condition() and time.monotonic()<end:self.pump(.03)
        self.assertTrue(condition(),'UI did not finish within the timeout')
    def shell_drop(self,path):
        if sys.platform!='win32':self.app.receive_drop([str(path)]);return
        from ctypes import wintypes as w
        self.assertIsNotNone(self.app._drops,'Native drop registration failed')
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GlobalAlloc.argtypes=[w.UINT,ctypes.c_size_t];kernel.GlobalAlloc.restype=w.HGLOBAL
        kernel.GlobalLock.argtypes=[w.HGLOBAL];kernel.GlobalLock.restype=ctypes.c_void_p
        kernel.GlobalUnlock.argtypes=[w.HGLOBAL]
        payload=struct.pack('<IiiII',20,0,0,0,1)+(str(path)+'\0\0').encode('utf-16le')
        handle=kernel.GlobalAlloc(0x42,len(payload));pointer=kernel.GlobalLock(handle)
        ctypes.memmove(pointer,payload,len(payload));kernel.GlobalUnlock(handle)
        user=ctypes.WinDLL('user32');user.SendMessageW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM]
        user.SendMessageW.restype=ctypes.c_ssize_t
        user.SendMessageW(self.app._drops.hwnd,0x233,handle,0)
    def test_drop_build_artwork_and_controls(self):
        app=self.app;self.shell_drop(self.game);self.until(lambda:len(app.snapshots)==2 and not app.scanning)
        self.assertEqual(app.title_id_text.get(),'0400111122220000')
        self.assertEqual(app.version_text.get(),'dump-131072')
        app.combo.current(1);app.select_snapshot();self.assertEqual(app.version_text.get(),'dump-65536')
        self.shell_drop(self.art);self.pump(.35);self.assertEqual(app.art_path,self.art)
        app.clear_art_btn.invoke();self.assertIsNone(app.art_path)
        app.set_art(self.art);app.title_text.set('Sample Custom Title');app.version_text.set('1.2')
        app.verify_check.invoke();self.assertFalse(app.verify.get())
        app.verify_check.invoke();self.assertTrue(app.verify.get())
        self.assertTrue(app.package_folder.get());app.package_folder_check.invoke()
        out=self.root/'Built.nsp';app.output.set(str(out));app.build_btn.invoke()
        self.assertTrue(app.busy);self.assertFalse(app.browse.enabled);self.assertTrue(app.cancel_btn.enabled)
        self.until(lambda:not app.busy,timeout=10)
        self.assertTrue(out.is_file());self.assertTrue(app.open_btn.enabled)
        self.assertFalse(out.with_suffix('.nsp.report.json').exists());self.assertFalse((out.parent/'main.npdm').exists())
        self.assertEqual(app.last_output,out)
        app.notes();self.pump(.06)
        self.assertTrue(any(w.winfo_class()=='Toplevel' for w in app.winfo_children()))
        self.assertFalse(self.errors)
    def test_motion_and_minimum_layout(self):
        app=self.app;app.motion.enabled=True
        values=[];app.motion.to('test',0,1,.18,values.append);self.pump(.08)
        self.assertTrue(any(0<v<1 for v in values));self.pump(.18);self.assertAlmostEqual(values[-1],1)
        app.geometry('1010x780');self.pump(.1)
        checkbox=app.package_folder_check;parent=checkbox.master
        self.assertEqual(checkbox.winfo_height(),25)
        self.assertLessEqual(checkbox.winfo_rooty()+checkbox.winfo_height(),parent.winfo_rooty()+parent.winfo_height())
        for widget in (app.verify_check,app.package_folder_check,app.folder_entry,app.combo,app.version_entry,app.clear_art_btn,app.crop_art_btn,app.paste_art_btn,app.build_btn,app.help_btn):
            self.assertTrue(widget.winfo_ismapped(),str(widget))
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.winfo_rooty()+app.winfo_height())
            self.assertLessEqual(widget.winfo_rooty()+widget.winfo_height(),app.content_area.winfo_rooty()+app.content_area.winfo_height()) if widget not in (app.build_btn,app.help_btn) else None
        app.motion.enabled=False;values=[]
        app.motion.to('static',0,1,.3,values.append);self.assertEqual(values,[1])
        # The default size previously left only two pixels of the path editor.
        # Both text rows also need to remain above the Browse button when small.
        for geometry in ('1160x830','1010x780','1280x960'):
            app.geometry(geometry);self.pump(.15)
            entry=app.folder_entry;inner=app.panels[0].inner;zone=app.drop_zone
            self.assertEqual(entry.winfo_height(),35,geometry)
            self.assertLessEqual(entry.winfo_rooty()+entry.winfo_height(),inner.winfo_rooty()+inner.winfo_height(),geometry)
            title=zone.bbox('folder-title');subtitle=zone.bbox('folder-subtitle')
            self.assertGreaterEqual(title[1],0,geometry)
            self.assertLessEqual(title[3],subtitle[1],geometry)
            self.assertLess(subtitle[3],app.browse.winfo_y(),geometry)
            self.assertEqual(app.browse.cget('bg'),'#192b43',geometry)
        self.assertFalse(self.errors)

    def test_nsp_only_path_build_and_brand(self):
        app=self.app
        self.assertEqual(app.title(),'NSP Box');self.assertFalse(hasattr(app,'format_combo'))
        self.assertFalse(hasattr(app.dlc_panel,'format_combo'))
        self.shell_drop(self.game);self.until(lambda:len(app.snapshots)==2 and not app.scanning)
        self.assertTrue(app.output.get().endswith('.nsp'))
        out=self.root/'Custom destination.nsp';app.output.set(str(out))
        self.assertEqual(app.build_btn.text,'Build NSP')
        self.assertTrue(app.package_folder.get())
        app.set_art(self.art);app.build_btn.invoke()
        self.assertFalse(app.package_folder_check.enabled)
        self.until(lambda:not app.busy,timeout=10)
        actual=out.parent/out.stem/out.name
        self.assertTrue(actual.is_file());self.assertEqual(app.last_output,actual)
        self.assertTrue(app.package_folder_check.enabled);self.assertEqual(app.status.get(),'NSP ready')
        report=json.loads(actual.with_suffix('.nsp.report.json').read_text())
        self.assertEqual(report['app'],'NSP Box');self.assertEqual(report['output_format'],'NSP');self.assertTrue(report['verified'])
        self.assertFalse(self.errors)

    def test_icon_assets_and_ambient_lifecycle(self):
        from ui import ASSET_DIR, icon_art, TEXT
        app=self.app;ambient=app._ambient
        files=list(ASSET_DIR.glob('*.png'));self.assertEqual(len(files),22)
        for path in files:
            with Image.open(path) as image:
                self.assertEqual(image.mode,'RGBA')
        self.assertEqual(app.draw_app_icon().tobytes(),icon_art('app',256,TEXT,1.7).tobytes())
        self.assertEqual(app.dlc_tab_button.kind,'dlc')
        self.assertEqual(app.emulator_patch_btn.kind,'emulator-patch')
        self.assertNotEqual(app.art_btn.kind,app.paste_art_btn.kind)
        app.motion.enabled=True;self.pump(.2)
        before=ambient.frame_count;first=ambient.frame.copy();self.pump(.25)
        self.assertGreater(ambient.frame_count,before)
        self.assertEqual(ambient.frame.size,(app.winfo_width(),app.winfo_height()))
        # Reconfigure after the first ambient frame, as happens during frozen
        # startup. Its opaque image must never cover the rounded panel surface.
        from types import SimpleNamespace
        for panel in app.panels:
            panel.resize(SimpleNamespace(width=panel.winfo_width(),height=panel.winfo_height()))
            stack=list(panel.find_all())
            self.assertLess(stack.index(panel.find_withtag('ambient')[0]),
                            stack.index(panel.find_withtag('surface')[0]))
        app.motion.enabled=False;self.pump(.12)
        before=ambient.frame_count;self.pump(.30)
        self.assertEqual(ambient.frame_count,before)
        app.motion.enabled=True;app.show_tab('dlc');self.pump(.45)
        self.assertTrue(app.dlc_panel.winfo_ismapped())
        self.assertAlmostEqual(app.dlc_tab_button.selection,1.)
        app.show_tab('game');self.pump(.45)
        self.assertAlmostEqual(app.game_tab_button.selection,1.)
        self.assertFalse(self.errors)

    def test_motion_retargets_and_icon_cache_stays_bounded(self):
        from ui import _PHOTO_CACHES, surface_art
        app=self.app;button=app.art_btn;app.motion.enabled=True
        button.hover(1);self.pump(.07)
        self.assertGreater(button.hot,0);self.assertLess(button.hot,1)
        button.hover(0);self.pump(.3);self.assertAlmostEqual(button.hot,0)
        cache=_PHOTO_CACHES[app];before=len(cache)
        for _ in range(25):button.draw()
        self.assertEqual(len(cache),before)
        self.assertLessEqual(surface_art.cache_info().currsize,96)
        ambient=app._ambient;app.close()
        self.assertIsNone(ambient.job);self.assertTrue(ambient.closed)
        self.assertFalse(app.motion.jobs)
        # This case closes explicitly to verify timer cleanup.
        self.app=None

    def test_crop_dialog_and_clipboard(self):
        app=self.app
        with patch('app.ImageGrab.grabclipboard',return_value=Image.new('RGB',(600,300),'#ffaa55')):
            self.assertTrue(app.paste_art())
        self.assertTrue(app.crop_art_btn.enabled);clipboard_path=app.art_path
        self.assertTrue(clipboard_path.is_file())
        dialog=CropDialog(app,app.art_selection);self.pump(.13)
        dialog.model.set_zoom(2);dialog.model.pan(80,0);dialog.schedule_render();self.pump(.08)
        selected=dialog.current_selection();dialog.apply();self.pump(.05)
        self.assertEqual(dialog.result,selected)
        with patch('app.CropDialog') as factory:
            factory.return_value.show.return_value=selected;app.crop_art()
        self.assertEqual(app.art_selection,selected)
        with patch('app.CropDialog') as factory:
            factory.return_value.show.return_value=None;app.crop_art()
        self.assertEqual(app.art_selection,selected)
        with patch('app.ImageGrab.grabclipboard',return_value=[str(self.art)]):
            self.assertTrue(app.paste_art());self.assertEqual(app.art_path,self.art)
        app.folder_entry.entry.focus_force();self.pump(.02)
        with patch('app.ImageGrab.grabclipboard',return_value=None):
            self.assertIsNone(app.paste_art_shortcut())
        self.assertFalse(self.errors)

    def test_supported_emulator_catalog_fits_with_actions(self):
        from emulator_dialog import EmulatorDialog
        dialog=EmulatorDialog(self.app)
        try:
            dialog.geometry('740x745');self.pump(.08)
            self.assertIn('Selevet performance build 4',dialog.supported_text)
            self.assertIn('30 FPS',dialog.supported_text)
            last=dialog.supported_panel.inner.winfo_children()[-1]
            self.assertLessEqual(last.winfo_rooty()+last.winfo_height(),
                                 dialog.supported_panel.winfo_rooty()+dialog.supported_panel.winfo_height())
            for button in (dialog.check_button,dialog.apply_button,dialog.remove_button):
                self.assertTrue(button.winfo_viewable())
                self.assertLessEqual(button.winfo_rooty()+button.winfo_height(),
                                     dialog.winfo_rooty()+dialog.winfo_height())
            self.assertFalse(self.errors)
        finally:dialog.close()

    def test_no_startup_modal_and_persistent_game_guidance(self):
        app=self.app;preferences=app.preferences_path
        app.show_startup_caution();self.pump(.08)
        self.assertIsNone(app._startup_dialog);self.assertIsNone(app._startup_job);self.assertIsNone(app.grab_current())
        self.assertFalse(preferences.exists())
        self.assertTrue(app.game_run_note.winfo_ismapped())
        self.assertIn('main.npdm',app.game_run_note.text);self.assertIn('Emulator patch',app.game_run_note.text)
        self.assertIn('Newer PokeDinner',app.game_run_note.text)
        self.assertFalse(self.errors)

    def test_explicit_emulator_setup_from_notes(self):
        import compatibility
        app=self.app;app.notes();self.pump(.05)
        notes=next(w for w in app.winfo_children() if w.winfo_class()=='Toplevel')
        setup=next(w for frame in notes.winfo_children() for w in frame.winfo_children() if w.winfo_class()=='TButton' and w.cget('text')=='Set up emulator keys folder…')
        folder=self.root/'emulator-keys'
        with patch('app.filedialog.askdirectory',return_value=str(folder)),patch('app.messagebox.showinfo') as info:
            setup.invoke()
        self.assertTrue(compatibility.inspect(folder)['ready']);self.assertTrue(info.called)
        before=(folder/'prod.keys_autogenerated').read_bytes()
        with patch('app.filedialog.askdirectory',return_value=''),patch('app.messagebox.showinfo') as info:
            setup.invoke()
        self.assertFalse(info.called);self.assertEqual((folder/'prod.keys_autogenerated').read_bytes(),before)
        self.assertFalse(self.errors)

    def test_emulator_patch_panel_check_and_close(self):
        app=self.app;app.emulator_patch_btn.invoke();self.pump(.08)
        dialog=app._emulator_dialog
        self.assertTrue(dialog.winfo_exists());self.assertFalse(dialog.apply_button.enabled)
        for name in ('build 98','build-99','build 96','2.1.0a','2.0.0'):
            self.assertIn(name,dialog.supported_text)
        for geometry in ('780x760','740x720'):
            dialog.geometry(geometry);self.pump(.05)
            bottom=dialog.winfo_rooty()+dialog.winfo_height()
            self.assertLessEqual(dialog.supported_label.winfo_rooty()+dialog.supported_label.winfo_height(),bottom)
            self.assertLessEqual(dialog.apply_button.winfo_rooty()+dialog.apply_button.winfo_height(),bottom)
        view={'folder':str(self.root),'files':[{'build':'Synthetic compatible fork','file':'future.exe','status':'experimental'}],
              'can_apply':True,'can_remove':False}
        with patch('emulator_patch.inspect',return_value=view):
            dialog.folder.set(str(self.root));dialog.check_button.invoke();self.until(lambda:not dialog.working)
        self.assertTrue(dialog.apply_button.enabled);self.assertEqual(dialog.apply_button.text,'Try patch')
        self.assertFalse(dialog.remove_button.enabled)
        view['files'][0]['status']='patched';view['can_apply']=False;view['can_remove']=True
        with patch('emulator_patch.apply',return_value=view):
            dialog.apply_button.invoke();self.until(lambda:not dialog.working)
        self.assertTrue(dialog.remove_button.enabled);self.assertIn('Patch added',dialog.message.get())
        dialog.close();self.pump(.02);self.assertFalse(dialog.winfo_exists())
        self.assertFalse(self.errors)

if __name__=='__main__':unittest.main(verbosity=2)
