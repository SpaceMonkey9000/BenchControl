"""Desktop UI components. No instrument communication in this module."""
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import math
import time
import tkinter as tk
from tkinter import ttk, messagebox
from timebase import TIME_BASES, plot_window
from graph_scale import ScaleControls,graph_top
from model_profiles import DEFAULT_PROFILE


def digit_step(text, caret, direction, maximum):
    """Adjust the digit at the caret, maintaining 1 mV / 1 mA precision."""
    value = Decimal(text.strip())
    if not value.is_finite() or value < 0: raise ValueError('Invalid positive number')
    if 'e' in text.lower() or not text.strip(): raise ValueError('Use decimal notation')
    point = text.find('.')
    point = len(text) if point < 0 else point
    index = min(max(int(caret), 0), len(text)-1)
    if not text[index].isdigit():
        index = index-1 if index > 0 else index+1
    if index < 0 or index >= len(text) or not text[index].isdigit(): raise ValueError('Select a digit')
    exponent = point-index-1 if index < point else point-index
    exponent = max(-3, exponent)
    changed = value + Decimal(direction) * Decimal(10) ** exponent
    changed = min(max(changed, Decimal(0)), Decimal(str(maximum)))
    formatted = format(changed.quantize(Decimal('.001'), rounding=ROUND_HALF_UP), '.3f')
    new_point = formatted.index('.')
    new_index = new_point-exponent-1 if exponent >= 0 else new_point-exponent
    return formatted, min(max(new_index, 0), len(formatted)-1)


def is_dirty(voltage, current, reading):
    if reading is None: return False
    try:
        v, i = float(voltage), float(current)
        return (not math.isfinite(v) or not math.isfinite(i)
                or abs(v-reading.set_voltage) > .0005 or abs(i-reading.set_current) > .0005)
    except (ValueError, TypeError): return True


def channel_state(reading, hold_until, now):
    if not reading.enabled: return 'OUTPUT OFF', False, 0
    if reading.current_limited: return 'OUTPUT ON', True, now+.5
    if now < hold_until: return 'OUTPUT ON', True, hold_until
    return 'OUTPUT ON', False, hold_until


@dataclass
class Stats:
    count: int = 0
    minimum: tuple = (math.inf, math.inf, math.inf)
    maximum: tuple = (-math.inf, -math.inf, -math.inf)
    totals: tuple = (0., 0., 0.)

    def add(self, row):
        values = (row.voltage, row.current, row.voltage*row.current)
        self.minimum = tuple(min(a,b) for a,b in zip(self.minimum,values))
        self.maximum = tuple(max(a,b) for a,b in zip(self.maximum,values))
        self.totals = tuple(a+b for a,b in zip(self.totals,values))
        self.count += 1

    def text(self):
        if not self.count: return 'No samples'
        lines = ['                 VOLTAGE       CURRENT         POWER']
        for name,values in [('Minimum',self.minimum),('Maximum',self.maximum),('Average',tuple(x/self.count for x in self.totals))]:
            lines.append(f'{name:10s} {values[0]:11.3f} V {values[1]:11.3f} A {values[2]:11.4f} W')
        return '\n'.join(lines)


class DigitEntry(ttk.Entry):
    def __init__(self,parent,variable,maximum,commit,changed=None):
        super().__init__(parent,textvariable=variable,width=9,font=('Consolas',16),justify='right')
        self.variable, self.maximum, self.commit = variable, maximum, commit
        self.changed=changed
        self.bind('<KeyRelease>',self.typed)
        self.bind('<Return>',self.enter)
        self.bind('<KP_Enter>',self.enter)
        self.bind('<Up>',lambda e:self.step(1))
        self.bind('<Down>',lambda e:self.step(-1))
        self.bind('<MouseWheel>',self.wheel)
        self.bind('<Button-4>',lambda e:self.step(1) if self.focus_get() is self else None)
        self.bind('<Button-5>',lambda e:self.step(-1) if self.focus_get() is self else None)

    def typed(self,event):
        if self.changed and event.keysym not in ('Return','KP_Enter','Up','Down','Left','Right','Home','End','Tab','Shift_L','Shift_R','Control_L','Control_R','Alt_L','Alt_R','Escape'):
            self.changed(None)

    def enter(self,event=None):
        if 'disabled' not in self.state(): self.commit()
        return 'break'

    def step(self,direction):
        if 'disabled' in self.state(): return 'break'
        try:
            caret = self.index('sel.first') if self.selection_present() else self.index('insert')
            formatted,index = digit_step(self.variable.get(),caret,direction,self.maximum)
            self.variable.set(formatted)
            self.icursor(index);self.selection_range(index,index+1)
            if getattr(self,'changed',None):self.changed(None)
        except (ValueError, InvalidOperation, tk.TclError): self.bell()
        return 'break'

    def wheel(self,event):
        if self.focus_get() is not self: return None
        if event.delta: return self.step(1 if event.delta>0 else -1)
        return 'break'


