"""BenchControl 9130B 1.9.1 — Windows desktop SCPI interface."""
import csv
from contextlib import closing
import itertools
import json
import queue
import threading
import time
import tkinter as tk
from collections import deque
from datetime import datetime
from pathlib import Path
from tkinter import ttk, messagebox, filedialog
from instrument import PSU, DemoDevice, PollInterrupted, Refused, validate
from preferences import Preferences, load_preferences, save_preferences, preferences_path
from settings_ui import SettingsWindow
from live_edits import LiveEdits
from model_profiles import DEFAULT_PROFILE, profile_from_identity
from graph_scale import ScaleControls
from disconnect_ui import ask_disconnect
from channel_split import ChannelGraphSplit
from ui_controls import ChannelPanel, ChannelDetail, Stats, draw_history
from timebase import TIME_BASES, LOG_INTERVALS, LogGate, MAX_SAMPLES, trim_history
from acquisition import POLL_RATES, DEFAULT_POLL_RATE, PLOT_INTERVAL_MS, ScanSample, query_delay_for

EVENT_LOG_LINES = 5000
CSV_FLUSH_SECONDS = 1.0


class Worker(threading.Thread):
    def __init__(self, events):
        super().__init__(daemon=True)
        self.events = events
        self.jobs = queue.PriorityQueue()
        self.serial = itertools.count()
        self.psu = None
        self.rm = None
        self.generation = 0
        self.lock = threading.Lock()
        self.instant_mode=False
        self.live_latest={}
        self.next_poll = 0
        self.poll_interval = 1 / DEFAULT_POLL_RATE
        self.start()

    @staticmethod
    def urgent(name, args):
        """OFF, all-off and disconnect jump the queue."""
        return name in ('all_off', 'disconnect') or (name == 'output' and not args[1])

    @staticmethod
    def cancellable(name, args):
        """Only requests that could turn an output ON or reprogram it are cancelled.

        An OFF must never cancel another OFF (or an all-off/disconnect), and
        housekeeping jobs such as a rate change or device scan are unaffected.
        """
        return name in ('apply','set_live') or (name == 'output' and bool(args[1]))

    def post(self, name, *args):
        with self.lock:
            urgent = self.urgent(name, args)
            if urgent:
                self.generation += 1  # invalidate pending apply/output-ON jobs
            serial=next(self.serial)
            if name=='set_live':self.live_latest[args[:2]]=serial
            if urgent or name=='instant_mode':self.live_latest.clear()
            self.jobs.put((0 if urgent else 10, serial, self.generation, name, args))

    def emit(self, name, data):
        if name == 'snapshot': data = ScanSample(data)
        self.events.put((name, data))

    def release(self):
        self.live_latest.clear()
        try:
            if self.psu: self.psu.close()
        finally:
            self.psu = None
            if self.rm: self.rm.close()
            self.rm = None

    def run(self):
        while True:
            try:
                _, job_serial, generation, name, args = self.jobs.get(timeout=max(.001, min(.05, self.next_poll - time.monotonic())) if self.psu else .05)
            except queue.Empty:
                if self.psu and time.monotonic() >= self.next_poll:
                    generation, name, args = self.generation, 'poll', ()
                else: continue
            if generation != self.generation and self.cancellable(name, args):
                self.emit('live_cancelled' if name=='set_live' else 'cancelled', name)
                continue
            if name=='set_live' and self.live_latest.get(args[:2])!=job_serial:
                self.emit('live_cancelled',name);continue
            try:
                if name == 'scan':
                    import pyvisa
                    with closing(pyvisa.ResourceManager()) as rm:
                        # Listing does not open or query other instruments.
                        resources = list(rm.list_resources())  # retain VISA aliases too
                    self.emit('resources', resources)
                elif name == 'connect':
                    resource, demo = args[:2]
                    options = args[2] if len(args)>2 else {}
                    connection = Preferences(resource=resource,demo=demo,**options).validate()
                    if self.psu: raise RuntimeError('Already connected')
                    if demo:
                        dev = DemoDevice(connection.demo_model)
                    else:
                        import pyvisa
                        self.rm = pyvisa.ResourceManager()
                        dev = self.rm.open_resource(resource, open_timeout=max(2000,connection.io_timeout_ms))
                        dev.timeout = connection.io_timeout_ms
                        dev.write_termination = '\n'
                        dev.read_termination = '\n'
                        dev.query_delay = connection.usb_query_delay_ms/1000 if dev.resource_name.upper().startswith('USB') else query_delay_for(dev.resource_name)
                    try: self.psu = PSU(dev)
                    except Exception:
                        dev.close()
                        raise
                    # No reset, mode change, setpoint change or output enable on connection.
                    self.psu.independent()
                    readings = self.psu.snapshot()
                    self.emit('connected', self.psu.identity)
                    self.emit('snapshot', readings)
                    self.next_poll = time.monotonic() + self.poll_interval
                elif name == 'disconnect':
                    switch_off=bool(args[0]) if args else False
                    if switch_off:
                        if not self.psu:raise RuntimeError('No active connection; outputs OFF cannot be verified')
                        self.psu.all_off()
                    self.release()
                    self.emit('disconnected','All outputs OFF confirmed. Disconnected.' if switch_off else 'Disconnected. Outputs retain their last hardware state.')
                elif name == 'instant_mode':
                    if type(args[0]) is not bool:raise Refused('Instant mode must be boolean')
                    self.instant_mode=args[0]
                elif name == 'rate':
                    rate = float(args[0])
                    if rate not in POLL_RATES: raise ValueError('Unsupported refresh rate')
                    self.poll_interval = 1 / rate
                    self.next_poll = 0
                elif name == 'demo_cc':
                    if not self.psu or not isinstance(self.psu.device, DemoDevice):
                        raise RuntimeError('CC simulation is available only in Demo mode')
                    ch, state = args
                    if state: self.psu.device.limited_channels.add(ch)
                    else: self.psu.device.limited_channels.discard(ch)
                    self.next_poll = 0
                elif name in ('apply','set_live','output','all_off','poll'):
                    if not self.psu: raise RuntimeError('Not connected')
                    if name=='set_live' and not self.instant_mode:raise Refused('Instant mode is disabled')
                    if name != 'poll':
                        if name=='set_live':
                            self.psu.set_live(*args,interrupt=lambda:generation!=self.generation or self.live_latest.get(args[:2])!=job_serial)
                        else:getattr(self.psu, name)(*args)
                        self.emit('live_done' if name=='set_live' else 'done',args if name=='set_live' else name)
                    # A queued all-off interrupts between transactions, not during VISA I/O.
                    if generation == self.generation:
                        started = time.monotonic()
                        rows = self.psu.snapshot(interrupt=lambda: not self.jobs.empty() or generation != self.generation,
                                                 force=name != 'poll')
                        self.emit('snapshot', rows)
                        # Start-to-start schedule, no extra one-second sleep after acquisition.
                        self.next_poll = max(started + self.poll_interval, time.monotonic())
            except PollInterrupted:
                self.next_poll = 0
            except Exception as exc:
                # A declined request that sent no output/setpoint command, or a
                # bad housekeeping request, leaves the healthy session connected.
                if (isinstance(exc, Refused) and name in ('apply', 'output', 'set_live')) or name in ('rate', 'demo_cc'):
                    if name=='set_live':self.live_latest.clear()
                    self.emit('live_refused' if name=='set_live' else 'refused', (name, str(exc)))
                    continue
                # Never reconnect or retry an output enable automatically.
                if name != 'scan':
                    with self.lock: self.generation += 1
                    try: self.release()
                    except Exception: pass
                if name=='disconnect' and args and args[0]:
                    exc=RuntimeError('Shutdown not confirmed; connection closed. '+str(exc))
                self.emit('error', (name, str(exc)))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title('BenchControl · B&K 9130B · 1.9.1')
        self.geometry('1180x840');self.minsize(1080,800)
        style=ttk.Style(self)
        style.theme_use('clam')
        style.configure('TButton',padding=7)
        self.configure(bg='#0b1726')
        self.device_profile=DEFAULT_PROFILE
        self.details={}
        self.close_after_disconnect=False
        self.settings_window=None
        self.available_resources=[]
        self.stats=[Stats(),Stats(),Stats()]
        self.events=queue.Queue(); self.worker=Worker(self.events)
        self.connected=False;self.busy=False;self.first=False;self.connecting=False
        self.logfile=None;self.writer=None;self.history=deque(maxlen=MAX_SAMPLES)
        self.time_base=tk.StringVar(value='1 min')
        self.log_interval=tk.StringVar(value='Every sample')
        self.log_gate=LogGate()
        self.plots_dirty = False
        self.stale_plots = set();self.plot_due = {}
        self.pending_jobs = 0
        self.log_started_at = 0.0
        self.last_flush = 0.0
        self.event_lines = deque(maxlen=EVENT_LOG_LINES);self.log_window = None
        self.preferences = preferences_path()
        self.plot_channel=tk.StringVar(value='CH1');self.plot_metric=tk.StringVar(value='Voltage (V)')
        self.resource=tk.StringVar();self.demo=tk.BooleanVar(value=False)
        self.live_edits=LiveEdits(self,self.submit_live)
        self.user_settings=load_preferences(self.preferences)
        self.worker.post('instant_mode',self.user_settings.instant_mode)
        self.resource.set(self.user_settings.resource);self.demo.set(self.user_settings.demo)
        self.time_base.set(self.user_settings.graph_timebase);self.log_interval.set(self.user_settings.log_interval)
        self.log_gate.reset(LOG_INTERVALS[self.log_interval.get()])
        self.worker.post('rate',self.user_settings.poll_rate)
        menu=tk.Menu(self)
        settings_menu=tk.Menu(menu,tearoff=False);settings_menu.add_command(label='Preferences…',command=self.open_settings,accelerator='Ctrl+,')
        menu.add_cascade(label='Settings',menu=settings_menu);self.configure(menu=menu)
        self.bind('<Control-comma>',lambda e:self.open_settings())
        top=ttk.Frame(self,padding=8);top.pack(fill='x')
        self.model_label=ttk.Label(top,text='POWER SUPPLY',font=('Segoe UI',19,'bold'));self.model_label.pack(side='left')
        conn=top
        self.connect_button=ttk.Button(conn,text='Connect',command=self.connect_toggle);self.connect_button.pack(side='right')
        ttk.Button(conn,text='Settings…',command=self.open_settings).pack(side='right',padx=6)
        self.main_split=ChannelGraphSplit(self)
        self.main_split.pack(fill='both',expand=True)
        area=tk.Frame(self.main_split,bg='#0b1726',padx=12,pady=8)
        graph_area=tk.Frame(self.main_split,bg='#0b1726')
        self.channel_area=area;self.graph_area=graph_area
        self.graph_visible=True;self.saved_sash_y=None
        self.main_split.add(area,minsize=360,stretch='always')
        self.main_split.add(graph_area,minsize=200,stretch='always')
        graph_controls=ttk.Frame(graph_area)
        graph_controls.pack(side='bottom',fill='x')
        self.panels=[]
        for j in range(3):
            p=ChannelPanel(area,j+1,self);p.grid(row=0,column=j,sticky='nsew',padx=4)
            area.columnconfigure(j,weight=1,uniform='channels');self.panels.append(p)
        area.rowconfigure(0,weight=1)
        tools=ttk.Frame(self,padding=(16,4));tools.pack(fill='x')
        ttk.Button(tools,text='Save preset…',command=self.save_settings).pack(side='left')
        ttk.Button(tools,text='Load preset…',command=self.load_settings).pack(side='left',padx=5)
        self.log_button=ttk.Button(tools,text='Start CSV log…',command=self.toggle_log);self.log_button.pack(side='left',padx=5)
        ttk.Label(tools,text='Every').pack(side='left',padx=(8,2))
        log_select=ttk.Combobox(tools,textvariable=self.log_interval,values=list(LOG_INTERVALS),state='readonly',width=12)
        log_select.pack(side='left',padx=4);log_select.bind('<<ComboboxSelected>>',lambda e:self.change_log_interval())
        ttk.Button(tools,text='Event log…',command=self.show_log).pack(side='left',padx=5)
        timing=ttk.Frame(graph_controls,padding=(16,4));timing.pack(fill='x')
        ttk.Combobox(timing,textvariable=self.plot_channel,values=['CH1','CH2','CH3'],state='readonly',width=5).pack(side='left')
        ttk.Combobox(timing,textvariable=self.plot_metric,values=['Voltage (V)','Current (A)'],state='readonly',width=13).pack(side='left',padx=6)
        ttk.Label(timing,text='Time base').pack(side='left',padx=(12,0))
        time_select=ttk.Combobox(timing,textvariable=self.time_base,values=list(TIME_BASES),state='readonly',width=12)
        time_select.pack(side='left',padx=6);time_select.bind('<<ComboboxSelected>>',lambda e:self.draw_plot())
        self.graph_scale=ScaleControls(timing,self.plot_metric,self.draw_plot)
        self.graph_scale.pack(side='right')
        self.canvas=tk.Canvas(graph_area,height=170,bg='#122234',highlightthickness=0);self.canvas.pack(side='top',fill='both',expand=True,padx=16,pady=8)
        self.canvas.bind('<Configure>',lambda e:self.request_plot('main'))
        self.plot_channel.trace_add('write',lambda *_:self.draw_plot())
        self.plot_metric.trace_add('write',lambda *_:self.graph_scale.changed())
        status_bar=ttk.Frame(self);status_bar.pack(fill='x')
        status_bar.columnconfigure(0,weight=1)
        self.status=ttk.Label(status_bar,text='',padding=(16,5),wraplength=500);self.status.grid(row=0,column=0,sticky='ew')
        self.identity=ttk.Label(status_bar,text='Disconnected',padding=(8,5,16,5),anchor='e');self.identity.grid(row=0,column=1,sticky='e')
        self.protocol('WM_DELETE_WINDOW',self.close_app)
        self.after(30,self.process_events)
        self.after(PLOT_INTERVAL_MS,self.refresh_plots)
        self.after_idle(self.initialize_layout)

    def initialize_layout(self):
        # Requested height includes every label, editor and footer control,
        # including current Tk font/DPI metrics. Never allow the sash above it.
        self.update_idletasks()
        self.main_split.paneconfigure(self.channel_area,minsize=self.channel_area.winfo_reqheight())
        self.set_minimal_ui(self.user_settings.minimal_ui)
        if self.graph_visible:
            self.main_split.sash_place(0,0,max(self.channel_area.winfo_reqheight(),int(self.main_split.winfo_height()*.62)))

    def set_minimal_ui(self,minimal):
        if minimal and self.graph_visible:
            self.saved_sash_y=self.main_split.sash_coord(0)[1]
            self.main_split.forget(self.graph_area)
            self.graph_visible=False
        elif not minimal and not self.graph_visible:
            self.main_split.add(self.graph_area,minsize=200,stretch='always')
            self.graph_visible=True
            if self.saved_sash_y is not None:
                self.after_idle(lambda:self.main_split.sash_place(0,0,self.saved_sash_y))
        # Reserve space for complete channels plus all controls outside the pane.
        chrome=sum(w.winfo_reqheight() for w in self.pack_slaves() if w is not self.main_split)
        self.minsize(1080,self.channel_area.winfo_reqheight()+chrome+(206 if self.graph_visible else 0))
        self.invalidate_plot()

    def invalidate_plot(self):
        self.plots_dirty=True

    def request_plot(self,key):
        # Resize or explicit request: redraw this graph on the next tick, unthrottled.
        if not hasattr(self,'stale_plots'):self.stale_plots=set()
        if not hasattr(self,'plot_due'):self.plot_due={}
        self.stale_plots.add(key);self.plot_due[key]=0

    def open_settings(self):
        if self.settings_window and self.settings_window.winfo_exists():
            self.settings_window.lift();self.settings_window.focus_set()
        else:self.settings_window=SettingsWindow(self)

    def apply_preferences(self,proposed):
        proposed.validate()
        if (self.connected or self.connecting) and proposed.connection_key()!=self.user_settings.connection_key():
            raise ValueError('Disconnect before changing connection/device settings')
        save_preferences(self.preferences,proposed)
        self.live_edits.cancel()
        self.worker.post('instant_mode',proposed.instant_mode)
        self.user_settings=proposed
        self.set_minimal_ui(proposed.minimal_ui)
        self.resource.set(proposed.resource);self.demo.set(proposed.demo)
        self.time_base.set(proposed.graph_timebase)
        changed_interval=self.log_interval.get()!=proposed.log_interval
        self.log_interval.set(proposed.log_interval)
        if changed_interval:self.change_log_interval()
        self.worker.post('rate',proposed.poll_rate)
        self.plots_dirty=True
        self.refresh_controls()
        self.note('Settings saved. Connection changes apply on the next Connect.')

    def refresh_plots(self):
        # New samples mark every graph stale. Each graph is then redrawn when
        # its own due time arrives: 5 Hz for short windows, slower for long
        # windows where one pixel covers several seconds (see draw_history).
        if not hasattr(self,'stale_plots'):self.stale_plots=set()
        if not hasattr(self,'plot_due'):self.plot_due={}
        if self.plots_dirty:
            self.plots_dirty=False
            self.stale_plots.add('main');self.stale_plots.update(self.details)
            for detail in list(self.details.values()):detail.update_stats()
        now=time.monotonic()
        graphs=[('main',self.draw_plot)]+[(number,detail.redraw) for number,detail in list(self.details.items())]
        for key,draw in graphs:
            if key in self.stale_plots and now>=self.plot_due.get(key,0):
                self.stale_plots.discard(key)
                interval=draw()
                self.plot_due[key]=now+(interval if isinstance(interval,(int,float)) else 0)
        self.stale_plots.intersection_update({'main',*self.details})
        self.after(PLOT_INTERVAL_MS,self.refresh_plots)

    def open_detail(self,number):
        self.plot_channel.set(f'CH{number}')
        if number in self.details:
            self.details[number].lift();self.details[number].focus_set()
        else:self.details[number]=ChannelDetail(self,number)

    def show_log(self):
        if self.log_window and self.log_window.winfo_exists():
            self.log_window.deiconify();self.log_window.lift();return
        window=tk.Toplevel(self);window.title('BenchControl · Event log');window.geometry('950x320')
        scroll=ttk.Scrollbar(window,orient='vertical');scroll.pack(side='right',fill='y')
        text=tk.Text(window,font=('Consolas',10),wrap='word',yscrollcommand=scroll.set);text.pack(fill='both',expand=True)
        scroll.configure(command=text.yview)
        text.insert('end',''.join(self.event_lines));text.configure(state='disabled');text.see('end')
        window.text=text;self.log_window=window
        window.protocol('WM_DELETE_WINDOW',self.close_log)

    def close_log(self):
        if self.log_window:self.log_window.destroy()
        self.log_window=None

    def note(self,text):
        self.status.configure(text=text)
        line=datetime.now().strftime('%H:%M:%S')+' '+text+'\n'
        self.event_lines.append(line)
        window=self.log_window
        if window and window.winfo_exists():
            # Append only the new line. Follow the end only if the user is already
            # there, so scrolling back or selecting text is not disturbed.
            box=window.text;at_end=box.yview()[1]>=.999
            box.configure(state='normal');box.insert('end',line)
            excess=int(box.index('end-1c').split('.')[0])-1-EVENT_LOG_LINES
            if excess>0:box.delete('1.0',f'{excess+1}.0')
            box.configure(state='disabled')
            if at_end:box.see('end')

    def refresh_controls(self):
        for p in self.panels:p.controls(self.connected,self.busy)
        for detail in list(self.details.values()):detail.sync()
        if self.settings_window:self.settings_window.sync_lock()
        self.connect_button.configure(text='Disconnect' if self.connected else 'Connect',state='disabled' if self.connecting or self.busy else 'normal')

    def request_disconnect(self,closing=False):
        choice=ask_disconnect(self,closing)
        if choice is None:return
        self.live_edits.cancel()
        self.close_after_disconnect=closing
        self.busy=True
        self.worker.post('disconnect',choice=='off')
        self.refresh_controls()
        self.note('Switching all outputs off before disconnecting…' if choice=='off' else 'Disconnecting; outputs will retain their current state…')

    def connect_toggle(self):
        if self.connected:
            self.request_disconnect()
        else:
            if not self.demo.get() and not self.resource.get().strip():
                self.note('Choose a device in Settings before connecting.');self.open_settings();return
            self.connecting=True;self.first=True;self.history.clear()
            self.stats=[Stats(),Stats(),Stats()];self.pending_jobs=0
            for p in self.panels:p.reading=None
            self.worker.post('connect',self.resource.get().strip(),self.demo.get(),self.user_settings.connection_options());self.refresh_controls()
            self.note('Connecting…')

    def set_device_profile(self,profile):
        self.live_edits.cancel()
        self.device_profile=profile
        self.model_label.configure(text=profile.model)
        self.title('BenchControl · B&K '+profile.model+' · 1.9.1')
        for panel in self.panels:panel.configure_profile(profile)
        for detail in self.details.values():detail.panel.configure_profile(profile)

    def queue_live(self,number,field,delay=None):
        if self.connected and not self.busy and self.user_settings.instant_mode:
            self.live_edits.queue(number,field,self.user_settings.instant_delay_ms if delay is None else delay)

    def submit_live(self,number,field):
        if not self.connected or self.busy or not self.user_settings.instant_mode:return
        panel=self.panels[number-1]
        if panel.reading is None:return
        var=panel.v if field=='voltage' else panel.i
        try:
            value=float(var.get())
            validate(number,value if field=='voltage' else 0,value if field=='current' else 0,getattr(self,'device_profile',DEFAULT_PROFILE))
        except (ValueError,TypeError):
            self.note(f'CH{number} {field}: enter a valid value within channel limits.');return
        value=float(f'{value:.3f}')
        self.worker.post('set_live',number,field,value)
        self.note(f'CH{number} live {field}: {value:.3f} queued.')

    def command(self,name,*args):
        if not self.connected:return
        if self.busy and name!='all_off' and not (name=='output' and not args[1]):return
        self.live_edits.cancel()
        self.pending_jobs=getattr(self,'pending_jobs',0)+1
        self.busy=True;self.worker.post(name,*args);self.refresh_controls()
        self.note('All-off queued; waiting for hardware confirmation.' if name=='all_off' else 'Sending '+name+'…')

    def process_events(self):
        # Yield frequently to Tk input even if acquisition has built a queue.
        deadline=time.perf_counter()+.012
        handled=False
        try:
            while time.perf_counter()<deadline:
                kind,data=self.events.get_nowait();handled=True
                if kind=='resources':
                    self.available_resources=list(data)
                    if self.settings_window:self.settings_window.set_resources(data)
                    self.note(f'{len(data)} VISA resource(s) found. Select the PSU resource.')
                elif kind=='connected':
                    self.set_device_profile(profile_from_identity(data))
                    self.connected=True;self.connecting=False;self.identity.configure(text=('DEMO · ' if self.demo.get() else '')+data)
                    self.note('Connected. Existing output states retained.')
                    if not self.demo.get():
                        try:
                            self.user_settings.resource=self.resource.get().strip()
                            save_preferences(self.preferences,self.user_settings)
                        except OSError: pass
                elif kind=='snapshot':
                    for p,r,stats in zip(self.panels,data,self.stats):
                        p.update_reading(r,self.first);stats.add(r)
                    for number,detail in list(self.details.items()):
                        detail.panel.update_reading(data[number-1])
                    self.first=False
                    now=data.acquired_at
                    self.history.append((now,data));trim_history(self.history,now)
                    self.plots_dirty=True
                    if self.writer and now >= self.log_started_at and self.log_gate.due(now):
                        try:
                            stamp=data.timestamp
                            for r in data:self.writer.writerow([stamp,'DEMO' if self.demo.get() else 'HARDWARE',r.number,r.voltage,r.current,r.voltage*r.current,int(r.enabled),r.set_voltage,r.set_current,int(r.current_limited)])
                            # Flush at most once a second; stop_log() flushes the remainder.
                            if now-getattr(self,'last_flush',0.)>=CSV_FLUSH_SECONDS:
                                self.logfile.flush();self.last_flush=now
                        except OSError as e:
                            self.stop_log();self.note('CSV logging stopped: '+str(e))
                elif kind=='live_done':
                    ch,field,value=data
                    self.note(f'CH{ch} {field} {value:.3f} confirmed.')
                elif kind=='live_cancelled':
                    pass
                elif kind=='live_refused':
                    self.live_edits.cancel()
                    self.note('Live edit refused: '+data[1])
                elif kind=='done':
                    self.job_finished()
                    self.note('All outputs OFF confirmed.' if data=='all_off' else data+' confirmed.')
                elif kind=='cancelled':
                    self.job_finished()
                    self.note(f'Queued {data} request cancelled because an OFF request took priority. Nothing was sent for it.')
                elif kind=='refused':
                    operation,error=data
                    if operation in ('apply','output','all_off'):self.job_finished()
                    self.note(f'{operation} not performed: {error}. Connection and outputs unchanged.')
                    self.after_idle(lambda message=error:messagebox.showwarning('Request not performed',message,parent=self))
                elif kind=='disconnected':
                    self.connected=False;self.busy=False;self.pending_jobs=0;self.stop_log();self.mark_stale();self.note(data)
                    if self.close_after_disconnect:
                        self.destroy();return
                elif kind=='error':
                    operation,error=data
                    self.close_after_disconnect=False
                    if operation!='scan':
                        self.connected=False;self.connecting=False;self.busy=False;self.pending_jobs=0;self.stop_log();self.mark_stale()
                    self.note(f'{operation}: {error}'+(' — OUTPUT STATE UNKNOWN. Check PSU front panel.' if operation!='scan' else ''))
        except queue.Empty:pass
        # One control-state refresh per batch rather than per event.
        if handled:self.refresh_controls()
        self.after(30,self.process_events)

    def job_finished(self):
        # Busy stays set until every queued control request has reported back,
        # e.g. an OFF still waiting behind an Apply that just completed.
        self.pending_jobs=max(0,getattr(self,'pending_jobs',1)-1)
        if not self.pending_jobs:self.busy=False

    def mark_stale(self):
        self.live_edits.cancel()
        for p in self.panels:p.stale()
        for detail in list(self.details.values()):detail.panel.stale();detail.sync()
        self.identity.configure(text='Disconnected')

    def draw_plot(self):
        if not self.graph_visible:return
        return draw_history(self.canvas,self.history,int(self.plot_channel.get()[-1])-1,self.plot_metric.get(),TIME_BASES[self.time_base.get()],self.graph_scale.mode.get(),self.graph_scale.manual_max())

    def save_settings(self):
        try:
            channels=[dict(channel=p.number,voltage=p.values()[0],current=p.values()[1]) for p in self.panels]
            path=filedialog.asksaveasfilename(defaultextension='.json',filetypes=[('Settings','*.json')])
            if path:Path(path).write_text(json.dumps({'model':self.device_profile.model,'channels':channels},indent=2),encoding='utf-8');self.note('Settings saved. Output states are never saved.')
        except Exception as e:messagebox.showerror('Save settings',str(e))

    def load_settings(self):
        self.live_edits.cancel()
        path=filedialog.askopenfilename(filetypes=[('Settings','*.json')])
        if not path:return
        try:
            doc=json.loads(Path(path).read_text(encoding='utf-8'))
            if doc.get('model')!=self.device_profile.model or len(doc['channels'])!=3:raise ValueError('Preset model must match '+self.device_profile.model)
            rows=doc['channels']
            if [r['channel'] for r in rows]!=[1,2,3]:raise ValueError('Invalid channel list')
            for r in rows:validate(r['channel'],r['voltage'],r['current'],self.device_profile)
            for p,r in zip(self.panels,rows):p.v.set(f"{r['voltage']:.3f}");p.i.set(f"{r['current']:.3f}")
            self.note('Preset loaded into editors only. Press Enter in each field to send it.' if self.user_settings.instant_mode else 'Settings loaded into editor only. Turn outputs off, then Apply each channel.')
        except Exception as e:messagebox.showerror('Load settings',str(e))

    def change_log_interval(self):
        self.log_gate.reset(LOG_INTERVALS[self.log_interval.get()])
        if self.logfile:self.note('CSV interval changed to '+self.log_interval.get()+'. Next acquired sample starts the new interval.')

    def toggle_log(self):
        if self.logfile:self.stop_log();self.note('CSV log closed.');return
        if not self.connected:self.note('Connect before starting a CSV log.');return
        path=filedialog.asksaveasfilename(defaultextension='.csv',filetypes=[('CSV log','*.csv')])
        if path:
            try:
                self.log_gate.reset(LOG_INTERVALS[self.log_interval.get()])
                self.log_started_at=time.monotonic();self.last_flush=self.log_started_at
                self.logfile=open(path,'w',newline='',encoding='utf-8-sig');self.writer=csv.writer(self.logfile)
                self.writer.writerow(['timestamp','source','channel','voltage_V','current_A','calculated_power_W','output_on','set_voltage_V','current_limit_A','near_current_limit_estimated'])
                self.log_button.configure(text='Stop CSV log');self.note('Logging to '+path)
            except OSError as e:self.stop_log();messagebox.showerror('CSV log',str(e))

    def stop_log(self):
        if self.logfile:
            try:self.logfile.close()
            except OSError:pass
        self.logfile=None;self.writer=None;self.log_button.configure(text='Start CSV log…')

    def close_app(self):
        if self.busy or self.connecting:
            messagebox.showinfo('Operation pending','Wait for the pending operation to finish before closing.')
            return
        if self.connected:
            self.request_disconnect(closing=True)
            return
        self.stop_log();self.destroy()


if __name__=='__main__':App().mainloop()
