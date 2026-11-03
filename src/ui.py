"""Minimal native Tk interface, vector graphics, and time-based motion."""
from pathlib import Path
import ctypes, sys, time, queue
import tkinter as tk
from tkinter import ttk
from tkinter import font as tkfont
from PIL import Image, ImageTk, ImageDraw, ImageOps
from functools import lru_cache
from weakref import WeakKeyDictionary
from ambient import AmbientBackground, AmbientFrame, AmbientLabel
from artwork import IMAGE_EXTENSIONS

BG='#0e1726';PANEL='#172338';FIELD='#1c2b42';TEXT='#edf4ff';MUTED='#93a8c8'
ACCENT='#289bff';BORDER='#2a3b56';ICON='#a9c8f3'
ASSET_DIR=Path(__file__).resolve().parent/'assets'/'icons'
_PHOTO_CACHES=WeakKeyDictionary()
ICON_ALIASES={'folder':'browse-folder','download':'game-files','image':'cover-art',
              'cube':'build','file':'save-output','clipboard':'paste','info':'notes'}

@lru_cache(maxsize=64)
def has_icon_asset(kind):
    return (ASSET_DIR/(ICON_ALIASES.get(kind,kind)+'.png')).is_file()

def ui_font(size,bold=False):
    if sys.platform=='win32':return ('Segoe UI Semibold' if bold else 'Segoe UI',size)
    return ('DejaVu Sans',size,'bold' if bold else 'normal')

def rgb(color):return tuple(int(color[i:i+2],16) for i in (1,3,5))
def blend(a,b,t):return '#'+''.join(f'{round(x+(y-x)*max(0,min(1,t))):02x}' for x,y in zip(rgb(a),rgb(b)))
@lru_cache(maxsize=128)
def icon_art(kind,size,color,width):
    """Load the reviewed artwork once per size; small utility marks stay native."""
    asset=ASSET_DIR/(ICON_ALIASES.get(kind,kind)+'.png')
    if asset.is_file():
        with Image.open(asset) as source:
            return source.convert('RGBA').resize((int(size),int(size)),Image.Resampling.LANCZOS)
    scale=4;size=int(size);unit=size*scale/24
    image=Image.new('RGBA',(size*scale,size*scale));d=ImageDraw.Draw(image)
    pen=max(1,round(width*scale));r=pen/2
    def line(*points):
        pts=[(points[i]*unit,points[i+1]*unit) for i in range(0,len(points),2)]
        d.line(pts,fill=color,width=pen,joint='curve')
        for x,y in pts:d.ellipse((x-r,y-r,x+r,y+r),fill=color)
    def oval(box,fill=None):d.ellipse(tuple(p*unit for p in box),fill=fill,outline=None if fill else color,width=pen)
    if kind in ('folder','download'):
        line(2,6,9,6,12,9,22,9,22,21,2,21,2,6)
        if kind=='download':line(12,12,12,18,9,15);line(12,18,15,15)
    elif kind=='image':
        d.rounded_rectangle(tuple(p*unit for p in (2,2,22,22)),radius=3*unit,outline=color,width=pen)
        oval((6,6,10,10));line(3,19,10,12,14,16,17,13,22,19)
    elif kind=='cube':
        line(12,2,22,7,22,18,12,23,2,18,2,7,12,2)
        line(12,2,12,13,22,7);line(2,7,12,13,12,23)
    elif kind=='game':
        line(6,7,18,7,22,18,19,20,15,16,9,16,5,20,2,18,6,7)
        line(6,10,6,15);line(3.5,12.5,8.5,12.5);oval((16,10,18.2,12.2),color);oval((18,13,20.2,15.2),color)
    elif kind=='file':
        line(5,2,14,2,20,8,20,22,5,22,5,2);line(14,2,14,8,20,8);line(9,12,16,12);line(9,16,16,16)
    elif kind=='plus':oval((2,2,22,22));line(12,7,12,17);line(7,12,17,12)
    elif kind=='check':line(5,12,10,17,20,6)
    elif kind=='close':line(6,6,18,18);line(6,18,18,6)
    elif kind=='info':oval((2,2,22,22));line(12,11,12,17);oval((11,6,13,8),color)
    elif kind=='crop':line(7,2,7,17,22,17);line(2,7,17,7,17,22)
    elif kind=='clipboard':
        d.rounded_rectangle(tuple(p*unit for p in (5,4,20,22)),radius=2*unit,outline=color,width=pen)
        d.rounded_rectangle(tuple(p*unit for p in (8,2,17,7)),radius=unit,fill=color)
    return image.resize((size,size),Image.Resampling.LANCZOS)

def icon(c,kind,x,y,size=22,color=ICON,width=1.7,tag='icon'):
    root=c.winfo_toplevel()._root()
    cache=_PHOTO_CACHES.setdefault(root,{})
    # PNGs retain their own palette. Hover colors must not decode/reallocate
    # this same 1K source on every frame of a drop-zone or button animation.
    asset=has_icon_asset(kind)
    key=(kind,int(size),None if asset else color,0 if asset else width)
    photo=cache.get(key)
    if photo is None:
        photo=cache[key]=ImageTk.PhotoImage(icon_art(kind,int(size),ICON if asset else color,1.7 if asset else width),master=c)
    return c.create_image(x,y,image=photo,anchor='nw',tags=(tag,'aa-icon'))

