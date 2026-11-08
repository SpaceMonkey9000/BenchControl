"""Regression tests for the 1.7.6 review fixes."""
import os
import queue
import sys
import time
import tkinter as tk
import unittest
from collections import deque
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App, Worker, EVENT_LOG_LINES
from instrument import PSU, DemoDevice, Channel, Refused
from preferences import preferences_path
from settings_ui import SettingsWindow
from ui_controls import draw_history, PLOT_MAX_SECONDS, PLOT_MIN_SECONDS


class SlowDemo(DemoDevice):
    def query(self,cmd):
        time.sleep(.03);return super().query(cmd)


def drain(events,seconds):
    end=time.monotonic()+seconds;seen=[]
    while time.monotonic()<end:
        try:seen.append(events.get(timeout=.05))
        except queue.Empty:pass
    return [(k,d) for k,d in seen if k!='snapshot']


class WorkerQueueTests(unittest.TestCase):
    def worker(self,device):
        events=queue.Queue();worker=Worker(events)
        worker.psu=PSU(device);worker.next_poll=0
        return worker,events

    def test_second_off_never_cancels_first_off(self):
        device=SlowDemo()
        for row in device.settings:row[2]=True
        worker,events=self.worker(device)
        time.sleep(.1)  # a monitoring scan is in flight
        worker.post('output',1,False);worker.post('output',2,False)
        seen=drain(events,1.5)
        self.assertNotIn(('cancelled','output'),seen)
        self.assertEqual([k for k,_ in seen].count('done'),2)
        self.assertEqual([row[2] for row in device.settings],[False,False,True])

    def test_off_still_cancels_queued_output_on_and_apply(self):
        device=SlowDemo();worker,events=self.worker(device)
        time.sleep(.1)
        worker.post('apply',2,1.0,.1);worker.post('output',1,True,(3.3,.1));worker.post('output',3,False)
        seen=drain(events,1.5)
        self.assertIn(('cancelled','apply'),seen);self.assertIn(('cancelled','output'),seen)
        self.assertFalse(device.settings[0][2]);self.assertEqual(device.settings[1][:2],[5,.2])

    def test_rate_change_survives_an_off_request(self):
        device=SlowDemo();worker,events=self.worker(device)
        time.sleep(.1)
        worker.post('rate',2);worker.post('output',1,False)
        drain(events,1)
        self.assertAlmostEqual(worker.poll_interval,.5)

    def test_refusal_keeps_connection(self):
        device=DemoDevice();worker,events=self.worker(device)
        worker.post('output',1,True,(9.9,.1))  # drafts differ from hardware
        seen=drain(events,.5)
        self.assertIn(('refused',('output','Settings changed since confirmation. Review and retry')),seen)
        self.assertNotIn('error',[k for k,_ in seen])
        self.assertIsNotNone(worker.psu);self.assertFalse(device.settings[0][2])
        device.settings[1][2]=True
        worker.post('apply',2,1,.1)
        seen=drain(events,.5)
        self.assertEqual([k for k,_ in seen],['refused']);self.assertIsNotNone(worker.psu)

    def test_communication_failure_still_disconnects(self):
        device=DemoDevice();worker,events=self.worker(device)
        def broken(cmd):raise IOError('VI_ERROR_TMO')
        device.write=broken
        worker.post('output',1,False)
        seen=drain(events,.5)
        self.assertEqual(seen[-1][0],'error');self.assertIsNone(worker.psu)

    def test_bad_rate_does_not_disconnect(self):
        worker,events=self.worker(DemoDevice())
        worker.post('rate',7)
        self.assertIn('refused',[k for k,_ in drain(events,.3)]);self.assertIsNotNone(worker.psu)


