"""Query-only latency benchmark. Never sets voltage, current, channel or output."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import time


def measure(device, count, delay):
    device.query_delay=delay
    cycles=[];pairs=[]
    for _ in range(count):
        started=time.perf_counter()
        values=[]
        for command in ('MEAS:VOLT?','MEAS:CURR?'):
            try:value=float(device.query(command).strip())
            except Exception as exc:raise RuntimeError(f'{command}: {exc}') from exc
            if not math.isfinite(value):raise RuntimeError(f'{command}: non-finite value')
            values.append(value)
        cycles.append(time.perf_counter()-started);pairs.append(values)
    ordered=sorted(cycles)
    return {'query_delay_ms':delay*1000,'pairs_completed':count,
            'mean_pair_ms':statistics.mean(cycles)*1000,
            'median_pair_ms':statistics.median(cycles)*1000,
            'p95_pair_ms':ordered[min(len(ordered)-1,math.ceil(.95*len(ordered))-1)]*1000,
            'pairs_per_second':count/sum(cycles),
            'unchanged_adjacent_pairs':sum(a==b for a,b in zip(pairs,pairs[1:]))}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource');parser.add_argument('--count',type=int,default=40)
    parser.add_argument('--baud',type=int,default=115200,choices=(4800,9600,19200,38400,57600,115200))
    args=parser.parse_args()
    if not 1<=args.count<=500:parser.error('--count must be 1–500')
    print('Close BenchControl, the B&K application and NI MAX test panels first.')
    print('This test reads voltage/current on the currently selected channel only.')
    print('Outputs retain their present state. No channel or output settings are sent.')
    resource=args.resource
    if not resource:
        from preferences import preferences_path
        try:default=json.loads(preferences_path().read_text(encoding='utf-8')).get('resource','')
        except (OSError,ValueError,AttributeError):default=''
        resource=input(f'VISA resource [{default}]: ').strip() or default
    if not resource:raise SystemExit('No resource supplied')
    import pyvisa
    result={'resource':resource,'timestamp':datetime.now().astimezone().isoformat(),
            'scope':'current-channel voltage/current round trip; not ADC freshness or full app scan',
            'phases':[],'status':'failed'}
    out=Path(__file__).with_name('benchmark-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    try:
        with closing(pyvisa.ResourceManager()) as rm:
            with closing(rm.open_resource(resource,open_timeout=2000)) as dev:
                dev.timeout=1500;dev.write_termination='\n';dev.read_termination='\n';dev.query_delay=.025
                if dev.resource_name.upper().startswith('ASRL'):
                    dev.baud_rate=args.baud;dev.data_bits=8;dev.parity=pyvisa.constants.Parity.none
                    dev.stop_bits=pyvisa.constants.StopBits.one;dev.write_termination='\r\n'
                identity=dev.query('*IDN?').strip();result['identity']=identity
                parts=[v.strip() for v in identity.split(',')]
                if len(parts)<2 or parts[1].upper()!='9130B' or 'B&K' not in parts[0].upper():
                    raise RuntimeError('Only B&K Precision 9130B is accepted: '+identity)
                print(identity)
                for delay in (.025,.010,0.):
                    phase=measure(dev,args.count,delay);result['phases'].append(phase)
                    print(f"Delay {delay*1000:4.0f} ms: {phase['pairs_per_second']:.1f} V/I pairs/s; median {phase['median_pair_ms']:.1f} ms; p95 {phase['p95_pair_ms']:.1f} ms")
                result['status']='completed'
    except Exception as exc:
        result['error']=str(exc);print('Stopped at first error: '+str(exc))
    result['interpretation']='Completed query rates are not necessarily fresh measurement rates. Equal readings on a stable load do not establish ADC speed. Compare interfaces on the same PSU, PC, channel and load.'
    out.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('Report: '+str(out))


if __name__=='__main__':main()
