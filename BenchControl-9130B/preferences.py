"""Validated local application preferences, separate from PSU setpoint profiles."""
from dataclasses import dataclass, asdict, fields
import json
import math
import os
from pathlib import Path
from model_profiles import get_profile
from acquisition import POLL_RATES, DEFAULT_POLL_RATE
from timebase import TIME_BASES, LOG_INTERVALS


@dataclass
class Preferences:
    resource: str = ''
    demo: bool = False
    demo_model: str = '9130B'
    minimal_ui: bool = False
    instant_mode: bool = False
    instant_delay_ms: int = 750
    poll_rate: int = DEFAULT_POLL_RATE
    confirm_output: bool = True
    confirm_setpoints: bool = False
    io_timeout_ms: int = 1500
    usb_query_delay_ms: float = 0.0
    graph_timebase: str = '1 min'
    log_interval: str = 'Every sample'

    def validate(self):
        if not isinstance(self.resource,str) or len(self.resource)>2048 or '\n' in self.resource or '\r' in self.resource:
            raise ValueError('Invalid VISA resource address')
        if not isinstance(self.demo_model,str):raise ValueError('Invalid demo model')
        get_profile(self.demo_model)
        for name in ('demo','minimal_ui','instant_mode','confirm_output','confirm_setpoints'):
            if type(getattr(self,name)) is not bool:raise ValueError(name+' must be true or false')
        if type(self.instant_delay_ms) is not int or not 100<=self.instant_delay_ms<=3000:
            raise ValueError('Instant edit delay must be 100–3000 ms')
        if type(self.poll_rate) is not int or self.poll_rate not in POLL_RATES:raise ValueError('Choose a supported refresh rate')
        if type(self.io_timeout_ms) is not int or not 500<=self.io_timeout_ms<=10000:raise ValueError('I/O timeout must be 500–10000 ms')
        if type(self.usb_query_delay_ms) not in (int,float) or not math.isfinite(self.usb_query_delay_ms) or not 0<=self.usb_query_delay_ms<=100:
            raise ValueError('USB query delay must be 0–100 ms')
        if self.graph_timebase not in TIME_BASES:raise ValueError('Invalid graph time base')
        if self.log_interval not in LOG_INTERVALS:raise ValueError('Invalid CSV interval')
        return self

    def connection_key(self):return self.resource.strip(),self.demo,self.demo_model,self.io_timeout_ms,self.usb_query_delay_ms
    def connection_options(self):return {'demo_model':self.demo_model,'io_timeout_ms':self.io_timeout_ms,'usb_query_delay_ms':self.usb_query_delay_ms}


def preferences_path():
    """%LOCALAPPDATA%\\BenchControl9130B\\preferences.json, honouring redirected profiles."""
    base=os.environ.get('LOCALAPPDATA')
    root=Path(base) if base else Path.home()/'AppData'/'Local'
    return root/'BenchControl9130B'/'preferences.json'


def load_preferences(path):
    defaults=Preferences()
    try:data=json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError,ValueError):return defaults
    if not isinstance(data,dict):return defaults
    # Preserve valid legacy resource-only files, and recover each bad field independently.
    values=asdict(defaults)
    for field in fields(Preferences):
        if field.name not in data:continue
        candidate=dict(values);candidate[field.name]=data[field.name]
        try:Preferences(**candidate).validate()
        except (ValueError,TypeError):continue
        values=candidate
    return Preferences(**values)


def save_preferences(path,preferences):
    preferences.validate()
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(asdict(preferences),indent=2),encoding='utf-8')
    temporary.replace(path)
