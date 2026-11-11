"""Cross-platform behaviour: exclusive commits, folder-name case, OS metadata and the CLI.

Runs without Tk or a display on Windows, macOS and Linux.
"""
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch
import errno, io, json, os, struct, sys, tempfile, unittest
sys.path.insert(0,str(Path(__file__).parent/'src'))
import portable, engine, dlc, cli, nup_format as nf, nup_tools as nt

TID=0x0400111122220000
DS_STORE=b'\x00\x00\x00\x01Bud1'+bytes(32)
APPLEDOUBLE=b'\x00\x05\x16\x07'+bytes(60)

def npdm(tid=TID):
    b=bytearray(0x100);b[:4]=b'META';struct.pack_into('<II',b,0x70,0x80,0x80);b[0x80:0x84]=b'ACI0'
    struct.pack_into('<Q',b,0x90,tid);return bytes(b)

def game(root,exefs='exefs',romfs='romfs',files=None):
    (root/exefs).mkdir(parents=True);(root/romfs).mkdir()
    (root/exefs/'main.npdm').write_bytes(npdm());(root/exefs/'main').write_bytes(b'NSO0'+bytes(256))
    for name,data in (files or {'data/a.bin':bytes(range(256))*64,'b.txt':b'hello'}).items():
        p=root/romfs/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(data)
    return root

class Scratch(unittest.TestCase):
    def setUp(self):
        scratch=Path(__file__).parent/'test-work';scratch.mkdir(exist_ok=True)
        self.tmp=tempfile.TemporaryDirectory(dir=scratch);self.root=Path(self.tmp.name)
    def tearDown(self):self.tmp.cleanup()

class CommitTests(Scratch):
    def check_commit(self):
        temp=self.root/'out.partial';temp.write_bytes(b'new')
        portable.commit_no_replace(temp,self.root/'out.bin')
        self.assertEqual((self.root/'out.bin').read_bytes(),b'new');self.assertFalse(temp.exists())
        temp.write_bytes(b'second')
        with self.assertRaises(FileExistsError):portable.commit_no_replace(temp,self.root/'out.bin')
        self.assertEqual((self.root/'out.bin').read_bytes(),b'new');self.assertTrue(temp.exists())
        stage=self.root/'stage';stage.mkdir();(stage/'f').write_bytes(b'1')
        portable.commit_no_replace(stage,self.root/'folder');self.assertEqual((self.root/'folder'/'f').read_bytes(),b'1')
        stage.mkdir();(self.root/'empty').mkdir()
        with self.assertRaises(FileExistsError):portable.commit_no_replace(stage,self.root/'empty')
        self.assertTrue(stage.is_dir())
        self.assertEqual(sorted(p.name for p in self.root.iterdir()),['empty','folder','out.bin','out.partial','stage'])

    def test_native_commit_never_replaces(self):
        self.check_commit()

    @unittest.skipIf(os.name=='nt','POSIX fallback path')
    def test_fallback_for_filesystems_without_links_or_exclusive_rename(self):
        # exFAT/FAT32/SMB: no hard links and no RENAME_NOREPLACE/RENAME_EXCL.
        def no_link(*a,**k):raise OSError(errno.EPERM,'Operation not permitted')
        with patch.object(portable,'_exclusive_rename',return_value=False),patch.object(portable.os,'link',no_link):
            self.check_commit()

class FolderCaseTests(Scratch):
    def test_child_prefers_exact_and_finds_other_case(self):
        (self.root/'RomFS').mkdir()
        found=portable.child(self.root,'romfs')
        self.assertTrue(found.is_dir())
        self.assertEqual(portable.child(self.root,'missing'),self.root/'missing')

    def test_mixed_case_snapshot_builds_and_verifies(self):
        src=game(self.root/'Game',exefs='ExeFS',romfs='RomFS')
        snapshots,_=engine.find_snapshots(src);self.assertEqual(len(snapshots),1)
        report=engine.build(snapshots[0],self.root/'out'/'Game.nsp','Game','1.0',verify=True)
        self.assertTrue(report['verified']);self.assertEqual(report['source_file_count'],4)

    def test_nup_index_uses_standard_top_level_names(self):
        src=game(self.root/'Game',exefs='ExeFS',romfs='RomFS')
        files,dirs=nt.tree_sources(src)
        self.assertIn('exefs/main.npdm',files);self.assertIn('romfs/b.txt',files)
        self.assertTrue({'exefs','romfs'}<=dirs)