@lru_cache(maxsize=96)
def surface_art(w,h,fill,border,radius,gradient):
    """Cache antialiased geometry; gradient interpolation runs in Pillow's C code."""
    factor=2
    im=Image.new('RGBA',(w*factor,h*factor));d=ImageDraw.Draw(im)
    d.rounded_rectangle((factor,factor,(w-1)*factor,(h-1)*factor),radius=radius*factor,fill=fill,outline=border,width=factor)
    if gradient:
        mask=Image.new('L',im.size);md=ImageDraw.Draw(mask)
        md.rounded_rectangle((2*factor,2*factor,(w-2)*factor,(h-2)*factor),radius=max(1,radius-1)*factor,fill=255)
        ramp=Image.linear_gradient('L').resize((1,h*factor))
        layer=ImageOps.colorize(ramp,gradient[0],gradient[1]).resize(im.size)
        im.paste(layer,(0,0),mask)
    return im.resize((w,h),Image.Resampling.LANCZOS)

def surface(c,w,h,fill,border,radius=17,gradient=None):
    w=max(1,int(w));h=max(1,int(h))
    backdrop=getattr(c.winfo_toplevel(),'_ambient',None)
    if backdrop is not None and c.cget('bg')==BG:
        if c not in backdrop.targets:backdrop.register(c)
        elif not c.find_withtag('ambient'):backdrop.paint(c)
    key=(w,h,fill,border,radius,gradient)
    if getattr(c,'_surface_key',None)!=key:
        c._surface_photo=ImageTk.PhotoImage(surface_art(*key),master=c)
        c._surface_key=key
    photo=c._surface_photo
    return c.create_image(0,0,image=photo,anchor='nw',tags='surface')

class Motion:
    def __init__(self,root):self.root=root;self.enabled=True;self.jobs={};self.closed=False
    def to(self,key,initial,final,duration,update,done=None,easing=None):
        if self.closed:return
        old=self.jobs.pop(key,None)
        if old:
            try:self.root.after_cancel(old)
            except tk.TclError:pass
        if not self.enabled or abs(initial-final)<.001:
            update(final)
            if done:done()
            return
        started=time.perf_counter()
        def tick():
            if self.closed or not self.root.winfo_exists():return
            t=min(1,(time.perf_counter()-started)/duration);ease=easing(t) if easing else 1-(1-t)**4
            try:update(initial+(final-initial)*ease)
            except tk.TclError:self.jobs.pop(key,None);return
            if t<1:self.jobs[key]=self.root.after(16,tick)
            else:
                self.jobs.pop(key,None)
                if done:done()
        tick()
    def stop(self):
        self.closed=True
        for job in self.jobs.values():
            try:self.root.after_cancel(job)
            except tk.TclError:pass
        self.jobs.clear()

