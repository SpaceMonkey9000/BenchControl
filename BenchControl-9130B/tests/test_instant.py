import queue
import tempfile
import sys
import threading
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App,Worker
from instrument import PSU,DemoDevice,Refused,PollInterrupted,Channel
from live_edits import LiveEdits
from preferences import Preferences,save_preferences,load_preferences
from ui_controls import ChannelPanel,DigitEntry


class Scheduler:
    def __init__(self):self.jobs={};self.serial=0
    def after(self,delay,fn):
        self.serial+=1;self.jobs[self.serial]=(delay,fn);return self.serial
    def after_cancel(self,job):self.jobs.pop(job,None)
    def fire(self):
        jobs=list(self.jobs.values());self.jobs.clear()
        for _,fn in jobs:fn()


class LiveEditTests(unittest.TestCase):
    def test_debounce_replaces_same_field_and_keeps_other_channel(self):
        scheduler=Scheduler();send=Mock();live=LiveEdits(scheduler,send)
        live.queue(1,'voltage');live.queue(1,'voltage');live.queue(2,'current',80)
        self.assertEqual(len(scheduler.jobs),2);send.assert_not_called()
        scheduler.fire()
        self.assertEqual([c.args for c in send.call_args_list],[(1,'voltage'),(2,'current')])
    def test_cancel_removes_every_pending_callback(self):
        scheduler=Scheduler();send=Mock();live=LiveEdits(scheduler,send)
        live.queue(1,'voltage');live.queue(3,'current');live.cancel();scheduler.fire()
        send.assert_not_called();self.assertFalse(live.pending)
    def test_snapshot_or_variable_change_has_no_automatic_write(self):
        scheduler=Scheduler();send=Mock();LiveEdits(scheduler,send)
        scheduler.fire();send.assert_not_called()
    def test_live_mode_defaults_off_and_validates_boolean(self):
        self.assertFalse(Preferences().instant_mode)
        with self.assertRaises(ValueError):Preferences(instant_mode='yes').validate()
    def test_configured_delay_is_used_except_explicit_enter(self):
        app=SimpleNamespace(connected=True,busy=False,user_settings=Preferences(instant_mode=True,instant_delay_ms=1200),live_edits=Mock())
        App.queue_live(app,1,'voltage')
        app.live_edits.queue.assert_called_with(1,'voltage',1200)
        App.queue_live(app,1,'current',0)
        app.live_edits.queue.assert_called_with(1,'current',0)
    def test_delay_validation_and_persistence(self):
        self.assertEqual(Preferences().instant_delay_ms,750)
        for value in (0,99,3001,True,750.5,'750'):
            with self.assertRaises(ValueError):Preferences(instant_delay_ms=value).validate()
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preferences.json'
            settings=Preferences(instant_mode=True,instant_delay_ms=1500)
            save_preferences(path,settings)
            self.assertEqual(load_preferences(path),settings)
    def test_live_label_does_not_change_between_pending_and_confirmed(self):
        variable=lambda value:SimpleNamespace(get=lambda:value)
        panel=SimpleNamespace(app=SimpleNamespace(user_settings=Preferences(instant_mode=True)),v=variable('6'),i=variable('.1'),
            reading=Channel(1,5,.1,True,5,.1),dirty=Mock(),palette=('#132439','#ffffff'))
        ChannelPanel.update_dirty(panel)
        pending=panel.dirty.configure.call_args
        panel.v=variable('5')
        ChannelPanel.update_dirty(panel)
        self.assertEqual(panel.dirty.configure.call_args,pending)
        self.assertEqual(pending.kwargs['text'],'LIVE EDITS')
    def app(self,value='7.500'):
        panel=SimpleNamespace(v=SimpleNamespace(get=lambda:value),i=SimpleNamespace(get=lambda:'invalid'),reading=Channel(1,3.3,.1,True,3.3,.1))
        return SimpleNamespace(connected=True,busy=False,user_settings=Preferences(instant_mode=True),panels=[panel],worker=Mock(),note=Mock())
    def test_submit_changes_only_edited_field_even_if_other_draft_invalid(self):
        app=self.app();App.submit_live(app,1,'voltage')
        app.worker.post.assert_called_once_with('set_live',1,'voltage',7.5)
    def test_return_to_original_value_still_replaces_queued_edit(self):
        app=self.app('3.300');App.submit_live(app,1,'voltage')
        app.worker.post.assert_called_once_with('set_live',1,'voltage',3.3)
    def test_invalid_or_disconnected_edits_send_nothing(self):
        for value in ('','NaN','inf','-1','30.001'):
            app=self.app(value);App.submit_live(app,1,'voltage');app.worker.post.assert_not_called()
        for key,value in (('connected',False),('busy',True)):
            app=self.app();setattr(app,key,value);App.submit_live(app,1,'voltage');app.worker.post.assert_not_called()
        app=self.app();app.user_settings.instant_mode=False;App.submit_live(app,1,'voltage');app.worker.post.assert_not_called()
    def test_live_channel_editors_remain_active_and_apply_is_hidden(self):
        app=SimpleNamespace(user_settings=Preferences(instant_mode=True))
        panel=SimpleNamespace(app=app,reading=Channel(1,3.3,.1,True,3.3,.1),last_controls=None,ve=Mock(),ie=Mock(),apply=Mock(),output_toggle=Mock())
        ChannelPanel.controls(panel,True)
        panel.ve.configure.assert_called_with(state='normal');panel.ie.configure.assert_called_with(state='normal')
        panel.apply.pack_forget.assert_called_once()
        panel.output_toggle.configure.assert_called_with(text='Output OFF',state='normal',style='TButton')
    def test_enter_in_live_mode_queues_only_its_field(self):
        panel=SimpleNamespace(number=2,app=SimpleNamespace(user_settings=Preferences(instant_mode=True),queue_live=Mock()),apply_settings=Mock())
        ChannelPanel.commit_field(panel,'current')
        panel.app.queue_live.assert_called_once_with(2,'current',0);panel.apply_settings.assert_not_called()