class MetadataTests(Scratch):
    def test_signature_required(self):
        (self.root/'.DS_Store').write_bytes(DS_STORE);(self.root/'._a').write_bytes(APPLEDOUBLE)
        (self.root/'._game_data').write_bytes(b'real game file')
        self.assertTrue(portable.is_os_metadata(self.root/'.DS_Store'))
        self.assertTrue(portable.is_os_metadata(self.root/'._a'))
        self.assertFalse(portable.is_os_metadata(self.root/'._game_data'))

    def junk(self,src):
        (src/'romfs'/'.DS_Store').write_bytes(DS_STORE);(src/'romfs'/'data'/'._a.bin').write_bytes(APPLEDOUBLE)
        (src/'exefs'/'._main').write_bytes(APPLEDOUBLE);(src/'romfs'/'._kept').write_bytes(b'not AppleDouble')

    def test_game_build_skips_and_reports_metadata(self):
        src=game(self.root/'Game');self.junk(src)
        snap=engine.find_snapshots(src)[0][0]
        report=engine.build(snap,self.root/'Game.nsp','Game','1.0',verify=True)
        self.assertTrue(report['verified'])
        self.assertEqual(sorted(report['ignored_os_metadata']),['exefs/._main','romfs/.DS_Store','romfs/data/._a.bin'])
        self.assertIn('romfs/._kept',[f['path'] for f in report['files']])

    def test_dlc_build_skips_metadata(self):
        root=self.root/'dlc'/f'{TID+0x1001:016X}';(root/'romfs'/'data').mkdir(parents=True)
        (root/'romfs'/'data'/'x.bin').write_bytes(b'dlc data');(root/'romfs'/'.DS_Store').write_bytes(DS_STORE)
        snap=dlc.find_snapshots(root)[0]
        report=dlc.build(snap,self.root/'DLC.nsp')
        self.assertEqual(report['ignored_os_metadata'],['.DS_Store']);self.assertEqual(report['source_file_count'],1)

    def test_nup_never_archives_metadata(self):
        src=game(self.root/'Game');self.junk(src)
        files,_=nt.tree_sources(src)
        self.assertNotIn('romfs/.DS_Store',files);self.assertNotIn('exefs/._main',files);self.assertIn('romfs/._kept',files)

class RaceTests(Scratch):
    def test_game_output_created_during_build_is_kept(self):
        src=game(self.root/'Game');snap=engine.find_snapshots(src)[0][0];out=self.root/'Game.nsp'
        def race(stage,value):
            if stage=='Comparing source files' and not out.exists():out.write_bytes(b'other writer')
        with self.assertRaises(FileExistsError):engine.build(snap,out,'Game','1.0',notify=race)
        self.assertEqual(out.read_bytes(),b'other writer');self.assertEqual(list(self.root.glob('*.partial')),[])

class ExtractCaseTests(Scratch):
    def test_case_colliding_names_follow_the_target_filesystem(self):
        files={'romfs/A.bin':nf.Source.data(b'upper'),'romfs/a.bin':nf.Source.data(b'lower'),
               'exefs/main.npdm':nf.Source.data(npdm()),'exefs/main':nf.Source.data(b'NSO0'+bytes(256))}
        archive=self.root/'case.nup'
        nf.pack([nf.Package(TID,0,0,files,{'exefs','romfs'},[])],archive)
        if portable.folds_names(self.root):
            with self.assertRaisesRegex(ValueError,'Case-colliding'):nf.extract(archive,self.root/'x')
            self.assertFalse((self.root/'x').exists())
        else:
            nf.extract(archive,self.root/'x')
            self.assertEqual((self.root/'x'/'base'/'romfs'/'A.bin').read_bytes(),b'upper')

