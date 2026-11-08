import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from instrument import PSU, DemoDevice, Channel, PollInterrupted
from app import ChannelPanel

class MonitoringTests(unittest.TestCase):
    def setUp(self):
        self.device=DemoDevice();self.psu=PSU(self.device)
    def test_warning_independent_for_each_channel(self):
        self.device.settings[1][2]=True;self.device.limited_channels={2}
        rows=self.psu.snapshot()
        self.assertEqual([r.current_limited for r in rows],[False,True,False])
        self.assertEqual(rows[1].current,.2)
        self.assertLess(rows[1].voltage,rows[1].set_voltage)
    def test_off_channel_does_not_show_warning(self):
        self.device.limited_channels={1}
        self.assertFalse(self.psu.snapshot()[0].current_limited)
    def test_legacy_queries_only_and_settings_cache(self):
        original=self.device.query
        allowed={'MEAS:VOLT?','MEAS:CURR?','CHAN:OUTP?','VOLT?','CURR?','SYST:ERR?'}
        def query(cmd):
            if cmd not in allowed:raise TimeoutError('Unsupported '+cmd)
            return original(cmd)
        self.device.query=Mock(side_effect=query)
        self.psu.snapshot();first=self.device.query.call_count
        self.psu.snapshot();second=self.device.query.call_count-first
        self.assertEqual(first,16);self.assertEqual(second,9)
    def test_forced_settings_refresh(self):
        self.psu.snapshot();self.device.settings[0][0]=7
        self.assertEqual(self.psu.snapshot()[0].set_voltage,3.3)
        self.assertEqual(self.psu.snapshot(force=True)[0].set_voltage,7)
    def test_control_interrupts_between_queries(self):
        calls=[];original=self.device.query
        def query(cmd):calls.append(cmd);return original(cmd)
        self.device.query=query
        with self.assertRaises(PollInterrupted):self.psu.snapshot(interrupt=lambda:len(calls)>=1)
        self.assertEqual(calls,['MEAS:VOLT?'])
    def test_nonfinite_reading_rejected(self):
        original=self.device.query
        self.device.query=lambda cmd:'nan' if cmd=='MEAS:VOLT?' else original(cmd)
        with self.assertRaises(RuntimeError):self.psu.snapshot()
    def test_error_identifies_failing_command(self):
        self.device.query=Mock(side_effect=TimeoutError('timeout'))
        with self.assertRaisesRegex(RuntimeError,'MEAS:VOLT'):
            self.psu.snapshot()
    def test_zero_limit_does_not_flag_zero_measurement(self):
        self.device.settings[0]=[5,0,True]
        self.assertFalse(self.psu.snapshot()[0].current_limited)
    def panel_stub(self):
        return SimpleNamespace(reading=None,alert_until=0,state=Mock(),vmeter=Mock(),imeter=Mock(),update_dirty=Mock(),power=Mock(),applied=Mock(),v=Mock(),i=Mock(),set_palette=Mock(),after=Mock())
    def test_panel_red_hold_then_clear(self):
        panel=self.panel_stub()
        with patch('app.time.monotonic',return_value=10):ChannelPanel.update_reading(panel,Channel(1,.01,.1,True,5,.1,True))
        panel.set_palette.assert_called_with(True)
        panel.state.configure.assert_called_with(text='OUTPUT ON',bg='#16804a',fg='#ffffff')
        with patch('app.time.monotonic',return_value=10.25):ChannelPanel.update_reading(panel,Channel(1,5,.02,True,5,.1,False))
        panel.set_palette.assert_called_with(True)
        with patch('app.time.monotonic',return_value=10.5):ChannelPanel.update_reading(panel,Channel(1,5,.02,True,5,.1,False))
        panel.set_palette.assert_called_with(False)
    def test_first_reading_initializes_drafts_without_apply(self):
        panel=self.panel_stub()
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,5.1,.5))
        panel.v.set.assert_called_once_with('5.100')
        panel.i.set.assert_called_once_with('0.500')
        panel.v.reset_mock();panel.i.reset_mock()
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,6,.6))
        panel.v.set.assert_not_called();panel.i.set.assert_not_called()
    def test_shared_detail_does_not_overwrite_existing_drafts(self):
        panel=self.panel_stub();panel.initialize_drafts=False
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,5,.5))
        panel.v.set.assert_not_called();panel.i.set.assert_not_called()
    def test_output_becomes_available_on_first_off_reading(self):
        panel=SimpleNamespace(reading=None,last_controls=None,app=SimpleNamespace(user_settings=SimpleNamespace(instant_mode=False)),ve=Mock(),ie=Mock(),apply=Mock(),output_toggle=Mock())
        ChannelPanel.controls(panel,True,False)
        panel.output_toggle.configure.assert_called_with(text='Output ON',state='disabled',style='TButton')
        panel.reading=Channel(1,0,0,False,5,.5)
        ChannelPanel.controls(panel,True,False)
        panel.output_toggle.configure.assert_called_with(text='Output ON',state='normal',style='TButton')
    def test_hold_clears_without_waiting_for_another_scan(self):
        panel=self.panel_stub();panel.alert_until=10.5
        row=Channel(1,5,.02,True,5,.1,False);panel.reading=row
        with patch('ui_controls.time.monotonic',return_value=10.5):ChannelPanel.clear_alert(panel,row)
        panel.set_palette.assert_called_with(False)
        panel.state.configure.assert_called_with(text='OUTPUT ON',bg='#16804a',fg='#ffffff')
        panel.set_palette.reset_mock();panel.reading=None
        ChannelPanel.clear_alert(panel,row)
        panel.set_palette.assert_not_called()

    def test_off_clears_red_without_hold(self):
        panel=self.panel_stub();panel.alert_until=100
        ChannelPanel.update_reading(panel,Channel(1,0,0,False,5,.1,False))
        panel.set_palette.assert_called_with(False)
    def test_unchanged_controls_not_reconfigured(self):
        panel=SimpleNamespace(reading=Channel(1,0,0,False,5,.1),last_controls=None,app=SimpleNamespace(user_settings=SimpleNamespace(instant_mode=False)),ve=Mock(),ie=Mock(),apply=Mock(),output_toggle=Mock())
        ChannelPanel.controls(panel,True,False);panel.ve.reset_mock()
        ChannelPanel.controls(panel,True,False);panel.ve.configure.assert_not_called()

if __name__=='__main__':unittest.main()
