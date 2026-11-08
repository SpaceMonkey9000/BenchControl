import sys
from pathlib import Path
import unittest
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from graph_scale import graph_top,positive_scale
from instrument import Channel
from ui_controls import draw_history

class ScaleTests(unittest.TestCase):
    def test_current_limit_with_headroom(self):
        row=Channel(1,5,.2,True,5,.5)
        self.assertAlmostEqual(graph_top(0,'Current (A)',row),.55)
    def test_voltage_setpoint_with_headroom(self):
        row=Channel(1,5,.2,True,5.1,.5)
        self.assertAlmostEqual(graph_top(0,'Voltage (V)',row),5.61)
    def test_zero_or_missing_limit_falls_back_to_full_range(self):
        row=Channel(3,0,0,False,0,0)
        self.assertEqual(graph_top(2,'Voltage (V)',row),5)
        self.assertEqual(graph_top(2,'Current (A)',row),3)
        self.assertEqual(graph_top(0,'Voltage (V)'),30)
    def test_full_range_ignores_small_setpoint(self):
        row=Channel(1,0,0,False,1,.1)
        self.assertEqual(graph_top(0,'Current (A)',row,'Full range'),3)
        self.assertEqual(graph_top(0,'Voltage (V)',row,'Full range'),30)
    def test_manual_scale_does_not_mutate_channel(self):
        row=Channel(1,1,.1,True,5,.5)
        before=row.__dict__.copy()
        self.assertEqual(graph_top(0,'Current (A)',row,'Manual',.2),.2)
        self.assertEqual(row.__dict__,before)
    def test_invalid_manual_scales_rejected(self):
        for value in (0,-1,float('inf'),float('nan'),'bad',None):
            with self.assertRaises(ValueError):positive_scale(value)
    def test_out_of_scale_samples_are_marked_and_raw_values_kept(self):
        canvas=Mock();canvas.winfo_width.return_value=400;canvas.winfo_height.return_value=200
        row=Channel(1,5,1,True,5,.5);history=[(0,[row]*3),(1,[row]*3)]
        draw_history(canvas,history,0,'Current (A)',10,'Channel limits')
        labels=[call.kwargs.get('text','') for call in canvas.create_text.call_args_list]
        self.assertTrue(any('clipped' in label for label in labels))
        self.assertEqual(row.current,1)
    def test_manual_axis_changes_plot_coordinates(self):
        canvas=Mock();canvas.winfo_width.return_value=400;canvas.winfo_height.return_value=200
        row=Channel(1,5,.1,True,5,.5)
        draw_history(canvas,[(0,[row]*3),(1,[row]*3)],0,'Current (A)',10,'Manual',.2)
        trace=[call for call in canvas.create_line.call_args_list if call.kwargs.get('fill')=='#4dd8c2'][0]
        self.assertAlmostEqual(trace.args[1],105)

if __name__=='__main__':unittest.main()