class CliTests(Scratch):
    def run_cli(self,*argv):
        out,err=io.StringIO(),io.StringIO()
        with redirect_stdout(out),redirect_stderr(err):code=cli.run([str(a) for a in argv])
        return code,out.getvalue(),err.getvalue()

    def test_dispatch_detection(self):
        self.assertFalse(cli.wants_cli([]));self.assertFalse(cli.wants_cli(['--folder','x']))
        for argv in (['scan','x'],['--help'],['--package','x','--output','y.nsp'],['--nup-operation','inspect']):
            self.assertTrue(cli.wants_cli(argv))

    def test_scan_build_and_nup_round_trip(self):
        src=game(self.root/'My Game')
        code,out,_=self.run_cli('scan',src,'--json');self.assertEqual(code,0)
        self.assertEqual(json.loads(out)['snapshots'][0]['title_id'],f'{TID:016X}')
        code,out,err=self.run_cli('build',src,'-o',self.root/'Out.nsp','--no-package-folder','-q','--json')
        self.assertEqual(code,0,err);self.assertTrue(json.loads(out)['verified']);self.assertTrue((self.root/'Out.nsp').is_file())
        code,out,err=self.run_cli('build',src,'-o',self.root/'Out.nsp','--no-package-folder','-q')
        self.assertEqual(code,1);self.assertIn('already exists',err)
        code,out,err=self.run_cli('nup','pack',src,'-q','--preset','Fast');self.assertEqual(code,0,err)
        self.assertTrue((self.root/'My Game.nup').is_file())
        code,out,err=self.run_cli('nup','pack',src,'-q','--preset','Fast');self.assertEqual(code,0,err)
        self.assertTrue((self.root/'My Game (2).nup').is_file())
        code,out,err=self.run_cli('nup','verify',self.root/'My Game.nup','-q');self.assertEqual(code,0,err)
        self.assertTrue(json.loads(out)['verified'])
        code,out,err=self.run_cli('nup','to-nsp',self.root/'My Game.nup','-o',self.root/'Back.nsp','-q');self.assertEqual(code,0,err)
        code,out,err=self.run_cli('nup','extract',self.root/'My Game.nup','-q');self.assertEqual(code,0,err)
        self.assertEqual((self.root/'My Game-extracted'/'base'/'romfs'/'b.txt').read_bytes(),b'hello')

    def test_errors_are_reported_with_exit_code(self):
        code,out,err=self.run_cli('scan',self.root/'missing');self.assertEqual(code,1);self.assertIn('error:',err)
        code,out,err=self.run_cli('nup','pack',self.root,'--include','bogus','-q');self.assertEqual(code,1)

    def test_non_ascii_output_through_ansi_code_page_pipes(self):
        # Windows pipes default to the ANSI code page (cp1252); titles must not crash output.
        import subprocess
        src=game(self.root/'日本語 Game')
        env=dict(os.environ,PYTHONIOENCODING='cp1252')
        for argv in (['scan',str(src)],['build','-h']):
            result=subprocess.run([sys.executable,str(Path(__file__).parent/'src'/'cli.py'),*argv],capture_output=True,env=env,timeout=60)
            self.assertEqual(result.returncode,0,result.stderr.decode('utf-8','replace'))
        self.assertIn('日本語',subprocess.run([sys.executable,str(Path(__file__).parent/'src'/'cli.py'),'scan',str(src)],
                      capture_output=True,env=env,timeout=60).stdout.decode('utf-8'))

    def test_ctrl_c_cancels_and_cleans_up(self):
        src=game(self.root/'Game');progress=cli.Progress(quiet=True)
        def call(notify,cancel):
            return engine.build(engine.find_snapshots(src)[0][0],self.root/'G.nsp','G','1',
                                notify=lambda s,v:(cancel.set(),notify(s,v)),cancel=cancel)
        with self.assertRaises(InterruptedError):cli.run_cancellable(call,progress)
        self.assertEqual([p.name for p in self.root.iterdir()],['Game'])

if __name__=='__main__':unittest.main()
