import json
import queue
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from model_profiles import get_profile,load_profile,profile_from_identity,PROFILES
from instrument import PSU,DemoDevice,Refused
from graph_scale import graph_top
from ui_controls import ChannelPanel
from app import App,Worker
from preferences import Preferences


class ModelProfileTests(unittest.TestCase):
    def test_profile_channel_limits(self):
        self.assertEqual(get_profile('9130B').channels,((30,3),(30,3),(5,3)))
        self.assertEqual(get_profile('9131B').channels,((30,6),(30,6),(5,3)))
        self.assertEqual(get_profile('9132B').channels,((60,3),(60,3),(5,3)))
    def test_identity_selects_exact_model_not_serial_or_partial_match(self):
        self.assertEqual(profile_from_identity('B&K Precision,9131B,123,1.0').model,'9131B')
        for identity in ('Other vendor,9131B,123,1','B&K Precision,9131B-extra,123,1','B&K Precision,9115,9131B,1','B&K Precision,9131C,123,1'):
            with self.assertRaises(ValueError):profile_from_identity(identity)
    def test_modified_capability_config_is_rejected(self):
        data=json.loads((Path(__file__).resolve().parents[1]/'profiles/9131B.json').read_text())
        data['channels'][2]['max_current_A']=6
        with patch('model_profiles.Path.read_text',return_value=json.dumps(data)):
            with self.assertRaises(ValueError):load_profile('9131B')
    def test_c_series_draft_configs_cannot_enable_control(self):
        for model in ('9130C','9131C','9132C'):
            path=Path(__file__).resolve().parents[1]/'profiles/drafts'/(model+'.json')
            self.assertFalse(json.loads(path.read_text())['enabled'])
            with self.assertRaises(ValueError):get_profile(model)
    def test_unknown_device_rejected_before_any_write(self):
        device=DemoDevice();query=device.query
        device.query=lambda cmd:'B&K Precision,9115,123,1' if cmd=='*IDN?' else query(cmd)
        device.write=Mock(wraps=device.write)
        with self.assertRaises(ValueError):PSU(device)
        device.write.assert_not_called()
    def test_each_profile_connect_snapshot_is_setpoint_and_output_read_only(self):
        for model in PROFILES:
            device=DemoDevice(model);device.write=Mock(wraps=device.write)
            psu=PSU(device);psu.independent();rows=psu.snapshot()
            self.assertEqual(psu.profile.model,model)
            self.assertTrue(all(c.args[0].startswith('INST CH') for c in device.write.call_args_list))
            self.assertEqual([(r.max_voltage,r.max_current) for r in rows],list(psu.profile.channels))
    def test_9131b_six_amp_manual_setting_keeps_ch3_three_amp_limit(self):
        psu=PSU(DemoDevice('9131B'));psu.apply(1,30,6)
        self.assertEqual(psu.device.settings[0],[30,6,False])
        with self.assertRaises(Refused):psu.apply(3,5,6)
        with self.assertRaises(Refused):psu.apply(1,30,6.001)
        with self.assertRaises(Refused):psu.apply(1,30.001,6)
    def test_9132b_live_sixty_volts_keeps_current_and_output(self):
        psu=PSU(DemoDevice('9132B'));psu.device.settings[0][2]=True
        psu.set_live(1,'voltage',60)
        self.assertEqual(psu.device.settings[0],[60,.1,True])
        with self.assertRaises(Refused):psu.set_live(1,'voltage',60.001)
        with self.assertRaises(Refused):psu.set_live(3,'voltage',5.001)
    def test_9130b_remains_limited_to_thirty_volts_three_amps(self):
        psu=PSU(DemoDevice())
        with self.assertRaises(Refused):psu.set_live(1,'current',3.001)
        with self.assertRaises(Refused):psu.set_live(1,'voltage',30.001)
    def test_enable_and_shutdown_use_each_models_full_range(self):
        for model in PROFILES:
            psu=PSU(DemoDevice(model));v,i=psu.profile.limits(1)
            psu.apply(1,v,i);psu.output(1,True,(v,i))
            self.assertTrue(psu.device.settings[0][2])
            psu.all_off()
            self.assertFalse(any(row[2] for row in psu.device.settings))
    def test_full_range_graph_uses_detected_profile(self):
        row=PSU(DemoDevice('9131B')).snapshot()[0]
        self.assertEqual(graph_top(0,'Current (A)',row,'Full range'),6)
        row=PSU(DemoDevice('9132B')).snapshot()[0]
        self.assertEqual(graph_top(0,'Voltage (V)',row,'Full range'),60)
    def test_editor_digit_limits_use_profile(self):
        panel=SimpleNamespace(number=1,ve=SimpleNamespace(maximum=0),ie=SimpleNamespace(maximum=0))
        ChannelPanel.configure_profile(panel,get_profile('9131B'))
        self.assertEqual((panel.ve.maximum,panel.ie.maximum),(30,6))
        ChannelPanel.configure_profile(panel,get_profile('9132B'))
        self.assertEqual((panel.ve.maximum,panel.ie.maximum),(60,3))
    def test_typed_values_use_detected_profile(self):
        var=lambda v:SimpleNamespace(get=lambda:v)
        panel=SimpleNamespace(number=1,app=SimpleNamespace(device_profile=get_profile('9131B')),v=var('30'),i=var('6'))
        self.assertEqual(ChannelPanel.values(panel),(30,6))
        panel.app.device_profile=get_profile('9130B')
        with self.assertRaises(ValueError):ChannelPanel.values(panel)
    def test_instant_submit_uses_detected_profile(self):
        panel=SimpleNamespace(reading=Mock(),v=SimpleNamespace(get=lambda:'50'))
        app=SimpleNamespace(connected=True,busy=False,user_settings=Preferences(instant_mode=True),device_profile=get_profile('9132B'),panels=[panel],worker=Mock(),note=Mock())
        App.submit_live(app,1,'voltage');app.worker.post.assert_called_once_with('set_live',1,'voltage',50.)
        app.worker.post.reset_mock();app.device_profile=get_profile('9130B')
        App.submit_live(app,1,'voltage');app.worker.post.assert_not_called()
    def test_cross_model_preset_is_refused_without_changing_drafts(self):
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'preset.json'
            path.write_text(json.dumps({'model':'9132B','channels':[{'channel':i,'voltage':5,'current':.1} for i in (1,2,3)]}))
            panels=[SimpleNamespace(v=Mock(),i=Mock()) for _ in range(3)]
            app=SimpleNamespace(live_edits=Mock(),device_profile=get_profile('9130B'),panels=panels)
            with patch('app.filedialog.askopenfilename',return_value=str(path)),patch('app.messagebox.showerror') as error:
                App.load_settings(app)
            error.assert_called_once()
            for p in panels:p.v.set.assert_not_called();p.i.set.assert_not_called()
    def test_worker_demo_model_is_explicit_and_detected(self):
        events=queue.Queue();worker=Worker(events)
        try:
            worker.post('connect','',True,{'demo_model':'9132B'})
            while True:
                kind,data=events.get(timeout=3)
                if kind=='error':self.fail(str(data))
                if kind=='snapshot':break
            self.assertEqual(worker.psu.profile.model,'9132B')
            self.assertEqual(data[0].max_voltage,60)
        finally:worker.post('disconnect')
