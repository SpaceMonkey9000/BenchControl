import sys
from pathlib import Path
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from instrument import PSU,DemoDevice
from sustained_benchmark import run_test,latency_summary

class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now

class SustainedTests(unittest.TestCase):
    def setup_test(self):
        clock=Clock();device=DemoDevice();device.commands=[]
        original_write=device.write;original_query=device.query
        def write(cmd):
            device.commands.append(cmd)
            if not cmd.startswith('INST CH'):raise AssertionError('Unexpected write: '+cmd)
            original_write(cmd)
        def query(cmd):
            clock.now+=.005
            return original_query(cmd)
        device.write=write;device.query=query
        return clock,device
    def test_exact_controller_scans_no_output_writes_and_periodic_settings(self):
        clock,device=self.setup_test()
        with patch('instrument.time.monotonic',clock):
            psu=PSU(device)
            result=run_test(psu,6,0,clock=clock)
        self.assertEqual(result['status'],'completed')
        self.assertGreater(result['normal_scans']['count'],0)
        self.assertGreaterEqual(result['settings_refresh_scans']['count'],3)
        self.assertTrue(all(cmd.startswith('INST CH') for cmd in device.commands))
        self.assertEqual(result['error_count'],0)
        self.assertEqual(device.settings,[[3.3,.1,False],[5,.2,False],[1.2,.1,False]])
        self.assertEqual(device.query_delay,0)
    def test_error_stops_and_retains_completed_scans(self):
        clock,device=self.setup_test()
        with patch('instrument.time.monotonic',clock):
            psu=PSU(device);snapshot=psu.snapshot;count=[0]
            def scan():
                count[0]+=1
                if count[0]==4:raise RuntimeError("Query 'MEAS:VOLT?' failed: timeout")
                return snapshot()
            psu.snapshot=scan
            result=run_test(psu,180,clock=clock)
        self.assertEqual(result['status'],'failed');self.assertEqual(result['scans_completed'],3)
        self.assertEqual(count[0],4);self.assertEqual(result['error_count'],1)
        self.assertIn('MEAS:VOLT?',result['error'])
    def test_interrupt_keeps_partial_report(self):
        clock,device=self.setup_test()
        with patch('instrument.time.monotonic',clock):
            psu=PSU(device);psu.snapshot=Mock(side_effect=KeyboardInterrupt)
            result=run_test(psu,180,clock=clock)
        self.assertEqual(result['status'],'interrupted');self.assertEqual(result['scans_completed'],0)
    def test_checkpoint_every_five_seconds(self):
        clock,device=self.setup_test();checkpoints=[]
        with patch('instrument.time.monotonic',clock):
            result=run_test(PSU(device),11,checkpoint=checkpoints.append,clock=clock)
        self.assertEqual(len(checkpoints),2)
        self.assertTrue(all(r['status']=='running' for r in checkpoints))
        self.assertEqual(result['status'],'completed')
    def test_latency_stats(self):
        stats=latency_summary([.01,.02,.03]);self.assertEqual(stats['count'],3)
        self.assertAlmostEqual(stats['mean_ms'],20)
        self.assertEqual(stats['p95_ms'],30)

if __name__=='__main__':unittest.main()