class LiveInstrumentTests(unittest.TestCase):
    def setUp(self):
        self.device=DemoDevice();self.psu=PSU(self.device)
        self.device.write=Mock(wraps=self.device.write)
    def test_live_voltage_keeps_current_limit_and_output_on(self):
        self.device.settings[0][2]=True;self.psu.set_live(1,'voltage',7.5)
        self.assertEqual(self.device.settings[0],[7.5,.1,True])
        self.assertEqual([c.args[0] for c in self.device.write.call_args_list],['INST CH1','VOLT 7.500'])
    def test_live_current_keeps_voltage_and_output_off(self):
        self.psu.set_live(3,'current',.075)
        self.assertEqual(self.device.settings[2],[1.2,.075,False])
        self.assertEqual([c.args[0] for c in self.device.write.call_args_list],['INST CH3','CURR 0.075'])
    def test_manual_apply_still_refuses_an_active_output(self):
        self.device.settings[0][2]=True
        with self.assertRaises(Refused):self.psu.apply(1,5,.2)
        self.assertEqual(self.device.settings[0],[3.3,.1,True])
    def test_invalid_live_requests_never_write(self):
        for args in ((3,'voltage',5.001),(1,'current',3.001),(1,'voltage',float('nan')),(1,'other',1),(0,'voltage',1)):
            with self.assertRaises(Refused):self.psu.set_live(*args)
        self.device.write.assert_not_called()
    def test_combined_mode_blocks_live_writes(self):
        query=self.device.query
        self.device.query=lambda cmd:'1' if cmd=='OUTP:SER?' else query(cmd)
        with self.assertRaises(Refused):self.psu.set_live(1,'voltage',5)
        self.device.write.assert_not_called()
    def test_nonfinite_readback_fails_verification(self):
        query=self.device.query
        self.device.query=lambda cmd:'nan' if cmd=='VOLT?' else query(cmd)
        with self.assertRaisesRegex(RuntimeError,'verification failed'):self.psu.set_live(1,'voltage',5)
    def test_off_or_newer_edit_can_interrupt_before_setpoint_write(self):
        with self.assertRaises(PollInterrupted):self.psu.set_live(1,'voltage',5,interrupt=lambda:True)
        self.assertEqual(self.device.settings[0],[3.3,.1,False])


