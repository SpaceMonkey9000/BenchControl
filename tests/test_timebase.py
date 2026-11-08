import sys
import unittest
from collections import deque
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from timebase import LogGate, plot_window, trim_history
from benchmark import measure
from instrument import DemoDevice, Channel
from ui_controls import draw_history
from unittest.mock import Mock

class TimingTests(unittest.TestCase):
    def test_fixed_timebase_does_not_expand_at_start(self):
        start,end,visible=plot_window([(100,[]),(101,[])],10)
        self.assertEqual((start,end),(91,101));self.assertEqual(len(visible),2)
    def test_filter_excludes_old_samples(self):
        _,_,visible=plot_window([(80,[]),(95,[]),(100,[])],10)
        self.assertEqual([v[0] for v in visible],[95,100])
    def test_all_retained(self):
        self.assertEqual(plot_window([(80,[]),(100,[])])[0],80)
    def test_empty_and_single_sample(self):
        self.assertEqual(plot_window([],60),(0,60,[]))
        self.assertEqual(plot_window([(3,[])])[:2],(2,3))
    def test_retention_trim(self):
        history=deque([(0,[]),(1000,[]),(4000,[])])
        trim_history(history,4000);self.assertEqual([v[0] for v in history],[1000,4000])
    def test_logging_interval_no_duplicate_or_catchup(self):
        gate=LogGate(1)
        self.assertTrue(gate.due(0));self.assertFalse(gate.due(.2));self.assertFalse(gate.due(.999))
        self.assertTrue(gate.due(1));self.assertTrue(gate.due(4))
        self.assertFalse(gate.due(4));self.assertFalse(gate.due(4.5));self.assertTrue(gate.due(5))
    def test_every_sample_and_interval_change(self):
        gate=LogGate()
        self.assertTrue(gate.due(1));self.assertTrue(gate.due(1.1))
        gate.reset(10);self.assertTrue(gate.due(2));self.assertFalse(gate.due(3))
    def test_slower_acquisition_only_logs_received_samples(self):
        gate=LogGate(.2)
        self.assertEqual([t for t in (1,2,3) if gate.due(t)],[1,2,3])
    def test_plot_fixed_window_has_time_axis(self):
        canvas=Mock();canvas.winfo_width.return_value=400;canvas.winfo_height.return_value=200
        rows=[Channel(1,5,.1,True,5,.1)]*3
        draw_history(canvas,[(100,rows),(101,rows)],0,'Voltage (V)',10)
        labels=[call.kwargs.get('text','') for call in canvas.create_text.call_args_list]
        self.assertTrue(any('10 s' in text for text in labels))
        self.assertIn('-10 s',labels);self.assertIn('0 s',labels)
    def test_plot_downsampling_preserves_current_peak(self):
        canvas=Mock();canvas.winfo_width.return_value=300;canvas.winfo_height.return_value=200
        samples=[]
        for n in range(2000):
            row=Channel(1,5,3 if n==1000 else .1,True,5,3)
            samples.append((n/2000,[row]*3))
        draw_history(canvas,samples,0,'Current (A)',1)
        trace=[call for call in canvas.create_line.call_args_list if call.kwargs.get('fill')=='#4dd8c2'][0]
        self.assertIn(32.0,trace.args[1::2])
        self.assertLess(len(trace.args),2*len(samples))
    def test_benchmark_sends_measurement_queries_only(self):
        d=DemoDevice();d.write=Mock(side_effect=AssertionError('Writes forbidden'))
        result=measure(d,3,0)
        d.write.assert_not_called();self.assertEqual(result['pairs_completed'],3)
    def test_benchmark_stops_first_failed_query(self):
        d=DemoDevice();d.query=Mock(side_effect=TimeoutError('timeout'))
        with self.assertRaisesRegex(RuntimeError,'MEAS:VOLT'):measure(d,10,0)
        self.assertEqual(d.query.call_count,1)

if __name__=='__main__':unittest.main()
