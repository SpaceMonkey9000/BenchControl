import json
from pathlib import Path
import queue
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from preferences import Preferences,load_preferences,save_preferences
from app import App,Worker
from ui_controls import ChannelPanel
from instrument import Channel,DemoDevice

class Var:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value

class PreferencesTests(unittest.TestCase):
    def test_round_trip_disabled_prompt_and_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'preferences.json'
            settings=Preferences(resource='USB0::TEST::INSTR',minimal_ui=True,confirm_output=False,confirm_setpoints=True,poll_rate=15,io_timeout_ms=2500,usb_query_delay_ms=2)
            save_preferences(path,settings);self.assertEqual(load_preferences(path),settings)
    def test_legacy_resource_is_preserved(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'preferences.json';path.write_text(json.dumps({'resource':'USB0::OLD::INSTR'}))
            settings=load_preferences(path)
        self.assertEqual(settings.resource,'USB0::OLD::INSTR');self.assertTrue(settings.confirm_output)
    def test_invalid_fields_fall_back_individually(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'preferences.json';path.write_text(json.dumps({'resource':'PSU_ALIAS','poll_rate':999,'confirm_output':'false','usb_query_delay_ms':-1}))
            settings=load_preferences(path)
        self.assertEqual(settings.resource,'PSU_ALIAS');self.assertEqual(settings.poll_rate,10)
        self.assertTrue(settings.confirm_output);self.assertEqual(settings.usb_query_delay_ms,0)
    def test_invalid_timeouts_and_nonfinite_delay(self):
        for settings in (Preferences(io_timeout_ms=100),Preferences(io_timeout_ms=10001),Preferences(usb_query_delay_ms=float('nan')),Preferences(usb_query_delay_ms=101)):
            with self.assertRaises(ValueError):settings.validate()
    def panel(self,confirm_output=True,confirm_setpoints=False):
        settings=Preferences(confirm_output=confirm_output,confirm_setpoints=confirm_setpoints)
        app=SimpleNamespace(connected=True,busy=False,command=Mock(),user_settings=settings)
        return SimpleNamespace(app=app,reading=Channel(1,0,0,False,5,.1),number=1,values=lambda:(5,.1),v=Var('5.000'),i=Var('0.100'))
    def test_output_confirmation_can_be_disabled(self):
        panel=self.panel(False)
        with patch('ui_controls.messagebox.askyesno') as ask:ChannelPanel.enable(panel)
        ask.assert_not_called();panel.app.command.assert_called_once_with('output',1,True,(5,.1))
    def test_first_hardware_snapshot_can_enable_without_apply(self):
        panel=self.panel(False);panel.reading=None
        panel.v=Var('0.000');panel.i=Var('0.000')
        panel.values=lambda:(float(panel.v.get()),float(panel.i.get()))
        panel.alert_until=0
        for name in ('set_palette','state','vmeter','imeter','power','applied','update_dirty','after'):
            setattr(panel,name,Mock())
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,5.1,.5))
        ChannelPanel.enable(panel)
        panel.app.command.assert_called_once_with('output',1,True,(5.1,.5))

    def test_enabled_output_confirmation_can_cancel(self):
        panel=self.panel(True)
        with patch('ui_controls.messagebox.askyesno',return_value=False) as ask:ChannelPanel.enable(panel)
        ask.assert_called_once();panel.app.command.assert_not_called()
    def test_disabled_prompt_still_rejects_unapplied_edits(self):
        panel=self.panel(False);panel.v.set('6.000');panel.values=lambda:(6,.1)
        with patch('ui_controls.messagebox.showerror'),patch('ui_controls.messagebox.askyesno') as ask:ChannelPanel.enable(panel)
        ask.assert_not_called();panel.app.command.assert_not_called()
    def test_optional_setpoint_confirmation_can_cancel(self):
        panel=self.panel(confirm_setpoints=True)
        with patch('ui_controls.messagebox.askyesno',return_value=False) as ask:ChannelPanel.apply_settings(panel)
        ask.assert_called_once();panel.app.command.assert_not_called()
    def test_no_setpoint_confirmation_keeps_explicit_apply(self):
        panel=self.panel(confirm_setpoints=False)
        with patch('ui_controls.messagebox.askyesno') as ask:ChannelPanel.apply_settings(panel)
        ask.assert_not_called();panel.app.command.assert_called_once_with('apply',1,5,.1)
    def stub_app(self,path,connected=False):
        settings=Preferences(resource='USB0::TEST::INSTR')
        return SimpleNamespace(connected=connected,connecting=False,user_settings=settings,preferences=path,
            resource=Var(settings.resource),demo=Var(False),applying_rate=Var('10 Hz'),time_base=Var('1 min'),
            log_interval=Var('Every sample'),change_log_interval=Mock(),live_edits=Mock(),refresh_controls=Mock(),worker=Mock(),note=Mock(),plots_dirty=False,set_minimal_ui=Mock())
    def test_saving_general_preferences_only_queues_mode_and_rate(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.stub_app(Path(tmp)/'preferences.json',True)
            settings=Preferences(resource=app.user_settings.resource,poll_rate=15,confirm_output=False)
            App.apply_preferences(app,settings)
            self.assertEqual([call.args for call in app.worker.post.call_args_list],[('instant_mode',False),('rate',15)])
            self.assertFalse(load_preferences(app.preferences).confirm_output)
    def test_enabling_live_mode_sends_no_setpoints(self):
        with tempfile.TemporaryDirectory() as tmp:
            app=self.stub_app(Path(tmp)/'preferences.json',True)
            settings=Preferences(resource=app.user_settings.resource,instant_mode=True)
            App.apply_preferences(app,settings)
            self.assertEqual([call.args for call in app.worker.post.call_args_list],[('instant_mode',True),('rate',10)])
            self.assertTrue(load_preferences(app.preferences).instant_mode)
            app.live_edits.cancel.assert_called_once()

    def test_changing_active_device_is_rejected_before_saving(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'preferences.json';app=self.stub_app(path,True)
            with self.assertRaises(ValueError):App.apply_preferences(app,Preferences(resource='USB0::OTHER::INSTR'))
            self.assertFalse(path.exists());app.worker.post.assert_not_called()
    def test_connection_options_reach_visa_resource(self):
        device=DemoDevice();device.resource_name='USB0::TEST::INSTR'
        manager=SimpleNamespace(open_resource=Mock(return_value=device),close=Mock())
        module=SimpleNamespace(ResourceManager=Mock(return_value=manager));events=queue.Queue();worker=Worker(events)
        try:
            with patch.dict(sys.modules,{'pyvisa':module}):
                worker.post('connect',device.resource_name,False,{'io_timeout_ms':2500,'usb_query_delay_ms':3})
                while True:
                    name,data=events.get(timeout=3)
                    if name=='error':self.fail(str(data))
                    if name=='snapshot':break
            self.assertEqual(device.timeout,2500);self.assertEqual(device.query_delay,.003)
            manager.open_resource.assert_called_once_with(device.resource_name,open_timeout=2500)
        finally:
            worker.post('disconnect')
            while events.get(timeout=3)[0]!='disconnected':pass

if __name__=='__main__':unittest.main()