class ChannelPanel(tk.Frame):
    def __init__(self,parent,number,app,shared=None,expanded=False):
        super().__init__(parent,bg='#132439',highlightthickness=2,highlightbackground='#324961')
        self.number,self.app=number,app
        self.initialize_drafts=shared is None
        self.reading=None;self.alert_until=0;self.palette=None;self.last_controls=None
        self.v=shared.v if shared else tk.StringVar(value='0.000')
        self.i=shared.i if shared else tk.StringVar(value='0.000')
        self._traces=[]
        self._palette_widgets=[self]
        header=tk.Frame(self,bg='#132439');header.pack(fill='x',padx=14,pady=(12,4));self._palette_widgets.append(header)
        self.heading=self.label(header,f'CH {number}',font=('Segoe UI',15,'bold'))
        self.heading.pack(side='left')
        expand=self.label(header,'DETAILS' if not expanded else 'CHANNEL',font=('Segoe UI',9,'bold'),cursor='hand2')
        expand.pack(side='right')
        if not expanded:
            for widget in (header,self.heading,expand):widget.bind('<Button-1>',lambda e:app.open_detail(number))
        self.state=self.label(self,'DISCONNECTED',font=('Segoe UI',9,'bold'),height=2,anchor='w',padx=8)
        self.state.pack(fill='x',padx=14,pady=(0,6))
        self.vmeter=self.measurement('VOLTAGE','V')
        self.ve=self.setpoint('SET',self.v,5 if number==3 else 30,'V')
        self.imeter=self.measurement('CURRENT','A')
        self.ie=self.setpoint('LIMIT',self.i,3,'A')
        self.configure_profile(getattr(app,'device_profile',DEFAULT_PROFILE))
        self.vmeter.bind('<Button-1>',lambda e:self.ve.focus_set())
        self.imeter.bind('<Button-1>',lambda e:self.ie.focus_set())
        self.vmeter.configure(cursor='xterm');self.imeter.configure(cursor='xterm')
        self.power=self.label(self,'POWER  — W',font=('Consolas',15),anchor='w')
        self.power.pack(fill='x',padx=14,pady=(12,4))
        self.applied=self.label(self,'PSU settings: —',font=('Segoe UI',9),anchor='w')
        self.applied.pack(fill='x',padx=14,pady=(0,2))
        self.dirty=self.label(self,'',font=('Segoe UI',9,'bold'),anchor='w')
        self.dirty.pack(fill='x',padx=14)
        # Bottom controls remain in the same position across all three tiles.
        footer=tk.Frame(self,bg='#132439');footer.pack(side='bottom',fill='x',padx=14,pady=12,before=header);self._palette_widgets.append(footer)
        self.apply=ttk.Button(footer,text='Apply settings',command=self.apply_settings);self.apply.pack(fill='x',pady=(0,6))
        self.output_toggle=ttk.Button(footer,text='Output ON',command=self.toggle_output);self.output_toggle.pack(fill='x')
        for var in (self.v,self.i):self._traces.append((var,var.trace_add('write',lambda *_:self.update_dirty())))
        self.bind('<Destroy>',self.cleanup)
        self.controls(False);self.set_palette(False)

    def configure_profile(self,profile):
        self.ve.maximum,self.ie.maximum=profile.limits(self.number)

    def label(self,parent,text,**kwargs):
        label=tk.Label(parent,text=text,bg='#132439',fg='#e5eef8',**kwargs)
        self._palette_widgets.append(label)
        return label

    def measurement(self,caption,unit):
        row=tk.Frame(self,bg='#132439');row.pack(fill='x',padx=14,pady=(8,0));self._palette_widgets.append(row)
        self.label(row,caption,font=('Segoe UI',8,'bold')).pack(anchor='w')
        meter=self.label(row,'— '+unit,font=('Consolas',28),anchor='e');meter.pack(fill='x')
        return meter

    def setpoint(self,caption,var,maximum,unit):
        row=tk.Frame(self,bg='#132439');row.pack(fill='x',padx=14);self._palette_widgets.append(row)
        self.label(row,caption,font=('Segoe UI',9,'bold')).pack(side='left')
        self.label(row,unit,font=('Segoe UI',11)).pack(side='right',padx=(6,0))
        field='voltage' if unit=='V' else 'current'
        entry=DigitEntry(row,var,maximum,lambda:self.commit_field(field),
            changed=lambda delay:self.app.queue_live(self.number,field,delay));entry.pack(side='right')
        return entry

    def cleanup(self,event):
        if event.widget is not self:return
        for var,token in self._traces:
            try:var.trace_remove('write',token)
            except tk.TclError:pass
        self._traces=[]

    def values(self):
        from instrument import validate
        v,i=float(self.v.get()),float(self.i.get());validate(self.number,v,i,getattr(self.app,'device_profile',DEFAULT_PROFILE))
        return v,i

    def update_dirty(self):
        pending=is_dirty(self.v.get(),self.i.get(),self.reading)
        instant=getattr(getattr(self.app,'user_settings',None),'instant_mode',False)
        self.dirty.configure(text='LIVE EDITS' if instant and self.reading else 'UNAPPLIED CHANGES' if pending else 'SETTINGS MATCH PSU' if self.reading else '',fg='#ffd278' if pending and not instant else self.palette[1] if self.palette else '#9aacc1')

    def commit_field(self,field):
        if getattr(self.app.user_settings,'instant_mode',False):
            self.app.queue_live(self.number,field,0)
        else:self.apply_settings()

    def apply_settings(self):
        if not self.app.connected or self.app.busy:return
        if not self.reading or self.reading.enabled:
            messagebox.showerror('Channel on','Switch the channel off before changing settings.');return
        try:v,i=self.values()
        except ValueError as e:messagebox.showerror('Invalid settings',str(e));return
        v,i=float(f'{v:.3f}'),float(f'{i:.3f}')
        preferences=getattr(self.app,'user_settings',None)
        if getattr(preferences,'confirm_setpoints',False) and not messagebox.askyesno('Apply settings',f'Set CH{self.number} to {v:.3f} V with a {i:.3f} A current limit?'):
            return
        self.v.set(f'{v:.3f}');self.i.set(f'{i:.3f}')
        self.app.command('apply',self.number,v,i)

    def enable(self):
        if not self.reading or not self.app.connected or self.app.busy:return
        try:v,i=self.values()
        except ValueError as e:messagebox.showerror('Invalid settings',str(e));return
        if is_dirty(self.v.get(),self.i.get(),self.reading):
            instant=getattr(getattr(self.app,'user_settings',None),'instant_mode',False)
            messagebox.showerror('Unconfirmed settings','Wait for live edits to be confirmed, or correct the field.' if instant else 'Apply the edited settings before enabling this output.');return
        preferences=getattr(self.app,'user_settings',None)
        if not getattr(preferences,'confirm_output',True) or messagebox.askyesno('Enable output',f'Enable CH{self.number} at {v:.3f} V with a {i:.3f} A current limit?'):
            self.app.command('output',self.number,True,(v,i))

    def toggle_output(self):
        if not self.app.connected or not self.reading:return
        if self.reading.enabled:
            self.app.command('output',self.number,False)
        else:
            self.enable()

    def controls(self,connected,busy=False):
        instant=getattr(getattr(self.app,'user_settings',None),'instant_mode',False)
        is_on=bool(self.reading and self.reading.enabled);key=(connected,busy,self.reading is not None,is_on,instant)
        if key==self.last_controls:return
        self.last_controls=key;enabled=connected and not busy
        for control in (self.ve,self.ie):control.configure(state='normal' if enabled and (instant or not is_on) else 'disabled')
        self.apply.configure(state='normal' if enabled and not is_on and not instant else 'disabled')
        if instant:self.apply.pack_forget()
        elif not self.apply.winfo_manager():self.apply.pack(fill='x',pady=(0,6),before=self.output_toggle)

        self.output_toggle.configure(text='Output OFF' if is_on else 'Output ON',
            state='normal' if connected and self.reading and (is_on or not busy) else 'disabled',style='TButton')

    def set_palette(self,alert=False):
        active=bool(self.reading and self.reading.enabled)
        colors=('#a51d32','#ffffff') if alert else ('#132439','#eef6ff' if active else '#a8b7c9')
        if colors==self.palette:return
        self.palette=colors;bg,fg=colors
        for widget in self._palette_widgets:
            widget.configure(bg=bg)
            if isinstance(widget,tk.Label):widget.configure(fg=fg)
        self.configure(highlightbackground='#ff6b7d' if alert else '#43cbb7' if active else '#324961')

    def update_reading(self,r,first=False):
        first=first or (self.reading is None and getattr(self,'initialize_drafts',True))
        self.reading=r
        text,alert,self.alert_until=channel_state(r,self.alert_until,time.monotonic())
        self.set_palette(alert)
        self.state.configure(text=text,bg='#16804a' if r.enabled else '#233449',fg='#ffffff' if r.enabled else '#a8b7c9')
        self.vmeter.configure(text=f'{r.voltage:.3f} V');self.imeter.configure(text=f'{r.current:.3f} A')
        self.power.configure(text=f'POWER  {r.voltage*r.current:.4f} W')
        self.applied.configure(text=f'PSU  {r.set_voltage:.3f} V / {r.set_current:.3f} A')
        if first:self.v.set(f'{r.set_voltage:.3f}');self.i.set(f'{r.set_current:.3f}')
        self.update_dirty()
        if alert and not r.current_limited:
            remaining=max(1,math.ceil((self.alert_until-time.monotonic())*1000))
            self.after(remaining,lambda:self.clear_alert(r))

    def clear_alert(self,reading):
        # A new sample or disconnect invalidates this scheduled repaint.
        if self.reading is not reading or reading.current_limited:return
        if time.monotonic()<self.alert_until:return
        self.set_palette(False)
        self.state.configure(text='OUTPUT ON' if reading.enabled else 'OUTPUT OFF',
            bg='#16804a' if reading.enabled else '#233449',fg='#ffffff' if reading.enabled else '#a8b7c9')

    def stale(self):
        self.reading=None;self.alert_until=0;self.set_palette(False)
        self.state.configure(text='DISCONNECTED · STALE',bg='#233449',fg='#a8b7c9')
        self.vmeter.configure(text='— V');self.imeter.configure(text='— A');self.power.configure(text='POWER  — W')
        self.applied.configure(text='PSU settings: —');self.update_dirty()


