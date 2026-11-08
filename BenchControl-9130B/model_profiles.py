"""Vetted 9130B-family capabilities, loaded from bundled JSON profiles."""
import json
import math
from dataclasses import dataclass
from pathlib import Path

# Adding a different command family requires a driver, not a JSON override.
APPROVED_LIMITS={
    '9130B':((30,3),(30,3),(5,3)),
    '9131B':((30,6),(30,6),(5,3)),
    '9132B':((60,3),(60,3),(5,3)),
}


@dataclass(frozen=True)
class ModelProfile:
    model: str
    channels: tuple

    def limits(self,ch):
        if type(ch) is not int or ch not in (1,2,3):raise ValueError('Channel must be 1, 2 or 3')
        return self.channels[ch-1]

    def validate(self,ch,volts,amps):
        maximum_v,maximum_i=self.limits(ch)
        if not all(math.isfinite(x) for x in (volts,amps)):raise ValueError('Settings must be finite numbers')
        if not 0<=volts<=maximum_v or not 0<=amps<=maximum_i:
            raise ValueError(f'{self.model} CH{ch}: 0–{maximum_v:g} V, 0–{maximum_i:g} A')

    def description(self):
        return f'B&K Precision {self.model}\n'+'\n'.join(f'CH{ch}: 0–{v:g} V, 0–{i:g} A' for ch,(v,i) in enumerate(self.channels,1))


def load_profile(model):
    if model not in APPROVED_LIMITS:
        raise ValueError(f'No enabled driver profile for {model}. Enabled models: '+', '.join(APPROVED_LIMITS))
    path=Path(__file__).with_name('profiles')/(model+'.json')
    data=json.loads(path.read_text(encoding='utf-8'))
    limits=tuple((row['max_voltage_V'],row['max_current_A']) for row in data['channels'])
    if (data.get('model')!=model or data.get('driver')!='bk9130b' or data.get('enabled') is not True
        or limits!=APPROVED_LIMITS[model] or [row['channel'] for row in data['channels']]!=[1,2,3]):
        raise ValueError('Invalid or modified capability profile: '+model)
    return ModelProfile(model,limits)


PROFILES={model:load_profile(model) for model in APPROVED_LIMITS}
DEFAULT_PROFILE=PROFILES['9130B']


def get_profile(model):
    model=model.strip().upper()
    if model not in PROFILES:
        raise ValueError(f'No enabled driver profile for {model}. Enabled models: '+', '.join(PROFILES))
    return PROFILES[model]


def profile_from_identity(identity):
    parts=[part.strip() for part in identity.split(',')]
    if len(parts)<2 or parts[0].upper() not in ('B&K PRECISION','BK PRECISION'):
        raise ValueError('Unsupported instrument identity: '+identity)
    return get_profile(parts[1])