class AllOffTests(unittest.TestCase):
    def test_failed_write_on_one_channel_does_not_skip_others(self):
        class Flaky(DemoDevice):
            def write(self,cmd):
                if cmd=='CHAN:OUTP OFF' and self.ch==1:raise IOError('VI_ERROR_TMO')
                super().write(cmd)
        device=Flaky()
        for row in device.settings:row[2]=True
        with self.assertRaisesRegex(RuntimeError,'All-off NOT confirmed.*CH1 still ON.*VI_ERROR_TMO'):PSU(device).all_off()
        self.assertEqual([row[2] for row in device.settings],[True,False,False])

    def test_refusals_are_runtime_and_value_errors(self):
        self.assertTrue(issubclass(Refused,RuntimeError) and issubclass(Refused,ValueError))

    def test_output_on_selects_channel_once(self):
        device=DemoDevice();device.write=Mock(wraps=device.write)
        PSU(device).output(2,True,(5,.2))
        self.assertEqual([c.args[0] for c in device.write.call_args_list].count('INST CH2'),1)


class AppBusyTests(unittest.TestCase):
    def stub(self):
        return SimpleNamespace(events=queue.Queue(),busy=True,pending_jobs=2,refresh_controls=Mock(),note=Mock(),after=Mock(),
                               after_idle=Mock(),process_events=Mock(),job_finished=lambda:App.job_finished(app))
    def test_busy_held_until_every_queued_request_reports(self):
        global app
        app=self.stub()
        app.events.put(('done','apply'));App.process_events(app)
        self.assertTrue(app.busy)
        app.events.put(('done','output'));App.process_events(app)
        self.assertFalse(app.busy)
        self.assertEqual(app.refresh_controls.call_count,2)

    def test_cancel_and_refusal_are_reported(self):
        global app
        app=self.stub()
        app.events.put(('cancelled','apply'));app.events.put(('refused',('output','Settings changed')))
        App.process_events(app)
        self.assertFalse(app.busy);self.assertEqual(app.note.call_count,2)
        self.assertIn('cancelled',app.note.call_args_list[0].args[0])
        app.after_idle.assert_called_once()
        app.refresh_controls.assert_called_once()


class EventLogTests(unittest.TestCase):
    def setUp(self):
        try:self.root=tk.Tk();self.root.withdraw()
        except tk.TclError as exc:self.skipTest('Tk display unavailable: '+str(exc))
    def tearDown(self):
        self.root.destroy()
    def app(self):
        stub=SimpleNamespace(status=Mock(),event_lines=deque(maxlen=EVENT_LOG_LINES),log_window=None)
        window=tk.Toplevel(self.root);text=tk.Text(window,height=5);text.pack();window.text=text;text.configure(state='disabled')
        stub.log_window=window
        return stub,text
    def test_new_lines_append_without_jumping_when_scrolled_back(self):
        app,text=self.app()
        for n in range(200):App.note(app,f'line {n}')
        self.root.update()
        text.yview_moveto(0);self.root.update()
        App.note(app,'new');self.root.update()
        self.assertEqual(text.yview()[0],0.)
        self.assertIn('new',text.get('end-2l','end'));self.assertEqual(len(app.event_lines),201)
    def test_follows_end_when_already_at_end(self):
        app,text=self.app()
        for n in range(200):App.note(app,f'line {n}');self.root.update()
        self.assertGreaterEqual(text.yview()[1],.999)