PLOT_MIN_SECONDS = .2   # matches PLOT_INTERVAL_MS
PLOT_MAX_SECONDS = 2.   # long windows still refresh at least every 2 s
NEGATIVE_TOLERANCE = .01  # readback noise near zero is not "clipped"


def _ordered(lo,hi):
    if lo is hi:return (lo,)
    return (lo,hi) if lo[0]<=hi[0] else (hi,lo)


def draw_history(canvas,history,ch,metric,seconds=None,scale_mode='Full range',manual_max=None):
    """Draw one channel's trace. Returns the suggested seconds until the next
    data-driven redraw: about one display pixel of time, within 0.2–2 s."""
    canvas.delete('all');w=max(canvas.winfo_width(),260);h=max(canvas.winfo_height(),100)
    start,end,samples=plot_window(history,seconds);current=metric.startswith('Current');unit='A' if current else 'V'
    if not samples:
        canvas.create_text(w/2,h/2,text='No samples',fill='#9baec4');return PLOT_MIN_SECONDS
    span=max(end-start,.001)
    top=graph_top(ch,metric,samples[-1][1][ch],scale_mode,manual_max)
    left,right,upper,lower=42,w-12,32,h-22
    width=max(right-left,1);height=lower-upper
    # One pass extracts (time, value); every later step works on plain floats.
    if current:points=[(t,rows[ch].current) for t,rows in samples]
    else:points=[(t,rows[ch].voltage) for t,rows in samples]
    floor=-NEGATIVE_TOLERANCE*top
    clipped=any(v>top or v<floor for _,v in points)
    canvas.create_text(10,10,text=f'CH{ch+1} · {metric} · {span:g} s · 0–{top:.4g} {unit}'+(' · clipped' if clipped else ''),anchor='nw',fill='#c5d6e8')
    for f in (0,.5,1):
        y=lower-height*f
        canvas.create_line(left,y,right,y,fill='#294057')
        canvas.create_text(left-5,y,text=f'{top*f:g}',anchor='e',fill='#8da6c0',font=('Consolas',9))
    for fraction in (0,.5,1):
        x=left+width*fraction
        remaining=span*(1-fraction)
        label=f'-{remaining:g} s' if remaining else '0 s'
        canvas.create_text(x,h-6,text=label,fill='#8da6c0',font=('Consolas',9))
    xscale=width/span
    # At most one min/max pair per display pixel, preserving narrow extrema.
    # Plot only actual samples, never fill in missing data.
    if len(points)>2*int(width):
        reduced=[];pixel=None
        for t,v in points:
            p=int((t-start)*xscale)
            if p!=pixel:
                if pixel is not None:reduced.extend(_ordered(lo,hi))
                pixel=p;lo=hi=(t,v)
            elif v<lo[1]:lo=(t,v)
            elif v>hi[1]:hi=(t,v)
        reduced.extend(_ordered(lo,hi))
        points=reduced
    yscale=height/top;coords=[]
    for t,v in points:
        y=lower-v*yscale
        coords.append(left+(t-start)*xscale);coords.append(upper if y<upper else lower if y>lower else y)
    if len(coords)>=4:canvas.create_line(*coords,fill='#4dd8c2',width=2)
    return min(PLOT_MAX_SECONDS,max(PLOT_MIN_SECONDS,span/width))


