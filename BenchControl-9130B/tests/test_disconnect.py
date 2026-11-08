import queue
import sys
import time
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import Worker,App
from ui_controls import ChannelPanel
from instrument import Channel

class DisconnectTests(unittest.TestCase):
    def event(self,events,kind):
        until=time.monotonic()+3
        while time.monotonic()<until:
            name,data=events.get(timeout=3)
            if name=='error' and kind!='error':self.fail(str(data))
            if name==kind:return data
        self.fail('Missing '+kind)
    def connected_worker(self):
        events=queue.Queue();worker=Worker(events)
        worker.post('connect','',True);self.event(events,'connected');self.event(events,'snapshot')
        return worker,events,worker.psu.device
    def test_disconnect_off_verifies_before_releasing(self):
        worker,events,device=self.connected_worker()
        for s in device.settings:s[2]=True
        checks=[];query=device.query
        def read(cmd):
            result=query(cmd)
            if cmd=='CHAN:OUTP?':checks.append('verified')
            return result
        device.query=read;device.close=Mock(side_effect=lambda:checks.append('closed'))
        worker.post('disconnect',True)
        message=self.event(events,'disconnected')
        self.assertEqual(checks,['verified','verified','verified','closed'])
        self.assertFalse(any(s[2] for s in device.settings));self.assertIn('OFF confirmed',message)
        self.assertIsNone(worker.psu)
    def test_disconnect_leave_does_not_change_outputs(self):
        worker,events,device=self.connected_worker()
        device.settings[0][2]=True
        original=device.write;device.write=Mock(wraps=original)
        worker.post('disconnect',False);self.event(events,'disconnected')
        self.assertTrue(device.settings[0][2])
        self.assertFalse(any(call.args[0].startswith(('APPL:OUT','CHAN:OUTP')) for call in device.write.call_args_list))
    def test_failed_shutdown_never_reports_confirmation(self):
        worker,events,device=self.connected_worker()
        worker.psu.all_off=Mock(side_effect=RuntimeError('Readback timeout'))
        worker.post('disconnect',True)
        name,error=self.event(events,'error')
        self.assertEqual(name,'disconnect');self.assertIn('Shutdown not confirmed',error)
        self.assertIsNone(worker.psu)
        remaining=[]
        while not events.empty():remaining.append(events.get_nowait()[0])
        self.assertNotIn('disconnected',remaining)
    def stub(self):
        return SimpleNamespace(close_after_disconnect=False,busy=False,live_edits=Mock(),worker=Mock(),refresh_controls=Mock(),note=Mock())
    def test_cancel_changes_nothing(self):
        app=self.stub()
        with patch('app.ask_disconnect',return_value=None):App.request_disconnect(app)
        self.assertFalse(app.busy);app.worker.post.assert_not_called()
    def test_leave_choice_queues_one_atomic_disconnect(self):
        app=self.stub()
        with patch('app.ask_disconnect',return_value='leave'):App.request_disconnect(app)
        app.worker.post.assert_called_once_with('disconnect',False);self.assertTrue(app.busy)
    def test_close_off_waits_for_worker_instead_of_destroying(self):
        app=self.stub();app.destroy=Mock()
        with patch('app.ask_disconnect',return_value='off'):App.request_disconnect(app,closing=True)
        app.worker.post.assert_called_once_with('disconnect',True)
        self.assertTrue(app.close_after_disconnect);app.destroy.assert_not_called()
    def test_toggle_label_and_busy_off_availability(self):
        panel=SimpleNamespace(reading=Channel(1,5,.1,True,5,.5),last_controls=None,app=SimpleNamespace(user_settings=SimpleNamespace(instant_mode=False)),ve=Mock(),ie=Mock(),apply=Mock(),output_toggle=Mock())
        ChannelPanel.controls(panel,True,True)
        panel.output_toggle.configure.assert_called_with(text='Output OFF',state='normal',style='TButton')
        panel.reading.enabled=False
        ChannelPanel.controls(panel,True,True)
        panel.output_toggle.configure.assert_called_with(text='Output ON',state='disabled',style='TButton')
        ChannelPanel.controls(panel,True,False)
        panel.output_toggle.configure.assert_called_with(text='Output ON',state='normal',style='TButton')
        ChannelPanel.controls(panel,False,False)
        panel.output_toggle.configure.assert_called_with(text='Output ON',state='disabled',style='TButton')
    def test_toggle_uses_confirmed_state(self):
        panel=SimpleNamespace(reading=Channel(1,5,.1,True,5,.5),number=1,app=SimpleNamespace(connected=True,command=Mock()),enable=Mock())
        ChannelPanel.toggle_output(panel)
        panel.app.command.assert_called_once_with('output',1,False)
        panel.enable.assert_not_called()
        panel.reading.enabled=False
        ChannelPanel.toggle_output(panel)
        panel.enable.assert_called_once_with()
        panel.app.command.reset_mock();panel.enable.reset_mock();panel.reading=None
        ChannelPanel.toggle_output(panel)
        panel.app.command.assert_not_called();panel.enable.assert_not_called()
    def test_status_under_channel_heading_is_green_when_on(self):
        panel=SimpleNamespace(reading=None,alert_until=0,set_palette=Mock(),state=Mock(),vmeter=Mock(),imeter=Mock(),power=Mock(),applied=Mock(),update_dirty=Mock(),v=Mock(),i=Mock())
        ChannelPanel.update_reading(panel,Channel(1,5,.1,True,5,.5))
        panel.state.configure.assert_called_with(text='OUTPUT ON',bg='#16804a',fg='#ffffff')
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,5,.5))
        panel.state.configure.assert_called_with(text='OUTPUT OFF',bg='#233449',fg='#a8b7c9')

if __name__=='__main__':unittest.main()
