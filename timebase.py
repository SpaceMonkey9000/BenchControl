"""Plot windows and CSV timing are independent of instrument acquisition."""
from dataclasses import dataclass

TIME_BASES = {'10 s':10., '30 s':30., '1 min':60., '5 min':300., '15 min':900., '1 h':3600., 'All retained':None}
LOG_INTERVALS = {'Every sample':0., '0.2 s':.2, '0.5 s':.5, '1 s':1., '2 s':2., '5 s':5., '10 s':10., '30 s':30., '60 s':60.}
RETENTION_SECONDS = 3600.
MAX_SAMPLES = 60000


def trim_history(history, now):
    cutoff = now-RETENTION_SECONDS
    while history and history[0][0] < cutoff:history.popleft()


def plot_window(history, seconds=None):
    if not history:return 0.,max(seconds or 1.,1.),[]
    end=history[-1][0]
    if seconds is None:
        return min(history[0][0],end-1.),end,list(history)
    start=end-seconds
    visible=[]
    # Walk newest-to-oldest so a short window need not scan an hour of data.
    for sample in reversed(history):
        if sample[0]<start:break
        visible.append(sample)
    visible.reverse()
    return start,end,visible


@dataclass
class LogGate:
    interval: float = 0.
    last_written: float | None = None

    def reset(self, interval=None):
        if interval is not None:
            if interval<0:raise ValueError('Logging interval must not be negative')
            self.interval=interval
        self.last_written=None

    def due(self, now):
        if self.last_written is None or now-self.last_written+1e-9 >= self.interval:
            self.last_written=now
            return True
        return False