class SettingsTests(unittest.TestCase):
    def test_unchanged_timebase_keeps_main_screen_choice(self):
        var=lambda v:SimpleNamespace(get=lambda:v)
        app=SimpleNamespace(time_base=var('5 min'),log_interval=var('10 s'),apply_preferences=Mock())
        window=SimpleNamespace(app=app,opened={'graph_timebase':'1 min','log_interval':'Every sample'},close=Mock(),
            vars={'instant_delay_ms':var('750'),'resource':var(''),'demo':var(True),'minimal_ui':var(False),'poll_rate':var('10'),'confirm_output':var(True),
                  'confirm_setpoints':var(False),'io_timeout_ms':var('1500'),'usb_query_delay_ms':var('0'),
                  'graph_timebase':var('1 min'),'log_interval':var('Every sample')})
        SettingsWindow.save(window)
        saved=app.apply_preferences.call_args.args[0]
        self.assertEqual((saved.graph_timebase,saved.log_interval),('5 min','10 s'))
        window.vars['graph_timebase']=var('15 min')
        SettingsWindow.save(window)
        self.assertEqual(app.apply_preferences.call_args.args[0].graph_timebase,'15 min')

    def test_preferences_path_uses_localappdata(self):
        with patch.dict(os.environ,{'LOCALAPPDATA':'/redirected/local'}):
            self.assertEqual(preferences_path(),Path('/redirected/local/BenchControl9130B/preferences.json'))


class GraphTests(unittest.TestCase):
    def canvas(self,width=1100):
        return SimpleNamespace(delete=Mock(),winfo_width=lambda:width,winfo_height=lambda:300,create_text=Mock(),create_line=Mock())
    def history(self,n,value=lambda t:5.):
        return [(t/15,[Channel(c,value(t),.1,True,5,.2) for c in (1,2,3)]) for t in range(n)]
    def test_long_window_preserves_spike_and_slows_redraw(self):
        canvas=self.canvas();history=self.history(54000,lambda t:5.4 if t==30000 else (-.01 if t==100 else 5.))
        interval=draw_history(canvas,history,0,'Voltage (V)',3600,'Channel limits')
        coords=canvas.create_line.call_args_list[-1].args
        ys=coords[1::2]
        self.assertLess(len(coords),4*1100+8)
        self.assertEqual(min(ys),300-22-(300-22-32)*5.4/5.5)  # narrow spike retained
        self.assertEqual(interval,PLOT_MAX_SECONDS)
        title=canvas.create_text.call_args_list[0].kwargs.get('text') or canvas.create_text.call_args_list[0].args[2]
        self.assertNotIn('clipped',title)  # -10 mV readback noise is not clipping
    def test_short_window_redraws_at_five_hz(self):
        self.assertEqual(draw_history(self.canvas(),self.history(300),0,'Voltage (V)',10,'Channel limits'),PLOT_MIN_SECONDS)

    def test_refresh_respects_each_graphs_due_time(self):
        app=SimpleNamespace(plots_dirty=True,details={},draw_plot=Mock(return_value=10.),after=Mock(),refresh_plots=Mock(),stale_plots=set(),plot_due={})
        App.refresh_plots(app);self.assertEqual(app.draw_plot.call_count,1)
        app.plots_dirty=True;App.refresh_plots(app)
        self.assertEqual(app.draw_plot.call_count,1)  # not yet due; stays pending
        self.assertIn('main',app.stale_plots)
        App.request_plot(app,'main');App.refresh_plots(app)
        self.assertEqual(app.draw_plot.call_count,2)  # resize redraws immediately


class CsvFlushTests(unittest.TestCase):
    def test_flush_at_most_once_per_second(self):
        from acquisition import ScanSample
        from timebase import LogGate
        app=SimpleNamespace(events=queue.Queue(),panels=[Mock() for _ in range(3)],stats=[Mock() for _ in range(3)],details={},first=False,
            demo=SimpleNamespace(get=lambda:False),history=deque(),plots_dirty=False,writer=Mock(),logfile=Mock(),log_started_at=0,
            last_flush=100.,log_gate=LogGate(),refresh_controls=Mock(),after=Mock(),process_events=Mock())
        for n in range(30):
            sample=ScanSample([Channel(c,1,.1,False,1,.1) for c in (1,2,3)]);sample.acquired_at=100+n*.1
            app.events.put(('snapshot',sample))
        while not app.events.empty():App.process_events(app)
        self.assertEqual(app.writer.writerow.call_count,90)
        self.assertEqual(app.logfile.flush.call_count,2)


if __name__=='__main__':unittest.main()
