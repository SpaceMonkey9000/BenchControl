import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from instrument import Channel
from ui_controls import digit_step, is_dirty, Stats, ChannelPanel, DigitEntry, channel_state

class EditingTests(unittest.TestCase):
    def test_selected_digit_steps(self):
        self.assertEqual(digit_step('3.300',0,1,30)[0],'4.300')
        self.assertEqual(digit_step('3.300',2,1,30)[0],'3.400')
        self.assertEqual(digit_step('3.300',3,1,30)[0],'3.310')
        self.assertEqual(digit_step('3.300',4,1,30)[0],'3.301')
    def test_step_carry_keeps_same_decimal_place(self):
        value,index=digit_step('9.900',2,1,30)
        self.assertEqual((value,index),('10.000',3))
    def test_bounds(self):
        self.assertEqual(digit_step('5.000',0,1,5)[0],'5.000')
        self.assertEqual(digit_step('0.000',4,-1,5)[0],'0.000')
        self.assertEqual(digit_step('29.000',0,1,30)[0],'30.000')
    def test_end_caret_selects_last_digit(self):
        self.assertEqual(digit_step('1.200',5,1,30),('1.201',4))
    def test_dirty_invalid_and_unapplied_values(self):
        r=Channel(1,0,0,False,3.3,.1)
        self.assertFalse(is_dirty('3.300','.100',r))
        for value in ('','bad','nan','inf','3.301'):
            self.assertTrue(is_dirty(value,'.100',r))
        self.assertFalse(is_dirty('5','1',None))
    def test_current_limit_no_short_claim(self):
        state,red,_=channel_state(Channel(1,.01,.1,True,5,.1,True),0,10)
        self.assertTrue(red);self.assertEqual(state,'OUTPUT ON')
    def test_statistics(self):
        stats=Stats();self.assertEqual(stats.text(),'No samples')
        stats.add(Channel(1,2,.1,True,2,.1))
        stats.add(Channel(1,4,.2,True,4,.2))
        self.assertEqual(stats.minimum,(2,.1,.2))
        self.assertEqual(stats.maximum,(4,.2,.8))
        self.assertIn('Average',stats.text());self.assertEqual(stats.count,2)
    def test_apply_never_changes_live_channel(self):
        app=SimpleNamespace(connected=True,busy=False,command=Mock())
        panel=SimpleNamespace(app=app,reading=Channel(1,5,.1,True,5,.1),number=1,values=Mock())
        with patch('ui_controls.messagebox.showerror'):
            ChannelPanel.apply_settings(panel)
        app.command.assert_not_called();panel.values.assert_not_called()
    def test_apply_normalizes_and_uses_existing_command(self):
        app=SimpleNamespace(connected=True,busy=False,command=Mock())
        panel=SimpleNamespace(app=app,reading=Channel(1,0,0,False,5,.1),number=1,values=lambda:(3.3,.1),v=Mock(),i=Mock())
        ChannelPanel.apply_settings(panel)
        app.command.assert_called_once_with('apply',1,3.3,.1)
        panel.v.set.assert_called_with('3.300')
    def test_enable_rejects_pending_edits(self):
        app=SimpleNamespace(connected=True,busy=False,command=Mock())
        v,i=Mock(),Mock();v.get.return_value='6.000';i.get.return_value='.100'
        panel=SimpleNamespace(app=app,reading=Channel(1,0,0,False,5,.1),number=1,values=lambda:(6,.1),v=v,i=i)
        with patch('ui_controls.messagebox.showerror'),patch('ui_controls.messagebox.askyesno') as confirm:
            ChannelPanel.enable(panel)
        app.command.assert_not_called();confirm.assert_not_called()
    def test_wheel_without_focus_does_not_edit(self):
        panel=SimpleNamespace(focus_get=lambda:object(),step=Mock())
        self.assertIsNone(DigitEntry.wheel(panel,SimpleNamespace(delta=120)))
        panel.step.assert_not_called()
    def test_enter_blocked_for_disabled_entry(self):
        entry=SimpleNamespace(state=lambda:('disabled',),commit=Mock())
        self.assertEqual(DigitEntry.enter(entry),'break');entry.commit.assert_not_called()

if __name__=='__main__':unittest.main()
