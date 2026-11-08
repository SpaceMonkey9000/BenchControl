"""Acquisition timing independent from GUI rendering and CSV sampling."""
from datetime import datetime
import time

POLL_RATES = (1, 2, 5, 10, 15)
DEFAULT_POLL_RATE = 10
QUERY_DELAY_SECONDS = 0.0
COMPAT_QUERY_DELAY_SECONDS = .025
PLOT_INTERVAL_MS = 200


class ScanSample(list):
    """One completed three-channel scan, stamped before it reaches the UI queue."""
    def __init__(self, rows):
        super().__init__(rows)
        self.acquired_at = time.monotonic()
        self.timestamp = datetime.now().astimezone().isoformat(timespec='milliseconds')


def query_delay_for(resource_name):
    # Zero-delay sustained performance was established on this USBTMC path only.
    return QUERY_DELAY_SECONDS if resource_name.upper().startswith('USB') else COMPAT_QUERY_DELAY_SECONDS
