"""Nonmodal settings window. Settings never activate PSU outputs."""
import tkinter as tk
from tkinter import ttk,messagebox
from dataclasses import asdict
from preferences import Preferences
from model_profiles import PROFILES, DEFAULT_PROFILE
from acquisition import POLL_RATES
from timebase import TIME_BASES,LOG_INTERVALS


class SettingsWindow(tk.Toplevel):
    def __init__(self,app):
        super().__init__(app);self.app=app;self.last_lock=None
        self.title('BenchControl · Settings');self.geometry('720x720');self.minsize(680,700)
        self.transient(app);self.protocol('WM_DELETE_WINDOW',self.close)
        self.vars={}
        current=asdict(app.user_settings)
        current.update(resource=app.resource.get(),demo=app.demo.get(),graph_timebase=app.time_base.get(),log_interval=app.log_interval.get())
        # Values shown when the window opened. If unchanged here at save time,
        # the main screen's current selection wins instead of being reverted.
        self.opened={key:current[key] for key in ('graph_timebase','log_interval')}
        for name,value in current.items():
            self.vars[name]=tk.BooleanVar(value=value) if type(value) is bool else tk.StringVar(value=str(value))
        tabs=ttk.Notebook(self);tabs.pack(fill='both',expand=True,padx=14,pady=14)
        general=ttk.Frame(tabs,padding=18);connection=ttk.Frame(tabs,padding=18);info=ttk.Frame(tabs,padding=18)
        tabs.add(general,text='General');tabs.add(connection,text='Connection');tabs.add(info,text='Device')
        self.combo(general,'Acquisition target','poll_rate',[str(x) for x in POLL_RATES],0,'Hz')
        self.combo(general,'Default graph time base','graph_timebase',list(TIME_BASES),1)
        self.combo(general,'CSV logging interval','log_interval',list(LOG_INTERVALS),2)
        ttk.Separator(general).grid(row=3,column=0,columnspan=3,sticky='ew',pady=18)
        ttk.Checkbutton(general,text='Confirm voltage/current before enabling an output',variable=self.vars['confirm_output']).grid(row=4,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Checkbutton(general,text='Confirm before applying voltage/current changes',variable=self.vars['confirm_setpoints']).grid(row=5,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Checkbutton(general,text='Instant mode — live voltage/current edits, no Apply button',variable=self.vars['instant_mode']).grid(row=6,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Label(general,text='Instant edit delay (ms)').grid(row=7,column=0,sticky='w',pady=8)
        ttk.Spinbox(general,from_=100,to=3000,increment=50,textvariable=self.vars['instant_delay_ms'],width=12).grid(row=7,column=1,sticky='w')
        ttk.Label(general,text='Applies after typing, arrows or wheel stop. Enter sends immediately.\nInstant mode changes setpoints while outputs are ON or OFF.\nOutput-ON confirmation retains its separate setting.',wraplength=620).grid(row=8,column=0,columnspan=3,sticky='w',pady=10)
        ttk.Checkbutton(general,text='Minimal UI — hide graph section',variable=self.vars['minimal_ui']).grid(row=9,column=0,columnspan=3,sticky='w',pady=8)
        ttk.Label(general,text='General settings apply when saved. Opening Settings sends no PSU commands.',wraplength=600).grid(row=10,column=0,columnspan=3,sticky='w',pady=8)
        general.columnconfigure(1,weight=1)
        ttk.Label(connection,text='VISA resource / alias').grid(row=0,column=0,sticky='w',pady=8)
        self.resource_box=ttk.Combobox(connection,textvariable=self.vars['resource'],values=app.available_resources,width=54)
        self.resource_box.grid(row=1,column=0,columnspan=2,sticky='ew',pady=(0,8))
        self.scan_button=ttk.Button(connection,text='Refresh device list',command=lambda:app.worker.post('scan'))
        self.scan_button.grid(row=2,column=0,sticky='w',pady=5)
        self.demo_button=ttk.Checkbutton(connection,text='Demo device (simulated readings)',variable=self.vars['demo'])
        self.demo_button.grid(row=3,column=0,sticky='w',pady=12)
        self.demo_model=ttk.Combobox(connection,textvariable=self.vars['demo_model'],values=list(PROFILES),state='readonly',width=12)
        self.demo_model.grid(row=3,column=1,sticky='w',pady=12)
        ttk.Label(connection,text='VISA I/O timeout (ms)').grid(row=4,column=0,sticky='w',pady=8)
        self.timeout=ttk.Spinbox(connection,from_=500,to=10000,increment=500,textvariable=self.vars['io_timeout_ms'],width=12)
        self.timeout.grid(row=4,column=1,sticky='w')
        ttk.Label(connection,text='USB query delay (ms)').grid(row=5,column=0,sticky='w',pady=8)
        self.delay=ttk.Spinbox(connection,from_=0,to=100,increment=1,textvariable=self.vars['usb_query_delay_ms'],width=12)
        self.delay.grid(row=5,column=1,sticky='w')
        ttk.Label(connection,text='Disconnect before changing connection fields. Saved connection settings\ntake effect on the next explicit Connect. Non-USB pacing remains 25 ms.\nLonger timeouts can delay an OFF request behind a stalled transaction.\nNo automatic connection, setpoint restore or output activation.',wraplength=600).grid(row=6,column=0,columnspan=2,sticky='w',pady=16)
        connection.columnconfigure(0,weight=1)
        self.info=ttk.Label(info,text='',wraplength=600,justify='left');self.info.pack(anchor='w',pady=12)
        self.capabilities=ttk.Label(info,text='',justify='left');self.capabilities.pack(anchor='w',pady=18)
        ttk.Label(info,text='Hardware model is detected from *IDN?, with no manual override.\nEnabled profiles: 9130B, 9131B, 9132B.\n9131B/9132B: documented command support; hardware untested here.\nC-series draft configs are disabled pending command verification.\nThe model selector under Connection is for Demo mode only.',justify='left').pack(anchor='w',pady=18)
        footer=ttk.Frame(self,padding=(14,0,14,14));footer.pack(fill='x')
        ttk.Button(footer,text='General defaults',command=self.defaults).pack(side='left')
        ttk.Button(footer,text='Cancel',command=self.close).pack(side='right',padx=5)
        ttk.Button(footer,text='Save settings',command=self.save).pack(side='right',padx=5)
        self.sync_lock()

    def combo(self,parent,label,key,values,row,unit=''):
        ttk.Label(parent,text=label).grid(row=row,column=0,sticky='w',pady=8,padx=(0,16))
        ttk.Combobox(parent,textvariable=self.vars[key],values=values,state='readonly',width=19).grid(row=row,column=1,sticky='w')
        if unit:ttk.Label(parent,text=unit).grid(row=row,column=2,sticky='w',padx=6)

    def sync_lock(self):
        locked=self.app.connected or self.app.connecting
        if locked!=self.last_lock:
            self.last_lock=locked
            for widget in (self.resource_box,self.scan_button,self.demo_button,self.timeout,self.delay):
                widget.configure(state='disabled' if locked else 'normal')
        self.demo_model.configure(state='disabled' if locked else 'readonly')
        self.capabilities.configure(text=getattr(self.app,'device_profile',DEFAULT_PROFILE).description())
        self.info.configure(text=self.app.identity.cget('text'))

    def set_resources(self,resources):self.resource_box.configure(values=resources)
    def defaults(self):
        defaults=asdict(Preferences())
        for key in ('poll_rate','confirm_output','confirm_setpoints','instant_mode','instant_delay_ms','minimal_ui','graph_timebase','log_interval'):self.vars[key].set(defaults[key])
    def save(self):
        try:
            data={name:var.get() for name,var in self.vars.items()}
            data['resource']=data['resource'].strip()
            data['instant_delay_ms']=int(data['instant_delay_ms']);data['poll_rate']=int(data['poll_rate']);data['io_timeout_ms']=int(data['io_timeout_ms'])
            data['usb_query_delay_ms']=float(data['usb_query_delay_ms'])
            for key,live in (('graph_timebase',self.app.time_base),('log_interval',self.app.log_interval)):
                if data[key]==self.opened[key]:data[key]=live.get()
            preferences=Preferences(**data).validate()
            self.app.apply_preferences(preferences)
        except (ValueError,OSError,tk.TclError) as exc:
            messagebox.showerror('Settings not saved',str(exc),parent=self);return
        self.close()
    def close(self):self.app.settings_window=None;self.destroy()