class ChannelDetail(tk.Toplevel):
    def __init__(self,app,number):
        super().__init__(app);self.app=app;self.number=number
        self.title(f'BenchControl · Channel {number}');self.geometry('1040x720');self.minsize(930,660)
        self.configure(bg='#0b1726')
        self.protocol('WM_DELETE_WINDOW',self.close)
        self.columnconfigure(1,weight=1);self.rowconfigure(1,weight=1)
        top=ttk.Frame(self,padding=12);top.grid(row=0,column=0,columnspan=2,sticky='ew')
        ttk.Label(top,text=f'CHANNEL {number} · DETAIL',font=('Segoe UI',17,'bold')).pack(side='left')
        self.panel=ChannelPanel(self,number,app,shared=app.panels[number-1],expanded=True)
        self.panel.grid(row=1,column=0,rowspan=3,sticky='nsew',padx=(12,6),pady=(0,12))
        right=tk.Frame(self,bg='#0b1726');right.grid(row=1,column=1,sticky='nsew',padx=12)
        right.rowconfigure(0,weight=1);right.columnconfigure(0,weight=1)
        self.metric=tk.StringVar(value='Current (A)')
        select=ttk.Combobox(right,textvariable=self.metric,values=['Voltage (V)','Current (A)'],state='readonly',width=14)
        select.grid(row=1,column=0,sticky='w',pady=8);select.bind('<<ComboboxSelected>>',lambda e:self.graph_scale.changed())
        self.time_base=tk.StringVar(value=app.time_base.get())
        time_select=ttk.Combobox(right,textvariable=self.time_base,values=list(TIME_BASES),state='readonly',width=13)
        time_select.grid(row=1,column=0,sticky='e',pady=8);time_select.bind('<<ComboboxSelected>>',lambda e:self.graph_scale.changed())
        self.graph_scale=ScaleControls(right,self.metric,self.redraw)
        self.graph_scale.grid(row=2,column=0,sticky='w',pady=(0,6))
        self.canvas=tk.Canvas(right,height=230,bg='#101f31',highlightthickness=0);self.canvas.grid(row=0,column=0,sticky='nsew')
        self.canvas.bind('<Configure>',lambda e:app.request_plot(number))
        self.statistics=tk.Label(self,bg='#0b1726',fg='#d6e3f2',font=('Consolas',10),anchor='w',justify='left')
        self.statistics.grid(row=2,column=1,sticky='ew',padx=12,pady=12)
        lower=ttk.Frame(self,padding=8);lower.grid(row=3,column=1,sticky='ew',padx=12,pady=(0,12))
        ttk.Button(lower,text='Reset statistics',command=self.reset_stats).pack(side='left')
        self.logbutton=ttk.Button(lower,text='Start CSV log…',command=app.toggle_log);self.logbutton.pack(side='left',padx=6)
        ttk.Label(self,text='Statistics include off-state samples. CSV logs cover all three channels.',padding=8).grid(row=4,column=0,columnspan=2,sticky='ew')
        r=app.panels[number-1].reading
        if r:self.panel.update_reading(r)
        else:self.panel.stale()
        self.sync();self.redraw()

    def reset_stats(self):self.app.stats[self.number-1]=Stats();self.redraw()
    def sync(self):
        self.panel.controls(self.app.connected,self.app.busy)
        self.logbutton.configure(text='Stop CSV log' if self.app.logfile else 'Start CSV log…')
    def redraw(self):
        interval=draw_history(self.canvas,self.app.history,self.number-1,self.metric.get(),TIME_BASES[self.time_base.get()],self.graph_scale.mode.get(),self.graph_scale.manual_max())
        self.update_stats()
        return interval
    def update_stats(self):
        stats=self.app.stats[self.number-1]
        self.statistics.configure(text=f'SINCE CONNECT / RESET · {stats.count} samples\n\n'+stats.text())
    def close(self):self.app.details.pop(self.number,None);self.destroy()