class LiveWorkerTests(unittest.TestCase):
    def worker(self):
        events=queue.Queue()
        with patch.object(Worker,'start'):worker=Worker(events)
        worker.psu=PSU(DemoDevice());worker.next_poll=time.monotonic()+100
        self.addCleanup(lambda:worker.post('disconnect'))
        return worker,events,worker.psu.device
    def wait(self,events,kind):
        until=time.monotonic()+3
        while time.monotonic()<until:
            event=events.get(timeout=3)
            if event[0]=='error':self.fail(str(event))
            if event[0]==kind:return event[1]
        self.fail('Missing '+kind)
    def test_live_gate_refuses_without_disconnect_when_not_opted_in(self):
        worker,events,device=self.worker();worker.post('set_live',1,'voltage',7)
        threading.Thread.start(worker);self.wait(events,'live_refused')
        self.assertIsNotNone(worker.psu);self.assertEqual(device.settings[0][0],3.3)
    def test_coalesces_same_field_preserving_other_field(self):
        worker,events,device=self.worker();worker.post('instant_mode',True)
        for v in (4,5,6):worker.post('set_live',1,'voltage',v)
        worker.post('set_live',1,'current',.15)
        threading.Thread.start(worker)
        self.wait(events,'live_done');self.wait(events,'live_done')
        self.assertEqual(device.settings[0],[6,.15,False])
    def test_off_cancels_all_queued_live_edits(self):
        worker,events,device=self.worker();worker.post('instant_mode',True)
        worker.post('set_live',1,'voltage',9);worker.post('set_live',2,'current',2)
        worker.post('output',1,False)
        threading.Thread.start(worker);self.wait(events,'live_cancelled');self.wait(events,'live_cancelled')
        self.assertEqual(device.settings[0],[3.3,.1,False]);self.assertEqual(device.settings[1],[5,.2,False])
    def test_disabling_mode_cancels_queued_edit(self):
        worker,events,device=self.worker();worker.instant_mode=True
        worker.post('set_live',1,'voltage',9);worker.post('instant_mode',False)
        threading.Thread.start(worker);self.wait(events,'live_cancelled')
        self.assertEqual(device.settings[0],[3.3,.1,False])
    def test_worker_updates_an_active_channel_without_output_toggle(self):
        worker,events,device=self.worker();device.settings[0][2]=True
        device.write=Mock(wraps=device.write)
        worker.post('instant_mode',True);worker.post('set_live',1,'current',.25)
        threading.Thread.start(worker);self.wait(events,'live_done')
        self.assertEqual(device.settings[0],[3.3,.25,True])
        self.assertFalse(any(c.args[0].startswith('CHAN:OUTP') for c in device.write.call_args_list))
    def test_write_failure_disconnects_and_never_retries(self):
        worker,events,device=self.worker();device.settings[0][2]=True
        write=device.write;attempts=[]
        def failing(cmd):
            if cmd.startswith('VOLT '):attempts.append(cmd);raise IOError('timeout')
            write(cmd)
        device.write=failing
        worker.post('instant_mode',True);worker.post('set_live',1,'voltage',9)
        threading.Thread.start(worker)
        until=time.monotonic()+3
        while time.monotonic()<until:
            kind,data=events.get(timeout=3)
            if kind=='error':break
        else:self.fail('No error')
        self.assertIsNone(worker.psu);self.assertEqual(attempts,['VOLT 9.000'])
        self.assertTrue(device.settings[0][2])
