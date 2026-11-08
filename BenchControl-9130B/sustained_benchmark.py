"""Sustained 9130B three-channel acquisition test. No output programming."""
import argparse
from contextlib import closing
from datetime import datetime
import json
import math
from pathlib import Path
import statistics
import time
from instrument import PSU


def latency_summary(values):
    if not values:return {'count':0}
    ordered=sorted(values)
    return {'count':len(values),'mean_ms':statistics.mean(values)*1000,
            'median_ms':statistics.median(values)*1000,
            'p95_ms':ordered[min(len(ordered)-1,math.ceil(.95*len(ordered))-1)]*1000,
            'max_ms':max(values)*1000}


def run_test(psu,seconds=180,delay=0,checkpoint=None,clock=None):
    clock=clock or time.monotonic
    psu.device.query_delay=delay
    result={'status':'running','duration_requested_s':seconds,'query_delay_ms':delay*1000,
            'scans_completed':0,'error_count':0,'unchanged_adjacent_scans':0}
    normal=[];refresh=[];previous=None;start=clock();next_report=start+5
    def summary():
        elapsed=max(clock()-start,0)
        result.update(elapsed_s=elapsed,scans_per_second=result['scans_completed']/elapsed if elapsed else 0,
                      normal_scans=latency_summary(normal),settings_refresh_scans=latency_summary(refresh))
        return dict(result)
    try:
        while clock()-start<seconds:
            before=clock()
            settings_due=psu.cached_settings is None or before-psu.settings_at>=2
            rows=psu.snapshot()  # identical acquisition function used by the app
            duration=clock()-before
            (refresh if settings_due else normal).append(duration)
            result['scans_completed']+=1
            signature=tuple((r.voltage,r.current,r.enabled) for r in rows)
            if previous==signature:result['unchanged_adjacent_scans']+=1
            previous=signature
            result['last_readings']=[{'channel':r.number,'voltage_V':r.voltage,'current_A':r.current,
                                      'output_on':r.enabled,'set_voltage_V':r.set_voltage,'current_limit_A':r.set_current} for r in rows]
            if clock()>=next_report:
                if checkpoint:checkpoint(summary())
                next_report=clock()+5
        result['status']='completed'
    except KeyboardInterrupt:
        result['status']='interrupted'
    except Exception as exc:
        result.update(status='failed',error_count=1,error=str(exc))
    return summary()


def save_report(path,data):
    temporary=path.with_suffix('.json.tmp')
    temporary.write_text(json.dumps(data,indent=2),encoding='utf-8')
    temporary.replace(path)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--resource');parser.add_argument('--seconds',type=float,default=180)
    parser.add_argument('--query-delay-ms',type=float,default=0)
    args=parser.parse_args()
    if not 1<=args.seconds<=1800:parser.error('--seconds must be 1–1800')
    if not 0<=args.query_delay_ms<=100:parser.error('--query-delay-ms must be 0–100')
    print('Close BenchControl, other PSU software and NI MAX test panels first.')
    print(f'Three-channel test: {args.seconds:g} seconds; {args.query_delay_ms:g} ms added query delay.')
    print('Uses channel-selection writes and measurement/settings queries only.')
    print('Voltage settings, current limits, output states and protection are not changed.')
    print('The selected channel will end on CH3. Ctrl+C stops and saves a partial report.')
    resource=args.resource
    if not resource:
        from preferences import preferences_path
        try:default=json.loads(preferences_path().read_text(encoding='utf-8')).get('resource','')
        except (OSError,ValueError,AttributeError):default=''
        resource=input(f'USB/GPIB VISA resource [{default}]: ').strip() or default
    if not resource:raise SystemExit('No resource supplied')
    path=Path(__file__).with_name('sustained-benchmark-'+datetime.now().strftime('%Y%m%d-%H%M%S')+'.json')
    report={'resource':resource,'timestamp':datetime.now().astimezone().isoformat(),
            'scope':'all-three-channel app acquisition function at maximum completed-scan rate; not ADC freshness',
            'status':'starting','duration_requested_s':args.seconds,'query_delay_ms':args.query_delay_ms}
    save_report(path,report)
    def checkpoint(data):
        report.update(data);save_report(path,report)
        print(f"{data['elapsed_s']:6.1f} s | {data['scans_completed']:6d} scans | {data['scans_per_second']:.2f} scans/s | errors {data['error_count']}",flush=True)
    try:
        import pyvisa
        with closing(pyvisa.ResourceManager()) as rm:
            with closing(rm.open_resource(resource,open_timeout=2000)) as device:
                # Serial is excluded from this zero-delay stress test: its manual requires pacing.
                if not device.resource_name.upper().startswith(('USB','GPIB')):
                    raise RuntimeError('This sustained test accepts USBTMC/GPIB resources only')
                device.timeout=1500;device.write_termination='\n';device.read_termination='\n';device.query_delay=.025
                psu=PSU(device);report['identity']=psu.identity;print(psu.identity)
                psu.independent()
                report.update(run_test(psu,args.seconds,args.query_delay_ms/1000,checkpoint))
    except KeyboardInterrupt:
        report.update(status='interrupted')
    except Exception as exc:
        report.update(status='failed',error=str(exc),error_count=1)
    report['interpretation']='Full acquisition scans/s include channel selection, output-state reads, and two-second setpoint/error checks. Excludes UI/plot/CSV overhead. Identical readings do not establish ADC freshness. No normal polling settings were changed.'
    save_report(path,report)
    print('Status: '+report['status'])
    if 'error' in report:print('Stopped at first error: '+report['error'])
    if 'scans_per_second' in report:print(f"Sustained rate: {report['scans_per_second']:.2f} complete three-channel scans/s")
    print('Report: '+str(path))


if __name__=='__main__':main()
