import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from app import App
from preferences import Preferences
from channel_split import channel_height


class LayoutTests(unittest.TestCase):
    def app(self):
        split=Mock();split.sash_coord.return_value=(0,510)
        channels=Mock();channels.winfo_reqheight.return_value=480
        toolbar=Mock();toolbar.winfo_reqheight.return_value=50
        return SimpleNamespace(main_split=split,channel_area=channels,graph_area=Mock(),
            graph_visible=True,saved_sash_y=None,pack_slaves=lambda:[split,toolbar],
            minsize=Mock(),invalidate_plot=Mock(),after_idle=Mock(),update_idletasks=Mock())

    def test_minimal_hides_graph_and_allows_compact_window(self):
        app=self.app()
        App.set_minimal_ui(app,True)
        app.main_split.forget.assert_called_once_with(app.graph_area)
        self.assertFalse(app.graph_visible);self.assertEqual(app.saved_sash_y,510)
        app.minsize.assert_called_with(1080,530)
        App.set_minimal_ui(app,True)
        app.main_split.forget.assert_called_once()

    def test_restoring_graph_restores_sash_and_full_minimum(self):
        app=self.app();App.set_minimal_ui(app,True)
        App.set_minimal_ui(app,False)
        self.assertTrue(app.graph_visible)
        app.main_split.add.assert_called_once_with(app.graph_area,minsize=200,stretch='always')
        app.minsize.assert_called_with(1080,736)
        app.after_idle.call_args.args[0]()
        app.main_split.sash_place.assert_called_with(0,0,510)

    def test_initial_sash_cannot_compress_channel_content(self):
        app=self.app();app.main_split.winfo_height.return_value=700
        app.user_settings=Preferences();app.set_minimal_ui=Mock()
        App.initialize_layout(app)
        app.main_split.paneconfigure.assert_called_once_with(app.channel_area,minsize=480)
        app.main_split.sash_place.assert_called_once_with(0,0,480)

    def test_resize_marks_dirty_without_immediate_redraw(self):
        app=SimpleNamespace(plots_dirty=False,draw_plot=Mock())
        App.invalidate_plot(app)
        self.assertTrue(app.plots_dirty);app.draw_plot.assert_not_called()

    def test_hidden_graph_is_not_drawn(self):
        App.draw_plot(SimpleNamespace(graph_visible=False))

    def test_divider_bounds_preserve_complete_channel_height(self):
        for wanted in (-100,0,100,600,2000):
            height=channel_height(wanted,480,900)
            self.assertGreaterEqual(height,480)
            self.assertLessEqual(height,694)
        # Even an undersized parent cannot force the top row below its content.
        self.assertEqual(channel_height(10,480,200),480)

    def test_minimal_setting_requires_boolean(self):
        self.assertFalse(Preferences().minimal_ui)
        with self.assertRaises(ValueError):Preferences(minimal_ui='true').validate()


if __name__=='__main__':unittest.main()
