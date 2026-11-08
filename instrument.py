"""B&K 9130B-family profiles. SCPI from manufacturer programming manual pp. 18–25."""
import math
import time
from dataclasses import dataclass
from model_profiles import DEFAULT_PROFILE, get_profile, profile_from_identity


@dataclass
class Channel:
    number: int
    voltage: float
    current: float
    enabled: bool
    set_voltage: float
    set_current: float
    current_limited: bool = False  # estimated from readback, not hardware CC status
    max_voltage: float | None = None
    max_current: float | None = None


def validate(ch, volts, amps, profile=DEFAULT_PROFILE):
    profile.validate(ch,volts,amps)


def boolean(text):
    value = text.strip().upper()
    if value in ('1', 'ON'): return True
    if value in ('0', 'OFF'): return False
    raise ValueError('Unexpected output state: ' + repr(text))


class PollInterrupted(Exception):
    """A control action has priority over the next monitoring query."""


class Refused(RuntimeError, ValueError):
    """A request was declined before any output or setpoint command was sent.

    The connection is still healthy and the PSU state is unchanged, so the
    worker reports it without disconnecting.
    """


class PSU:
    def __init__(self, device):
        self.device = device
        self.cached_settings = None
        self.settings_at = 0
        self.identity = self.query('*IDN?').strip()
        self.profile=profile_from_identity(self.identity)

    def query(self, command):
        try:
            return self.device.query(command)
        except Exception as exc:
            raise RuntimeError(f'Query {command!r} failed: {exc}') from exc

    def write(self, command):
        try:
            return self.device.write(command)
        except Exception as exc:
            raise RuntimeError(f'Write {command!r} failed: {exc}') from exc

    def select(self, ch):
        validate(ch, 0, 0, self.profile)
        self.write(f'INST CH{ch}')

    def check_error(self):
        reply = self.query('SYST:ERR?').strip()
        if int(reply.split(',')[0]) != 0:
            raise RuntimeError('PSU error: ' + reply)

    def independent(self):
        # Block writes when CH1/2 are combined. Do not change mode automatically.
        for mode in ('TRAC', 'SER', 'PAR'):
            if boolean(self.query(f'OUTP:{mode}?')):
                raise Refused('Set PSU to independent mode on its front panel before control')
        self.check_error()

    def snapshot(self, interrupt=None, force=False):
        def query(command):
            if interrupt and interrupt(): raise PollInterrupted()
            return self.query(command)

        refresh_settings = force or self.cached_settings is None or time.monotonic() - self.settings_at >= 2
        settings = []
        result = []
        for ch in (1, 2, 3):
            if interrupt and interrupt(): raise PollInterrupted()
            self.select(ch)
            volts = float(query('MEAS:VOLT?'))
            amps = float(query('MEAS:CURR?'))
            enabled = boolean(query('CHAN:OUTP?'))
            if refresh_settings:
                set_v, set_i = float(query('VOLT?')), float(query('CURR?'))
            else:
                set_v, set_i = self.cached_settings[ch-1]
            if not all(math.isfinite(x) for x in (volts, amps, set_v, set_i)):
                raise RuntimeError(f'CH{ch}: non-finite instrument reading')
            settings.append((set_v,set_i))
            # Visual warning only: close to current setpoint, not confirmed hardware CC.
            # Low limits are constrained by the instrument's readback resolution/accuracy.
            threshold = max(.001, set_i - max(.002, .02 * set_i))
            near_limit = enabled and set_i > 0 and amps >= threshold
            result.append(Channel(ch,volts,amps,enabled,set_v,set_i,near_limit,*self.profile.limits(ch)))
        if refresh_settings:
            reply = query('SYST:ERR?').strip()
            if int(reply.split(',')[0]) != 0:
                raise RuntimeError('PSU error: ' + reply)
            self.cached_settings = settings
            self.settings_at = time.monotonic()
        return result

    def apply(self, ch, volts, amps):
        try: validate(ch, volts, amps, self.profile)
        except ValueError as exc: raise Refused(str(exc)) from None
        self.independent()
        self.select(ch)
        if boolean(self.query('CHAN:OUTP?')):
            raise Refused('Switch this channel OFF before changing its settings')
        self.cached_settings = None
        self.write(f'CURR {amps:.3f}')
        self.write(f'VOLT {volts:.3f}')
        self.check_error()
        actual_v = float(self.query('VOLT?'))
        actual_i = float(self.query('CURR?'))
        if abs(actual_v - volts) > .002 or abs(actual_i - amps) > .002:
            raise RuntimeError(f'Setpoint verification failed: {actual_v} V, {actual_i} A')

    def set_live(self, ch, field, value, interrupt=None):
        # Write only the edited setpoint; never touch output state or the other
        # setpoint. Standard Apply retains its separate output-OFF requirement.
        try:
            if field not in ('voltage','current'):raise ValueError('Invalid live field')
            validate(ch,value if field=='voltage' else 0,value if field=='current' else 0,self.profile)
        except (ValueError,TypeError) as exc:raise Refused(str(exc)) from None
        value=float(f'{value:.3f}')
        self.independent()
        self.select(ch)
        self.cached_settings=None
        command='VOLT' if field=='voltage' else 'CURR'
        if interrupt and interrupt():raise PollInterrupted()
        self.write(f'{command} {value:.3f}')
        self.check_error()
        actual=float(self.query(command+'?'))
        if not math.isfinite(actual) or abs(actual-value)>.002:
            raise RuntimeError(f'Live {field} verification failed: requested {value}, read {actual}')

    def output(self, ch, state, expected=None):
        if state:
            self.independent()  # mode queries only; channel selection unaffected
        self.select(ch)
        if state:
            actual = (float(self.query('VOLT?')), float(self.query('CURR?')))
            try: validate(ch, *actual, self.profile)
            except ValueError as exc: raise Refused(str(exc)) from None
            if expected is None or any(abs(a-b) > .002 for a,b in zip(actual, expected)):
                raise Refused('Settings changed since confirmation. Review and retry')
        self.write('CHAN:OUTP ' + ('ON' if state else 'OFF'))
        self.check_error()
        if boolean(self.query('CHAN:OUTP?')) != state:
            raise RuntimeError('Output state was not confirmed')

    def all_off(self):
        # Use the same channel commands as individual OFF, avoiding the bulk
        # APPL:OUT command rejected by the user's firmware. Every channel is
        # attempted even if an earlier channel's write or readback fails, so
        # one failure can never leave later channels untouched.
        failures = []
        for ch in (1, 2, 3):
            try:
                self.select(ch)
                self.write('CHAN:OUTP OFF')
            except Exception as exc:
                failures.append(f'CH{ch} OFF: {exc}')
        still_on = []
        for ch in (1, 2, 3):
            try:
                self.select(ch)
                if boolean(self.query('CHAN:OUTP?')): still_on.append(f'CH{ch}')
            except Exception as exc:
                failures.append(f'CH{ch} readback: {exc}')
        try: self.check_error()
        except Exception as exc: failures.append(str(exc))
        if still_on or failures:
            detail = ([', '.join(still_on) + ' still ON'] if still_on else []) + failures
            raise RuntimeError('All-off NOT confirmed; check PSU front panel. ' + '; '.join(detail))

    def close(self):
        self.device.close()


