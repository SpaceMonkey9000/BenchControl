"""Display-only graph scale selection. Never changes PSU settings."""
import math
import tkinter as tk
from tkinter import ttk,messagebox

SCALE_MODES=('Channel limits','Full range','Manual')


def positive_scale(value):
    try:value=float(value)
    except (ValueError,TypeError):raise ValueError('Graph maximum must be a positive finite number') from None
    if not math.isfinite(value) or value<=0:raise ValueError('Graph maximum must be a positive finite number')
    return value


def graph_top(ch,metric,reading=None,mode='Channel limits',manual_max=None):
    current=metric.startswith('Current')
    full=3. if current else (5. if ch==2 else 30.)
    if reading is not None:
        model_max=getattr(reading,'max_current' if current else 'max_voltage',None)
        if model_max is not None:full=model_max
    if mode=='Full range':return full
    if mode=='Manual':return positive_scale(manual_max)
    if mode!='Channel limits':raise ValueError('Unknown graph scale mode')
    setting=(reading.set_current if current else reading.set_voltage) if reading is not None else 0
    if not math.isfinite(setting) or setting<=0:return full
    return max(setting*1.1,.001)


class ScaleControls(ttk.Frame):
    def __init__(self,parent,metric,on_change):
        super().__init__(parent)
        self.metric=metric;self.on_change=on_change
        self.mode=tk.StringVar(value='Channel limits')
        self.variables={'V':tk.StringVar(value='30'),'A':tk.StringVar(value='3')}
        self.accepted={'V':30.,'A':3.}
        ttk.Label(self,text='Scale').grid(row=0,column=0,padx=(0,6))
        box=ttk.Combobox(self,textvariable=self.mode,values=SCALE_MODES,state='readonly',width=14)
        box.grid(row=0,column=1);box.bind('<<ComboboxSelected>>',lambda e:self.changed())
        self.maximum=ttk.Label(self,text='Max');self.maximum.grid(row=0,column=2,padx=(8,4))
        self.entry=ttk.Entry(self,width=8);self.entry.grid(row=0,column=3)
        self.unit=ttk.Label(self,text='V');self.unit.grid(row=0,column=4,padx=(4,0))
        self.entry.bind('<Return>',self.commit);self.entry.bind('<FocusOut>',self.commit)
        self.changed(redraw=False)

    def key(self):return 'A' if self.metric.get().startswith('Current') else 'V'
    def changed(self,redraw=True):
        key=self.key();self.entry.configure(textvariable=self.variables[key]);self.unit.configure(text=key)
        for widget in (self.maximum,self.entry,self.unit):
            widget.grid() if self.mode.get()=='Manual' else widget.grid_remove()
        if redraw:self.on_change()
    def manual_max(self):return self.accepted[self.key()]
    def commit(self,event=None):
        key=self.key()
        try:self.accepted[key]=positive_scale(self.variables[key].get())
        except ValueError as exc:
            self.variables[key].set(f'{self.accepted[key]:g}')
            messagebox.showerror('Graph scale',str(exc),parent=self.winfo_toplevel());return 'break'
        self.variables[key].set(f'{self.accepted[key]:g}');self.on_change()
        return 'break'