class Button(tk.Canvas):
    def __init__(self,parent,text,command,motion,width=155,height=43,kind=None,primary=False,quiet=False,state='normal',**kw):
        super().__init__(parent,width=width,height=height,bg=parent.cget('bg'),highlightthickness=0,
                         bd=0,takefocus=True,cursor='hand2',**kw)
        self.text=text;self.command=command;self.motion=motion;self.kind=kind;self.primary=primary
        self.quiet=quiet;self.enabled=state!='disabled';self.hot=0.;self.pressed=False;self.focused=False
        self.press_depth=0.;self.selection=1. if primary else 0.;self._metrics=None
        self.bind('<Configure>',lambda e:self.draw());self.bind('<Enter>',lambda e:self.hover(1))
        self.bind('<Leave>',lambda e:self.hover(0));self.bind('<ButtonPress-1>',self.press)
        self.bind('<ButtonRelease-1>',self.release);self.bind('<Return>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke());self.bind('<FocusIn>',lambda e:self.focus(True))
        self.bind('<FocusOut>',lambda e:self.focus(False))
    def configure(self,cnf=None,**kw):
        if 'state' in kw:
            self.enabled=kw.pop('state')!='disabled'
            super().configure(cursor='hand2' if self.enabled else 'arrow',takefocus=self.enabled)
        if 'text' in kw:self.text=kw.pop('text')
        if cnf or kw:super().configure(cnf,**kw)
        if hasattr(self,'hot'):self.draw()
    config=configure
    def focus(self,value):self.focused=value;self.draw()
    def hover(self,target):
        if not self.enabled:target=0
        self.motion.to((id(self),'hover'),self.hot,target,.23,self.paint_hover)
    def paint_hover(self,value):self.hot=value;self.draw()
    def press(self,event):
        if self.enabled:
            self.focus_set();self.pressed=True
            self.motion.to((id(self),'press'),self.press_depth,1.,.12,self.paint_press)
    def release(self,event):
        pressed=self.pressed;self.pressed=False
        self.motion.to((id(self),'press'),self.press_depth,0.,.24,self.paint_press)
        if pressed and 0<=event.x<self.winfo_width() and 0<=event.y<self.winfo_height():self.invoke()
    def paint_press(self,value):self.press_depth=value;self.draw()
    def set_selected(self,selected):
        self.primary=selected;self.quiet=not selected
        self.motion.to((id(self),'selection'),self.selection,float(selected),.30,self.paint_selection)
    def paint_selection(self,value):self.selection=value;self.draw()
    def invoke(self):
        if self.enabled and self.command:self.command()
    def draw(self):
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        if w<3:return
        bg=self.cget('bg');base='#163d66' if self.primary else '#22344e'
        fill=blend(base,'#3d608c',self.hot*.48)
        if self.primary or self.selection>.001:
            top=blend('#1baaff','#68c6ff',self.hot*.45);bottom=blend('#0568ed','#398bff',self.hot*.5)
            if not self.enabled:top=bottom='#244361'
            top=blend(top,'#071323',self.press_depth*.16);bottom=blend(bottom,'#071323',self.press_depth*.16)
            top=blend(bg,top,self.selection);bottom=blend(bg,bottom,self.selection)
            border=blend('#137ce8','#85d3ff',self.hot*.6)
            surface(self,w,h,top,border,14,(top,bottom))
        else:
            if self.quiet:fill=blend(bg,'#233752',self.hot)
            if not self.enabled:fill=blend(fill,bg,.6)
            fill=blend(fill,'#081321',self.press_depth*.22)
            border=blend('#3b5478','#6c9bd4',self.hot) if not self.quiet else fill
            surface(self,w,h,fill,'#9bcfff' if self.focused else border,14)
        color=TEXT if self.enabled else '#647c9c'
        font=ui_font(10,True)
        if self._metrics is None or self._metrics[0]!=(self.text,font):
            self._metrics=((self.text,font),tkfont.Font(self,font=font).measure(self.text))
        tw=self._metrics[1];total=tw+(29 if self.kind else 0);start=(w-total)/2
        dy=1.5*self.press_depth
        if self.kind:icon(self,self.kind,start,(h-21)/2+dy,21,color)
        self.create_text(start+(29 if self.kind else 0),h/2+dy,text=self.text,anchor='w',fill=color,font=font)

class Panel(tk.Canvas):
    def __init__(self,parent,**kw):
        self.fluid_resize=kw.pop('fluid_resize',False);self._fluid_width=None
        kw.setdefault('width',1);kw.setdefault('height',1)
        super().__init__(parent,bg=BG,highlightthickness=0,bd=0,**kw)
        self.inner=tk.Frame(self,bg=PANEL);self.inner_id=self.create_window(1,1,anchor='nw',window=self.inner)
        self.bind('<Configure>',self.resize)
        backdrop=getattr(self.winfo_toplevel(),'_ambient',None)
        if backdrop is not None:backdrop.register(self)
    def resize(self,event):
        if self.fluid_resize and event.height>=52:
            self.resize_fluid_surface(event.width,event.height)
        else:
            self._fluid_width=None
            self.delete('surface');surface(self,event.width,event.height,PANEL,'#263750',22)
        self.tag_lower('surface')
        if self.find_withtag('ambient'):self.tag_lower('ambient')
        self.coords(self.inner_id,15,14)
        self.itemconfigure(self.inner_id,width=max(1,event.width-30),height=max(1,event.height-28))

    def resize_fluid_surface(self,width,height):
        """Reuse rounded caps while height changes; avoid full-card rasterization."""
        cap=24
        if self._fluid_width!=width:
            self.delete('surface')
            art=surface_art(max(1,width),52,PANEL,'#263750',22,None)
            self._fluid_photos=(ImageTk.PhotoImage(art.crop((0,0,width,cap)),master=self),
                                ImageTk.PhotoImage(art.crop((0,52-cap,width,52)),master=self))
            self._fluid_middle=self.create_rectangle(2,cap,width-2,height-cap,fill=PANEL,outline='',tags='surface')
            self._fluid_left=self.create_line(1,cap,1,height-cap,fill='#263750',tags='surface')
            self._fluid_right=self.create_line(width-2,cap,width-2,height-cap,fill='#263750',tags='surface')
            self.create_image(0,0,image=self._fluid_photos[0],anchor='nw',tags='surface')
            self._fluid_bottom=self.create_image(0,height-cap,image=self._fluid_photos[1],anchor='nw',tags='surface')
            self._fluid_width=width
        self.coords(self._fluid_middle,2,cap,width-2,height-cap)
        self.coords(self._fluid_left,1,cap,1,height-cap)
        self.coords(self._fluid_right,width-2,cap,width-2,height-cap)
        self.coords(self._fluid_bottom,0,height-cap)

class Entry(tk.Canvas):
    """Rounded field with a genuine native text editor and clean focus states."""
    def __init__(self,parent,placeholder='',**kw):
        width=kw.pop('width',15);font=kw.pop('font',ui_font(10))
        super().__init__(parent,bg=parent.cget('bg'),width=width*8,height=41,bd=0,highlightthickness=0)
        self.entry=tk.Entry(self,bd=0,highlightthickness=0,bg=FIELD,fg=TEXT,insertbackground=TEXT,
            readonlybackground=FIELD,disabledbackground=FIELD,disabledforeground='#7188a8',
            selectbackground='#245b8f',selectforeground=TEXT,font=font,**kw)
        self.item=self.create_window(13,20,anchor='w',window=self.entry)
        self.hint=tk.Label(self,text=placeholder,bg=FIELD,fg='#829ab9',font=ui_font(9),bd=0,cursor='xterm')
        self.hint.bind('<Button-1>',lambda e:self.entry.focus_set())
        super().bind('<Configure>',lambda e:self.draw())
        self.entry.bind('<FocusIn>',lambda e:self.draw());self.entry.bind('<FocusOut>',lambda e:self.draw())
        self.entry.bind('<Button-1>',lambda e:self.draw(),add=True)
        variable=kw.get('textvariable')
        if variable:variable.trace_add('write',lambda *a:self.refresh_hint())
    def bind(self,sequence=None,func=None,add=None):
        return self.entry.bind(sequence,func,add) if hasattr(self,'entry') else super().bind(sequence,func,add)
    def get(self):return self.entry.get()
    def configure(self,cnf=None,**kw):
        if 'state' in kw:self.entry.configure(state=kw.pop('state'))
        if cnf or kw:super().configure(cnf,**kw)
        if hasattr(self,'entry'):self.draw()
    config=configure
    def draw(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<3:return
        self.delete('surface');surface(self,w,h,FIELD,'#64b4ff' if self.focus_get() is self.entry else '#354b68',13)
        self.tag_lower('surface');self.coords(self.item,13,h/2);self.itemconfigure(self.item,width=max(1,w-26))
        self.refresh_hint()
    def refresh_hint(self):
        if not self.get() and self.focus_get() is not self.entry:self.hint.place(x=13,rely=.5,anchor='w')
        else:self.hint.place_forget()

class Combo(tk.Canvas):
    def __init__(self,parent,**kw):
        super().__init__(parent,bg=parent.cget('bg'),width=160,height=37,bd=0,highlightthickness=0)
        self.entry=ttk.Combobox(self,style='Flat.TCombobox',**kw)
        self.item=self.create_window(12,18,anchor='w',window=self.entry)
        super().bind('<Configure>',lambda e:self.draw())
        self.entry.bind('<FocusIn>',lambda e:self.draw());self.entry.bind('<FocusOut>',lambda e:self.draw())
    def bind(self,sequence=None,func=None,add=None):return self.entry.bind(sequence,func,add)
    def configure(self,cnf=None,**kw):
        if 'state' in kw:self.entry.configure(state=kw.pop('state'))
        if cnf or kw:super().configure(cnf,**kw)
    config=configure
    def __setitem__(self,key,value):self.entry.configure(**{key:value})
    def current(self,index=None):return self.entry.current(index) if index is not None else self.entry.current()
    def get(self):return self.entry.get()
    def draw(self):
        w=self.winfo_width();h=self.winfo_height()
        if w<3:return
        self.delete('surface');surface(self,w,h,FIELD,'#64b4ff' if self.focus_get() is self.entry else '#354b68',12)
        self.tag_lower('surface');self.coords(self.item,12,h/2);self.itemconfigure(self.item,width=max(1,w-24))

class DropZone(tk.Canvas):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL,highlightthickness=0,height=172,bd=0)
        self.app=app;self.hot=0;self.bind('<Configure>',lambda e:self.draw())
        self.bind('<Enter>',lambda e:self.hover(1));self.bind('<Leave>',lambda e:self.hover(0))
        self.app.folder.trace_add('write',lambda *args:self.draw())
    def hover(self,value):self.app.motion.to((id(self),'hover'),self.hot,value,.2,self.paint)
    def paint(self,value):self.hot=value;self.draw()
    def draw(self):
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        if w<4:return
        surface(self,w,h,blend('#192b43','#1d3859',self.hot),blend('#425979','#6faeff',self.hot),20)
        # Reserve the real button footprint, then fit the text above it. Fixed
        # percentages used to overlap the button at compact window sizes.
        button=getattr(self.app,'browse',None)
        fill=blend('#192b43','#1d3859',self.hot)
        if button is not None and button.cget('bg')!=fill:
            button.configure(bg=fill)  # Rounded corners must match this surface.
        button_top=h-12-(button.winfo_reqheight() if button is not None else 37)
        compact=h<112
        title_font=ui_font(12 if compact else 13,True);subtitle_font=ui_font(9 if compact else 10)
        title_height=tkfont.Font(self,font=title_font).metrics('linespace')
        subtitle_height=tkfont.Font(self,font=subtitle_font).metrics('linespace')
        text_height=title_height+3+subtitle_height
        padding=4 if compact else 8
        available=max(0,button_top-2*padding)
        show_icon=available>=text_height+52
        block_height=text_height+(52 if show_icon else 0)
        top=padding+max(0,(available-block_height)/2)
        if show_icon:
            icon(self,'download',w/2-20,top,40,blend('#7297c9','#a6ceff',self.hot),2.1)
            top+=52
        selected=Path(self.app.folder.get()).name if self.app.folder.get() else None
        title=selected or ('Drop your game folder here' if sys.platform=='win32' else 'Select your game folder')
        if len(title)>56:title=title[:53]+'…'
        self.create_text(w/2,top+title_height/2,text=title,fill='#bdd6fa',font=title_font,tags='folder-title')
        self.create_text(w/2,top+title_height+3+subtitle_height/2,
                         text='Choose another folder' if selected else 'or choose a folder manually',
                         fill=MUTED,font=subtitle_font,tags='folder-subtitle')

class Cover(tk.Canvas):
    def __init__(self,parent,app):
        super().__init__(parent,bg=PANEL,width=240,height=220,highlightthickness=0,bd=0,cursor='hand2')
        self.app=app;self.picture=None;self.photo=None;self.hot=0;self._photo_side=0
        self.bind('<Configure>',lambda e:self.draw());self.bind('<Button-1>',lambda e:app.pick_art() if not app.busy else None)
        self.bind('<Enter>',lambda e:self.hover(1));self.bind('<Leave>',lambda e:self.hover(0))
    def hover(self,value):self.app.motion.to((id(self),'hover'),self.hot,value,.18,self.paint)
    def paint(self,value):self.hot=value;self.draw()
    def set_picture(self,image):
        self.picture=image.copy() if image is not None else None
        self._photo_side=0;self.reveal_t=0.
        self.draw();self.app.motion.to((id(self),'reveal'),0,1,.42,self.reveal)
    def reveal(self,t):
        # A small lift reveals replacement art without changing the image itself.
        self.reveal_t=t
        self.move('artwork',0,(self._art_y+8*(1-t))-self.coords('artwork')[1]) if self.find_withtag('artwork') else None
    def draw(self):
        self.delete('all');w=self.winfo_width();h=self.winfo_height()
        if w<3:return
        surface(self,w,h,blend('#213552','#28496f',self.hot*.45),blend('#344b6c','#75a6e3',self.hot),20)
        if self.picture:
            side=max(32,min(w-24,h-24,256))
            if self._photo_side!=side:
                self.photo=ImageTk.PhotoImage(self.picture.resize((side,side),Image.Resampling.LANCZOS));self._photo_side=side
            self._art_y=h/2;self.create_image(w/2,h/2+8*(1-getattr(self,'reveal_t',1)),image=self.photo,tags='artwork')
        else:
            icon(self,'image',w/2-43,h*.38-43,86,'#6488b9',3)
            self.create_text(w/2,h*.69,text='Add cover artwork',fill='#b0c9ee',font=ui_font(11,True))
            self.create_text(w/2,h*.69+28,text='WEBP, PNG, JPG + more',fill=MUTED,font=ui_font(9))

class Progress(tk.Canvas):
    def __init__(self,parent,motion):
        super().__init__(parent,height=3,bg='#18243a',highlightthickness=0,bd=0)
        self.value=0;self.motion=motion;self.bind('<Configure>',lambda e:self.draw())
    def __setitem__(self,key,value):
        if key=='value':self.motion.to((id(self),'progress'),self.value,float(value),.24,self.update_value)
        else:super().__setitem__(key,value)
    def update_value(self,value):self.value=value;self.draw()
    def draw(self):
        self.delete('all');w=self.winfo_width()
        self.create_rectangle(0,0,w*self.value/100,4,fill=ACCENT,outline='')

class Check(tk.Canvas):
    def __init__(self,parent,text,variable,kind=None):
        super().__init__(parent,bg=parent.cget('bg'),height=25,width=280 if kind else 230,highlightthickness=0,bd=0,takefocus=True,cursor='hand2')
        self.text=text;self.variable=variable;self.enabled=True;self.kind=kind
        self.bind('<Configure>',lambda e:self.draw());self.bind('<Button-1>',lambda e:self.invoke())
        self.bind('<space>',lambda e:self.invoke());self.bind('<Return>',lambda e:self.invoke())
        self.bind('<FocusIn>',lambda e:self.draw());self.bind('<FocusOut>',lambda e:self.draw())
        variable.trace_add('write',lambda *a:self.draw())
    def invoke(self):
        if self.enabled:self.focus_set();self.variable.set(not self.variable.get())
    def configure(self,cnf=None,**kw):
        if 'state' in kw:self.enabled=kw.pop('state')!='disabled'
        if cnf or kw:super().configure(cnf,**kw)
        if hasattr(self,'variable'):self.draw()
    config=configure
    def draw(self):
        self.delete('all');checked=self.variable.get()
        surface(self,22,22,'#168ff8' if checked else FIELD,'#8bcaff' if self.focus_get() is self else ('#3ba8ff' if checked else '#546d90'),6)
        if checked:icon(self,'check',3,3,16,TEXT,1.8)
        if self.kind:icon(self,self.kind,31,1,21)
        self.create_text(58 if self.kind else 31,11,text=self.text,anchor='w',fill=TEXT if self.enabled else MUTED,font=ui_font(10))

class Status(tk.Canvas):
    def __init__(self,parent,app):
        super().__init__(parent,width=43,height=43,bg=BG,highlightthickness=0,bd=0)
        self.app=app;self.color='#53bd7b';self.phase=0;self.running=False;self.job=None
        app.status.trace_add('write',self.changed);self.bind('<Configure>',lambda e:self.draw());self.draw()
    def changed(self,*args):
        text=self.app.status.get().lower()
        target='#e99c63' if any(x in text for x in ('could not','cancel','supported')) else ('#349cff' if self.app.busy or self.app.scanning else '#53bd7b')
        start=self.color
        self.app.motion.to((id(self),'status'),0,1,.2,lambda t:self.paint_color(blend(start,target,t)))
        if (self.app.busy or self.app.scanning) and not self.running:self.running=True;self.spin()
    def paint_color(self,value):self.color=value;self.draw()
    def spin(self):
        self.job=None
        if not self.winfo_exists():return
        self.phase=(self.phase+5)%360;self.draw()
        if (self.app.busy or self.app.scanning) and self.app.motion.enabled:self.job=self.after(16,self.spin)
        else:self.running=False;self.draw()
    def stop(self):
        if self.job is not None:self.after_cancel(self.job);self.job=None
    def draw(self):
        self.delete('all');surface(self,43,43,self.color,self.color,21)
        if self.app.busy or self.app.scanning:
            self.create_arc(11,11,31,31,start=self.phase,extent=245,style='arc',outline=TEXT,width=2.3)
        else:icon(self,'check',10,10,22,TEXT,2)

class FileDrops:
    """Windows shell file drops. Hooks only this app's own top-level window."""
    def __init__(self,root,receive):
        self.root=root;self.receive=receive;self.old=None;self.callback=None;self.hwnd=None
        self.pending=queue.SimpleQueue();self.job=None;self.closed=False
        if sys.platform!='win32':return
        from ctypes import wintypes as w
        self.user=ctypes.WinDLL('user32',use_last_error=True);self.shell=ctypes.WinDLL('shell32',use_last_error=True)
        self.user.GetParent.argtypes=[w.HWND];self.user.GetParent.restype=w.HWND
        self.user.SetWindowLongPtrW.argtypes=[w.HWND,ctypes.c_int,ctypes.c_void_p];self.user.SetWindowLongPtrW.restype=ctypes.c_void_p
        self.user.CallWindowProcW.argtypes=[ctypes.c_void_p,w.HWND,w.UINT,w.WPARAM,w.LPARAM];self.user.CallWindowProcW.restype=ctypes.c_ssize_t
        self.shell.DragAcceptFiles.argtypes=[w.HWND,w.BOOL]
        self.shell.DragQueryFileW.argtypes=[w.HANDLE,w.UINT,w.LPWSTR,w.UINT];self.shell.DragQueryFileW.restype=w.UINT
        self.shell.DragFinish.argtypes=[w.HANDLE]
        root.update_idletasks();self.hwnd=self.user.GetParent(root.winfo_id()) or root.winfo_id()
        signature=ctypes.WINFUNCTYPE(ctypes.c_ssize_t,w.HWND,w.UINT,w.WPARAM,w.LPARAM)
        @signature
        def proc(hwnd,message,wp,lp):
            if message==0x233:
                paths=[]
                try:
                    for i in range(min(256,self.shell.DragQueryFileW(wp,0xffffffff,None,0))):
                        count=self.shell.DragQueryFileW(wp,i,None,0)
                        if count>32767:continue
                        buffer=ctypes.create_unicode_buffer(count+1);self.shell.DragQueryFileW(wp,i,buffer,count+1);paths.append(buffer.value)
                    self.pending.put(paths)
                finally:self.shell.DragFinish(wp)
                # Never enter Tcl/Tk from a ctypes Windows procedure. mainloop
                # releases Tcl's Python thread state during native dispatch;
                # calling even root.after here can abort the entire process.
                return 0
            return self.user.CallWindowProcW(self.old,hwnd,message,wp,lp)
        self.callback=proc;ctypes.set_last_error(0)
        self.old=self.user.SetWindowLongPtrW(self.hwnd,-4,ctypes.cast(proc,ctypes.c_void_p))
        if not self.old:raise ctypes.WinError(ctypes.get_last_error())
        self.shell.DragAcceptFiles(self.hwnd,True)
        self.job=root.after(40,self.drain)
    def drain(self):
        self.job=None
        if self.closed:return
        try:
            for _ in range(8):
                try:paths=self.pending.get_nowait()
                except queue.Empty:break
                if paths:self.receive(paths)
        finally:
            if not self.closed:self.job=self.root.after(40,self.drain)
    def close(self):
        self.closed=True
        if self.job:
            self.root.after_cancel(self.job);self.job=None
        if self.old and self.hwnd:
            self.shell.DragAcceptFiles(self.hwnd,False);self.user.SetWindowLongPtrW(self.hwnd,-4,self.old);self.old=None

class Layout:
    def style(self):
        self.motion=Motion(self)
        if sys.platform=='win32':
            enabled=ctypes.c_int(1)
            if ctypes.windll.user32.SystemParametersInfoW(0x1042,0,ctypes.byref(enabled),0):self.motion.enabled=bool(enabled.value)
        s=ttk.Style(self);s.theme_use('clam')
        s.configure('.',font=ui_font(10),background=PANEL,foreground=TEXT)
        s.configure('TEntry',fieldbackground=FIELD,foreground=TEXT,bordercolor='#344962',lightcolor='#344962',darkcolor='#344962',
                    padding=(11,10),insertcolor=TEXT,selectbackground='#225d96')
        s.map('TEntry',fieldbackground=[('disabled','#17243a'),('readonly',FIELD)],foreground=[('disabled','#7188a8'),('readonly','#bdd1ef')],bordercolor=[('focus','#5faeff')])
        s.configure('TCombobox',fieldbackground=FIELD,background=FIELD,foreground=TEXT,arrowcolor=ICON,padding=(10,8),bordercolor='#344962')
        s.map('TCombobox',fieldbackground=[('readonly',FIELD)],foreground=[('readonly',TEXT)],selectbackground=[('readonly',FIELD)])
        self.option_add('*TCombobox*Listbox.background',FIELD);self.option_add('*TCombobox*Listbox.foreground',TEXT)
        s.configure('Flat.TCombobox',borderwidth=0,relief='flat',padding=(0,3),fieldbackground=FIELD,
                    background=FIELD,lightcolor=FIELD,darkcolor=FIELD,bordercolor=FIELD,arrowcolor=ICON)
        s.map('Flat.TCombobox',fieldbackground=[('readonly',FIELD)],foreground=[('readonly',TEXT)],
              selectbackground=[('readonly',FIELD)],bordercolor=[('focus',FIELD)])
        s.configure('TCheckbutton',background=PANEL,foreground=TEXT,indicatorbackground=FIELD,indicatorforeground=TEXT,padding=0)
        s.map('TCheckbutton',background=[('active',PANEL)])
        s.configure('TLabel',background=BG,foreground=TEXT);s.configure('Section.TLabel',font=ui_font(12,True))
        s.configure('TButton',padding=(12,9),background=FIELD,foreground=TEXT,bordercolor=BORDER)
        s.map('TButton',background=[('active','#294566')]);s.configure('TFrame',background=BG)

    def label(self,parent,text=None,var=None,color=TEXT,size=10,bold=False,**kw):
        label_type=AmbientLabel if isinstance(parent,AmbientFrame) else tk.Label
        return label_type(parent,text=text,textvariable=var,bg=parent.cget('bg'),fg=color,
                        font=ui_font(size,bold),bd=0,**kw)

    def heading(self,parent,title,kind):
        row=tk.Frame(parent,bg=PANEL);row.pack(fill='x',pady=(0,10))
        c=tk.Canvas(row,width=25,height=25,bg=PANEL,bd=0,highlightthickness=0);c.pack(side='left',padx=(0,10));icon(c,kind,1,1,23)
        self.label(row,title,size=12,bold=True).pack(side='left')

    def layout(self):
        self.configure(bg=BG);self.geometry('1160x880');self.minsize(1010,830)
        self._ambient=AmbientBackground(self,self.motion)
        self.title_id_text=tk.StringVar(value='Detected automatically');self.snapshot_info=tk.StringVar(value='Choose a game folder to begin.')
        header=AmbientFrame(self);header.pack(fill='x',padx=24,pady=(19,14))
        mark=tk.Canvas(header,width=60,height=60,bg=BG,highlightthickness=0);mark.pack(side='left',padx=(0,17))
        self._ambient.register(mark);icon(mark,'app',0,0,60)
        title=AmbientFrame(header,width=355,height=60);title.pack(side='left')
        title.create_text(0,0,text='NSP Box',anchor='nw',fill=TEXT,font=ui_font(26,True))
        title.create_text(1,42,text='Nintendo Switch 2 · games & DLC',anchor='nw',fill='#aec6e9',font=ui_font(11))
        self.help_btn=Button(header,'Notes & compatibility',self.notes,self.motion,width=192,quiet=True,kind='notes');self.help_btn.pack(side='right')
        self.emulator_patch_btn=Button(header,'Emulator patch',self.emulator_patch,self.motion,width=156,quiet=True,kind='emulator-patch');self.emulator_patch_btn.pack(side='right',padx=(0,10))
        tabs=AmbientFrame(self);tabs.pack(fill='x',padx=24,pady=(0,10))
        self.game_tab_button=Button(tabs,'Game',lambda:self.show_tab('game'),self.motion,width=112,height=36,primary=True,kind='game')
        self.game_tab_button.pack(side='left',padx=(0,8))
        self.dlc_tab_button=Button(tabs,'DLC',lambda:self.show_tab('dlc'),self.motion,width=108,height=36,quiet=True,kind='dlc')
        self.dlc_tab_button.pack(side='left')
        self.nup_tab_button=Button(tabs,'NUP Tools',lambda:self.show_tab('nup'),self.motion,width=145,height=36,quiet=True,kind='package-folder')
        self.nup_tab_button.pack(side='left',padx=(8,0))
        footer=AmbientFrame(self);footer.pack(side='bottom',fill='x')
        self.game_footer=footer
        self.progressbar=Progress(footer,self.motion);self.progressbar.pack(fill='x')
        action=AmbientFrame(footer);action.pack(fill='x',padx=24,pady=(16,18))
        self.status_icon=Status(action,self);self.status_icon.pack(side='left',padx=(0,12))
        status=AmbientFrame(action);status.pack(side='left',fill='x',expand=True)
        self.label(status,var=self.status,bold=True,size=11,anchor='w').pack(anchor='w')
        self.detail_label=self.label(status,var=self.detail,color=MUTED,size=9,anchor='w');self.detail_label.pack(anchor='w',pady=(3,0))
        self.build_btn=Button(action,'Build NSP',self.start,self.motion,width=155,height=47,kind='build',primary=True);self.build_btn.pack(side='right',padx=(10,0))
        self.cancel_btn=Button(action,'Cancel',self.cancel,self.motion,width=105,height=47,kind='cancel',state='disabled');self.cancel_btn.pack(side='right',padx=(10,0))
        self.open_btn=Button(action,'Open output folder',self.open_output,self.motion,width=190,height=47,kind='open-output',state='disabled');self.open_btn.pack(side='right',padx=(12,0))
        area=AmbientFrame(self);area.pack(fill='both',expand=True,padx=20,pady=(0,12));self.content_area=area;self._compact=False
        area.grid_columnconfigure(0,weight=1);area.grid_columnconfigure(1,minsize=270)
        area.grid_rowconfigure(0,weight=1,minsize=255);area.grid_rowconfigure(1,minsize=186);area.grid_rowconfigure(2,minsize=185)
        self.panels=[]
        game=Panel(area);game.grid(row=0,column=0,sticky='nsew',padx=(0,12),pady=(0,10));self.panels.append(game)
        self.heading(game.inner,'Game files','game-files')
        self.drop_zone=DropZone(game.inner,self)
        self.browse=Button(self.drop_zone,'Browse folder',self.pick_folder,self.motion,width=172,height=37,kind='browse-folder')
        self.browse.place(relx=.5,rely=1,anchor='s',y=-12)
        # Pack the fixed-height editor first so the expanding drop target cannot
        # consume its allocation and leave just a sliver of placeholder text.
        pathrow=tk.Frame(game.inner,bg=PANEL);pathrow.pack(side='bottom',fill='x',pady=(9,0))
        self.folder_entry=Entry(pathrow,textvariable=self.folder,font=ui_font(9),placeholder='Or paste a folder path and press Enter');self.folder_entry.configure(height=35);self.folder_entry.pack(fill='x')
        self.folder_entry.bind('<Return>',lambda e:self.scan())
        self.drop_zone.pack(fill='both',expand=True)
        details=Panel(area);details.grid(row=1,column=0,sticky='nsew',padx=(0,12),pady=(0,10));self.panels.append(details)
        self.heading(details.inner,'Game details','game-details')
        fields=tk.Frame(details.inner,bg=PANEL);fields.pack(fill='x')
        for col,weight in enumerate((22,17,10)):
            fields.grid_columnconfigure(col,weight=weight)
        self.name_entry=None
        for col,(text,var) in enumerate([('Title',self.title_text),('Title ID',self.title_id_text),('Display version',self.version_text)]):
            frame=tk.Frame(fields,bg=PANEL);frame.grid(row=0,column=col,sticky='ew',padx=(0,12) if col<2 else 0)
            self.label(frame,text,color=MUTED,size=9).pack(anchor='w',pady=(0,6))
            entry=Entry(frame,textvariable=var,width=12,placeholder='Detected automatically' if col==0 else '');entry.pack(fill='x')
            if col==0:self.name_entry=entry
            elif col==1:entry.configure(state='readonly');self.id_entry=entry
            else:self.version_entry=entry
        snapshot=tk.Frame(details.inner,bg=PANEL);snapshot.pack(fill='x',pady=(10,0))
        self.label(snapshot,'Snapshot',color=MUTED,size=9).pack(side='left',padx=(0,12))
        self.combo=Combo(snapshot,textvariable=self.snapshot_label,state='readonly',font=ui_font(9));self.combo.pack(side='left',fill='x',expand=True)
        self.combo.bind('<<ComboboxSelected>>',lambda e:self.select_snapshot())
        out=Panel(area);out.grid(row=2,column=0,sticky='nsew',padx=(0,12));self.panels.append(out)
        self.heading(out.inner,'NSP output','save-output')
        outrow=tk.Frame(out.inner,bg=PANEL);outrow.pack(fill='x')
        self.out_entry=Entry(outrow,textvariable=self.output,placeholder='Choose where to save your package');self.out_entry.pack(side='left',fill='x',expand=True)
        self.save_btn=Button(outrow,'',self.pick_output,self.motion,width=45,height=39,kind='save-output');self.save_btn.pack(side='right',padx=(7,0))
        self.verify_check=Check(out.inner,text='Verify after building',variable=self.verify,kind='verify');self.verify_check.pack(anchor='w',pady=(10,0))
        self.package_folder_check=Check(out.inner,text='Create package folder',variable=self.package_folder,kind='package-folder');self.package_folder_check.pack(anchor='w',pady=(5,0))
        art=Panel(area);art.grid(row=0,column=1,rowspan=2,sticky='nsew',pady=(0,10));self.panels.append(art)
        self.heading(art.inner,'Cover art','cover-art')
        self.preview=Cover(art.inner,self);self.preview.pack(fill='both',expand=True,pady=(1,12))
        artrow=tk.Frame(art.inner,bg=PANEL);artrow.pack(fill='x')
        self.art_btn=Button(artrow,'Add artwork',self.pick_art,self.motion,kind='add-artwork',height=44,width=145);self.art_btn.pack(side='left',fill='x',expand=True)
        self.paste_art_btn=Button(artrow,'Paste',self.paste_art,self.motion,kind='paste',height=44,width=83);self.paste_art_btn.pack(side='right',padx=(8,0))
        self.art_name=tk.StringVar(value='256 × 256 square icon')
        self.label(art.inner,var=self.art_name,color=MUTED,size=9,wraplength=235,anchor='w',justify='left').pack(anchor='w',pady=(10,2))
        arttools=tk.Frame(art.inner,bg=PANEL);arttools.pack(fill='x')
        self.crop_art_btn=Button(arttools,'Crop icon',self.crop_art,self.motion,width=124,height=31,quiet=True,kind='crop',state='disabled');self.crop_art_btn.pack(side='left')
        self.clear_art_btn=Button(arttools,'Remove',self.clear_art,self.motion,width=99,height=31,quiet=True,kind='remove-artwork');self.clear_art_btn.pack(side='right')
        small=AmbientFrame(area);small.grid(row=2,column=1,sticky='nw',padx=7,pady=8)
        self.game_run_note=self.label(small,'Running Switch 2 NSPs\n1. Keep the game’s main.npdm beside its NSP.\n2. Or use a supported emulator in Emulator patch.\n\nUse each game’s own file. Newer PokeDinner needs no patch.',color=MUTED,size=9,wraplength=245,justify='left')
        self.game_run_note.pack(anchor='w')
        self.bind('<Configure>',self.resized,add=True)
        self._visual_jobs=set();self.defer_visual(60,self.enter_panels)
        self._drops=None;self.defer_visual(100,self.setup_drops)
        self._window_icon=ImageTk.PhotoImage(self.draw_app_icon())
        self.iconphoto(True,self._window_icon)

    def draw_app_icon(self):
        return icon_art('app',256,TEXT,1.7).copy()

    def defer_visual(self,delay,callback):
        def run():
            self._visual_jobs.discard(job)
            if not self.motion.closed:callback()
        job=self.after(delay,run);self._visual_jobs.add(job)

    def enter_panels(self,panels=None):
        for i,panel in enumerate(self.panels if panels is None else panels):
            def start(p=panel):
                def step(t):
                    if p.winfo_exists():p.coords(p.inner_id,15,14+10*(1-t))
                self.motion.to((id(p),'entrance'),0,1,.42,step)
            self.defer_visual(i*35,start)

    def resized(self,event):
        if event.widget is self and hasattr(self,'detail_label'):
            self.detail_label.configure(wraplength=max(220,event.width-620))
            compact=event.height<860
            if compact!=self._compact:
                self._compact=compact
                self.drop_zone.configure(height=95 if compact else 150)
                for row,size in enumerate((205,184,175) if compact else (255,186,185)):
                    self.content_area.grid_rowconfigure(row,minsize=size)

    def setup_drops(self):
        try:self._drops=FileDrops(self,self.receive_drop)
        except (OSError,AttributeError):
            self._drops=None
            # Browsing and path entry remain available when the shell disallows drops.
            self.drop_zone.draw()

    def receive_drop(self,paths):
        if getattr(self,'active_tab','game')=='nup':
            if len(paths)==1:self.nup_panel.receive_drop(paths[0])
            else:self.nup_panel.status.set('Drop one folder or package at a time.')
            return
        if getattr(self,'active_tab','game')=='dlc':
            panel=self.dlc_panel
            if panel.busy:return
            if len(paths)==1 and Path(paths[0]).is_dir():
                panel.folder.set(str(paths[0]));panel.title_id.set('');panel.scan()
            elif len(paths)==1 and Path(paths[0]).suffix.lower() =='.nsp':
                panel.base_game.set(str(paths[0]))
                if panel.folder.get().strip():panel.scan()
            else:
                from tkinter import messagebox
                messagebox.showinfo('DLC input','Drop one extracted DLC folder or a base-game NSP.',parent=self)
            return
        if self.busy or self.scanning:return
        if len(paths)!=1:
            from tkinter import messagebox
            messagebox.showinfo('Choose one item','Drop one game folder or artwork image at a time.',parent=self);return
        path=Path(paths[0])
        if path.is_dir():self.folder.set(str(path));self.scan()
        elif path.suffix.lower() in IMAGE_EXTENSIONS:self.set_art(path)
        else:
            from tkinter import messagebox
            messagebox.showinfo('Choose a folder or image','Drop an extracted game folder or supported artwork image (WEBP, PNG, JPG, GIF, TIFF, ICO, ICNS, AVIF and more).',parent=self)

    def refresh_details(self):
        i=self.combo.current()
        if 0<=i<len(self.snapshots):self.title_id_text.set(f'{self.snapshots[i].title_id:016X}')
        else:self.title_id_text.set('Detected automatically')