class DemoDevice:
    """In-memory demonstration, not a model of PSU electrical behavior."""
    def __init__(self,model='9130B'):
        self.profile=get_profile(model)
        self.ch = 1
        self.settings = [[3.3,.1,False], [5,.2,False], [1.2,.1,False]]
        self.limited_channels = set()
    def write(self, cmd):
        op, _, arg = cmd.partition(' ')
        s = self.settings[self.ch-1]
        if op == 'INST': self.ch = int(arg[-1])
        elif op == 'CURR': s[1] = float(arg)
        elif op == 'VOLT': s[0] = float(arg)
        elif op == 'CHAN:OUTP': s[2] = boolean(arg)
        else: raise ValueError('Unknown demo command: ' + cmd)
    def query(self, cmd):
        s = self.settings[self.ch-1]
        if cmd == '*IDN?': return f'B&K Precision,{self.profile.model},DEMO,simulation'
        if cmd == 'SYST:ERR?': return '0,"No error"'
        if cmd in ('OUTP:TRAC?', 'OUTP:SER?', 'OUTP:PAR?'): return '0'
        if cmd == 'VOLT?': return str(s[0])
        if cmd == 'CURR?': return str(s[1])
        if cmd == 'CHAN:OUTP?': return str(int(s[2]))
        if cmd == 'MEAS:VOLT?': return str((min(s[0],s[1]*.1) if self.ch in self.limited_channels else s[0]) if s[2] else 0)
        if cmd == 'MEAS:CURR?': return str((s[1] if self.ch in self.limited_channels else min(s[1],s[0]/100)) if s[2] else 0)
        raise ValueError('Unknown demo query: ' + cmd)
    def close(self): pass
