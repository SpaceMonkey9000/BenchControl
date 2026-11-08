import unittest
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from instrument import PSU, DemoDevice, validate

class Recorder(DemoDevice):
    def __init__(self): super().__init__();self.commands=[];self.mode=False;self.idn=None;self.error='0,"No error"';self.ignore_voltage=False
    def write(self,cmd):
        self.commands.append(cmd)
        if not (self.ignore_voltage and cmd.startswith('VOLT ')):super().write(cmd)
    def query(self,cmd):
        if cmd=='*IDN?' and self.idn:return self.idn
        if cmd=='OUTP:SER?' and self.mode:return '1'
        if cmd=='SYST:ERR?':return self.error
        return super().query(cmd)

class SafetyTests(unittest.TestCase):
    def setUp(self):self.d=Recorder();self.p=PSU(self.d)
    def test_connection_is_read_only(self):
        self.p.independent();self.p.snapshot()
        self.assertTrue(all(c.startswith('INST ') for c in self.d.commands))
    def test_wrong_instrument(self):
        self.d.idn='Keysight Technologies,34461A,1,1'
        with self.assertRaises(ValueError):PSU(self.d)
        self.assertEqual(self.d.commands,[])
    def test_limits_and_nan_rejected_without_writes(self):
        for args in [(3,5.1,1),(1,31,1),(2,1,3.1),(0,1,1),(1,float('nan'),1),(1,1,float('inf')),(1,-1,1)]:
            with self.assertRaises(ValueError):self.p.apply(*args)
        self.assertEqual(self.d.commands,[])
    def test_live_output_cannot_be_reprogrammed(self):
        self.d.settings[0][2]=True
        with self.assertRaises(RuntimeError):self.p.apply(1,5,.1)
        self.assertFalse(any(c.startswith(('CURR ','VOLT ')) for c in self.d.commands))
    def test_current_limit_before_voltage(self):
        self.p.apply(2,12,.5)
        self.assertLess(self.d.commands.index('CURR 0.500'),self.d.commands.index('VOLT 12.000'))
        self.assertFalse(self.d.settings[1][2])
    def test_combined_mode_blocks_programming(self):
        self.d.mode=True
        with self.assertRaises(RuntimeError):self.p.apply(1,5,.1)
        self.assertEqual(self.d.commands,[])
    def test_enable_rechecks_settings(self):
        with self.assertRaises(RuntimeError):self.p.output(1,True,(5,.1))
        self.assertFalse(self.d.settings[0][2])
    def test_enable_and_all_off(self):
        self.p.output(1,True,(3.3,.1))
        self.assertTrue(self.d.settings[0][2])
        self.d.settings[1][2]=True
        self.p.all_off()
        self.assertFalse(any(s[2] for s in self.d.settings))
    def test_all_off_uses_channel_commands_and_preserves_setpoints(self):
        before=[row[:2] for row in self.d.settings]
        for row in self.d.settings:row[2]=True
        self.p.all_off()
        self.assertEqual(self.d.commands,['INST CH1','CHAN:OUTP OFF','INST CH2','CHAN:OUTP OFF','INST CH3','CHAN:OUTP OFF','INST CH1','INST CH2','INST CH3'])
        self.assertEqual([row[:2] for row in self.d.settings],before)
    def test_all_off_rejects_stuck_channel_after_switching_others_off(self):
        for row in self.d.settings:row[2]=True
        write=self.d.write
        def stuck(cmd):
            if self.d.ch==2 and cmd=='CHAN:OUTP OFF':return
            write(cmd)
        self.d.write=stuck
        with self.assertRaisesRegex(RuntimeError,'All-off NOT confirmed'):self.p.all_off()
        self.assertEqual([row[2] for row in self.d.settings],[False,True,False])
    def test_all_off_sends_every_off_before_first_readback_failure(self):
        for row in self.d.settings:row[2]=True
        query=self.d.query
        def failed(cmd):
            if cmd=='CHAN:OUTP?':raise RuntimeError('timeout')
            return query(cmd)
        self.d.query=failed
        with self.assertRaisesRegex(RuntimeError,'timeout'):self.p.all_off()
        self.assertFalse(any(row[2] for row in self.d.settings))
    def test_setpoint_mismatch_detected(self):
        self.d.ignore_voltage=True
        with self.assertRaises(RuntimeError):self.p.apply(1,12,.1)
    def test_instrument_error_blocks_writes(self):
        self.d.error='-200,"Execution error"'
        with self.assertRaises(RuntimeError):self.p.apply(1,5,.1)
        self.assertEqual(self.d.commands,[])

if __name__=='__main__':unittest.main()
