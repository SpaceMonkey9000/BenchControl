import queue
import sys
import time
from pathlib import Path
from collections import deque
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from acquisition import ScanSample,POLL_RATES,DEFAULT_POLL_RATE,QUERY_DELAY_SECONDS,PLOT_INTERVAL_MS,query_delay_for
from app import Worker,App
from instrument import DemoDevice,Channel
from timebase import MAX_SAMPLES,LogGate

class SpeedTests(unittest.TestCase):
    def rows(self):return [Channel(ch,1,.1,True,1,.2) for ch in (1,2,3)]
    def event(self,events,kind):
        deadline=time.monotonic()+3
        while time.monotonic()<deadline:
            name,data=events.get(timeout=3)
            if name=='error':self.fail(str(data))
            if name==kind:return data
        self.fail('No '+kind+' event')
    def test_timing_defaults_and_retention(self):
        self.assertEqual(DEFAULT_POLL_RATE,10);self.assertEqual(QUERY_DELAY_SECONDS,0)
        self.assertEqual(POLL_RATES,(1,2,5,10,15))
        self.assertGreaterEqual(MAX_SAMPLES,15*3600)
    def test_zero_delay_only_for_verified_usb_path(self):
        self.assertEqual(query_delay_for('USB0::TEST::INSTR'),0)
        self.assertEqual(query_delay_for('GPIB0::1::INSTR'),.025)
        self.assertEqual(query_delay_for('ASRL1::INSTR'),.025)
    def test_timestamp_and_list_compatibility(self):
        with patch('acquisition.time.monotonic',return_value=123.4):sample=ScanSample(self.rows())
        self.assertEqual(sample.acquired_at,123.4);self.assertEqual(len(sample),3)
        self.assertIn('T',sample.timestamp)
    def test_real_connection_path_sets_zero_delay_without_output_programming(self):
        device=DemoDevice();device.resource_name='USB0::TEST::INSTR'
        original_write=device.write;device.write=Mock(wraps=original_write)
        manager=SimpleNamespace(open_resource=Mock(return_value=device),close=Mock())
        module=SimpleNamespace(ResourceManager=Mock(return_value=manager))
        events=queue.Queue();worker=Worker(events)
        try:
            with patch.dict(sys.modules,{'pyvisa':module}):
                worker.post('connect','USB0::TEST::INSTR',False)
                self.event(events,'connected');sample=self.event(events,'snapshot')
            self.assertEqual(device.query_delay,0)
            self.assertIsInstance(sample,ScanSample)
            self.assertTrue(all(call.args[0].startswith('INST CH') for call in device.write.call_args_list))
        finally:
            worker.post('disconnect');self.event(events,'disconnected')
    def test_worker_accepts_fifteen_hz(self):
        events=queue.Queue();worker=Worker(events)
        try:
            worker.post('connect','',True);self.event(events,'connected');self.event(events,'snapshot')
            worker.post('rate',15);self.event(events,'snapshot')
            self.assertAlmostEqual(worker.poll_interval,1/15)
        finally:
            worker.post('disconnect');self.event(events,'disconnected')
    def app_stub(self):
        return SimpleNamespace(events=queue.Queue(),panels=[Mock() for _ in range(3)],stats=[Mock() for _ in range(3)],details={},first=False,
            demo=SimpleNamespace(get=lambda:False),process_events=Mock(),last_sample_at=None,smoothed_interval=None,rate_label=Mock(),history=deque(maxlen=MAX_SAMPLES),plots_dirty=False,
            writer=Mock(),logfile=Mock(),log_started_at=0,log_gate=LogGate(),refresh_controls=Mock(),after=Mock(),draw_plot=Mock())
    def test_ui_keeps_acquisition_time_and_does_not_render_per_sample(self):
        app=self.app_stub();sample=ScanSample(self.rows());sample.acquired_at=12.3;sample.timestamp='captured-before-queue'
        app.events.put(('snapshot',sample));App.process_events(app)
        self.assertEqual(app.history[0][0],12.3)
        self.assertEqual(app.writer.writerow.call_args_list[0].args[0][0],'captured-before-queue')
        self.assertTrue(app.plots_dirty);app.draw_plot.assert_not_called()
    def test_graphs_throttled_without_dropping_csv_samples(self):
        app=self.app_stub()
        for n in range(20):
            sample=ScanSample(self.rows());sample.acquired_at=100+n*.1
            app.events.put(('snapshot',sample))
        while not app.events.empty():App.process_events(app)
        self.assertEqual(len(app.history),20);self.assertEqual(app.writer.writerow.call_count,60)
        app.draw_plot.assert_not_called()
        detail=Mock();app.details={1:detail}
        app.refresh_plots=lambda:App.refresh_plots(app)
        App.refresh_plots(app);App.refresh_plots(app)
        self.assertEqual(app.draw_plot.call_count,1);self.assertEqual(detail.redraw.call_count,1)
        app.after.assert_called_with(PLOT_INTERVAL_MS,app.refresh_plots)
    def test_samples_queued_before_log_start_are_not_logged(self):
        app=self.app_stub();app.log_started_at=100
        sample=ScanSample(self.rows());sample.acquired_at=99
        app.events.put(('snapshot',sample));App.process_events(app)
        app.writer.writerow.assert_not_called();self.assertEqual(len(app.history),1)

if __name__=='__main__':unittest.main()
