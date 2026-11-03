"""Local emulator patch controls; all disk work runs outside the Tk thread."""
from pathlib import Path
import queue,threading,tkinter as tk
from tkinter import filedialog
import emulator_patch
from emulator_profiles import SUPPORTED_BUILDS, SUPPORT_CHECKED_DATE
from ui import BG,PANEL,TEXT,MUTED,Button,Entry,Panel,ui_font

class EmulatorDialog(tk.Toplevel):
    def __init__(self,parent):
        super().__init__(parent);self.withdraw();self.title('Emulator patch');self.configure(bg=BG)
        self.geometry('800x790');self.minsize(780,780);self.transient(parent)
        self.parent=parent;self.motion=parent.motion;self.working=False;self.view=None;self.events=queue.Queue()
        self.folder=tk.StringVar();self.summary=tk.StringVar(value='Select the folder containing the emulator executable.')
        self.message=tk.StringVar(value='No emulator files have been changed.')
        tk.Label(self,text='Emulator patch',bg=BG,fg=TEXT,font=ui_font(22,True)).pack(anchor='w',padx=24,pady=(22,6))
        tk.Label(self,text='Read Switch 2 metadata inside NSP',bg=BG,fg=MUTED,font=ui_font(11)).pack(anchor='w',padx=24)
        self.native_notice=tk.Label(self,text='PokeDinner 2.5.0 and newer builds with native NSP support need no patch or external main.npdm.\n'
                 'Thanks to Franseven, creator of PokeDinner, for integrating support! Older builds are listed below.',
                 bg=BG,fg='#b9d8ff',font=ui_font(10),justify='left',wraplength=748)
        self.native_notice.pack(anchor='w',padx=24,pady=(12,0))
        row=tk.Frame(self,bg=BG);row.pack(fill='x',padx=24,pady=(20,14))
        self.entry=Entry(row,textvariable=self.folder,placeholder='Choose a Windows x64 emulator folder');self.entry.pack(side='left',fill='x',expand=True)
        self.browse=Button(row,'Browse',self.pick,self.motion,width=105,height=41,kind='folder');self.browse.pack(side='right',padx=(10,0))
        self.entry.bind('<Return>',lambda event:self.check())
        card=Panel(self,height=118);card.pack(fill='x',padx=24)
        tk.Label(card.inner,textvariable=self.summary,bg=PANEL,fg=TEXT,font=ui_font(11,True),anchor='nw',justify='left',wraplength=595).pack(fill='both',expand=True)
        self.supported_panel=Panel(self,height=190);self.supported_panel.pack(fill='x',padx=24,pady=(12,0))
        tk.Label(self.supported_panel.inner,text='Supported patch targets · Windows x64',bg=PANEL,fg=TEXT,
                 font=ui_font(10,True)).pack(anchor='w',pady=(0,6))
        self.supported_text='\n'.join(f'{b["label"]} — {b["variants"]}' for b in SUPPORTED_BUILDS)
        self.supported_label=tk.Label(self.supported_panel.inner,text=self.supported_text,bg=PANEL,fg=MUTED,
                 font=ui_font(9),justify='left',anchor='w',wraplength=680)
        self.supported_label.pack(fill='x')
        tk.Label(self.supported_panel.inner,text='Checked '+SUPPORT_CHECKED_DATE+' · patch support is not a gameplay guarantee.',
                 bg=PANEL,fg=MUTED,font=ui_font(8)).pack(anchor='w',pady=(5,0))
        tk.Label(self,text='Close the emulator before adding or removing. Exact originals stay in .s2gp-patch.\n'
                 'Other builds/forks require matching loader and metadata-reader code; unmatched files stay untouched.\n'
                 'Experimental detection patch only. Games, saves and emulator settings are unchanged.',
                 bg=BG,fg=MUTED,font=ui_font(9),justify='left',wraplength=720).pack(anchor='w',padx=24,pady=(15,12))
        tk.Label(self,textvariable=self.message,bg=BG,fg='#b9d8ff',font=ui_font(10),justify='left',wraplength=650).pack(anchor='w',padx=24)
        buttons=tk.Frame(self,bg=BG);buttons.pack(side='bottom',fill='x',padx=24,pady=22)
        self.apply_button=Button(buttons,'Add patch',lambda:self.run('apply'),self.motion,kind='apply-patch',primary=True,state='disabled');self.apply_button.pack(side='right')
        self.remove_button=Button(buttons,'Remove patch',lambda:self.run('remove'),self.motion,kind='remove-patch',state='disabled');self.remove_button.pack(side='right',padx=(0,10))
        self.check_button=Button(buttons,'Check build',self.check,self.motion,width=145,kind='check-emulator');self.check_button.pack(side='left')
        self.protocol('WM_DELETE_WINDOW',self.close);self.job=self.after(70,self.poll)
        self.update_idletasks()
        x=max(0,parent.winfo_rootx()+(parent.winfo_width()-800)//2)
        y=max(0,parent.winfo_rooty()+(parent.winfo_height()-790)//2)
        self.geometry(f'800x790{x:+d}{y:+d}');self.deiconify()
    def pick(self):
        folder=filedialog.askdirectory(parent=self,title='Select the folder containing the emulator executable')
        if folder:self.folder.set(folder);self.check()
    def check(self):
        if self.folder.get().strip():self.run('inspect')
    def run(self,action):
        if self.working:return
        folder=self.folder.get().strip()
        if not folder:return
        self.working=True;self.view=None
        for button in (self.browse,self.check_button,self.apply_button,self.remove_button):button.configure(state='disabled')
        self.entry.configure(state='disabled')
        self.message.set({'inspect':'Checking executable hashes…','apply':'Backing up and adding the patch…','remove':'Restoring the exact original executable…'}[action])
        def worker():
            try:self.events.put((action,getattr(emulator_patch,action)(folder),None))
            except Exception as error:self.events.put((action,None,str(error)))
        threading.Thread(target=worker,daemon=True).start()
    def poll(self):
        try:
            action,view,error=self.events.get_nowait();self.working=False;self.view=view
            self.browse.configure(state='normal');self.check_button.configure(state='normal');self.entry.configure(state='normal')
            if error:
                self.summary.set('Could not safely complete this operation.')
                self.message.set(error+' Close the emulator before retrying.')
            else:
                self.folder.set(view['folder'])
                labels={'supported':'Verified · ready to patch','experimental':'Experimental match · ready to try','patched':'Patch installed','outdated':'Older patch · remove before updating','unsupported':'No compatible loader found','changed':'Changed after backup'}
                self.summary.set('\n'.join(f'{f["build"]}\n{f["file"]} · {labels[f["status"]]}' for f in view['files']))
                self.apply_button.configure(state='normal' if view['can_apply'] else 'disabled')
                self.apply_button.configure(text='Try patch' if any(f['status']=='experimental' for f in view['files']) else 'Add patch')
                self.remove_button.configure(state='normal' if view['can_remove'] else 'disabled')
                if action=='apply':self.message.set('Patch added. Restart this emulator and test a single-file NSP. Original backups are retained.')
                elif action=='remove':self.message.set('Patch removed. Exact original executable bytes restored; backups retained.')
                elif any(f['status']=='outdated' for f in view['files']):self.message.set('An older patch is installed. Remove patch first, then Add patch to install the corrected probe. Your original backup is retained.')
                elif any(f['status']=='experimental' for f in view['files']):self.message.set('Matching loader code found in an unverified build. Trying the patch is experimental. Exact backups will be saved for removal.')
                elif any(f['status'] in ('unsupported','changed') for f in view['files']):self.message.set('Unrecognized files will be left unchanged. See EMULATOR_PATCH.md for compatibility details.')
                else:self.message.set('Build verified. Add or remove the patch below; close the emulator first.')
        except queue.Empty:pass
        self.job=self.after(70,self.poll)
    def close(self):
        if self.working:self.message.set('Wait for the current check or file operation to finish before closing.');return
        self.after_cancel(self.job);self.destroy()
