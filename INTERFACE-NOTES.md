# 9130B interface speed research · 2 November 2026

## Finding

Keep USBTMC for this setup. B&K documents USBTMC, GPIB and RS-232 but publishes no interface-specific measurement queries/second, ADC refresh rate or USB-vs-GPIB readback benchmark in the 9130B documents reviewed. The fastest measured interface on this unit remains unestablished. There is no source-backed basis to buy a GPIB controller for a speed improvement.

| Interface | Verified information | Consequence |
| --- | --- | --- |
| USBTMC | Native supported interface; B&K recommends NI-VISA. | Existing working connection; retain it while measuring software/instrument latency. |
| GPIB | Native supported interface. | Could be compared experimentally, but no published performance advantage for this model was found. |
| RS-232 | Up to 115200 baud; no flow-control mechanism; command pacing required. | Serial wire speed is limited; no evidence it improves this setup's readback rate. |

115200 baud with 8-N-1 carries at most 11520 data bytes/s before protocol and processing overhead. This arithmetic is not a PSU measurement-rate specification. USB/GPIB nominal bus bandwidth likewise cannot establish a PSU's fresh-measurement rate.

## What limits the current app

The compatibility acquisition path deliberately waits 25 ms after writing each query before reading its response. A routine scan uses nine queries, imposing at least 225 ms of delay alone (a theoretical ceiling of 4.44 scans/s before VISA and PSU time). Settings-refresh scans use sixteen queries, imposing 400 ms. Additional channel-selection transactions and the PSU's command/ADC processing take more time. The 5 Hz selector is a target, not a guaranteed acquisition rate.

The earlier bulk/status polling version timed out. Without a command-level trace from that version, the exact failed command remains unidentified. Bulk commands are not re-enabled here. The working controller and acquisition worker are unchanged from 1.2.

## Included query-only benchmark

Close BenchControl, other PSU applications and NI MAX test panels. Run Benchmark.bat and enter the VISA resource (the remembered USB address is the default). It measures repeated MEAS:VOLT? / MEAS:CURR? pairs on the currently selected channel, first with 25 ms query delay, then 10 ms, then zero additional delay. It sends no channel-selection, voltage-setting, current-setting, output-state, reset or protection commands. Existing output states remain unchanged. It stops at the first query error, without automatic retries or buffer clearing.

A timestamped JSON report is saved beside the script. It reports mean/median/p95 latency, completed voltage/current pairs per second and unchanged adjacent pairs. Identical results on a stable load do not reveal ADC freshness. The benchmark does not perform the app's nine/sixteen-query full scan and does not automatically apply its timings to the app.

To compare a GPIB interface, use the same PC, PSU, channel, load and benchmark with that interface's VISA resource after configuring the PSU interface. No GPIB hardware was available for this research. The user subsequently supplied the USB short-run results recorded below; no GPIB rate is claimed. RS-232 testing is supported by the script's --baud argument, default 115200, only when the PSU's serial configuration matches 8-N-1 at that rate. App serial settings are not changed.

## Source verification

B&K 9130B product page — supported interfaces:
https://www.bkprecision.com/products/power-supplies/9130B

Actual 9130B/9131B/9132B manual — printed pages 23 and 33–35 for interface setup, 36–37 for specifications:
https://bkpmedia.s3.amazonaws.com/downloads/manuals/en-us/9132B_manual.pdf

The current product page's generic 9130B_Series_manual.pdf link unexpectedly resolves to a document whose cover says 9130C. The model-B manual above was checked instead; model-C capabilities were not attributed to the B.

9130B series datasheet — specifications page 4:
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/datasheets/en-us/9130B_Series_datasheet.pdf

The datasheet's 180 microsecond transient response for CH1/2 describes electrical regulation following a load change. It is not a computer polling interval or ADC readout rate.

Programming manual — measurement commands:
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9130B_Series_programming_manual.pdf

## User USB result and follow-up

The supplied benchmark-20261102-200058.json completed 40 V/I pairs per phase on USB, firmware 1.06-1.04. Results: 25 ms delay = 19.06 pairs/s (52.46 ms mean); 10 ms = 44.76 pairs/s (22.34 ms); zero delay = 101.56 pairs/s (9.85 ms). Each phase had 39 identical adjacent pairs, so fresh-measurement speed remains unknown. This establishes short-run USB query throughput only; no USB-vs-GPIB comparison has been performed.

SustainedBenchmark.bat in 1.3.2 performs the next 180-second zero-delay full-three-channel test. Normal app timing is deliberately unchanged until that report is evaluated.

## Sustained result and version 1.4

The user pasted the completed 180-second USB sustained report: 3407 scans in 180.0299 s, 18.9246 full three-channel scans/s, zero errors. The test used the app's exact acquisition function with zero added query delay and two-second setpoint/error checks. Normal scans: mean 52.1027 ms, p95 55.7059 ms, maximum 56.6762 ms. Settings-refresh scans: mean 77.6208 ms, p95 82.9759 ms, maximum 84.0807 ms. All outputs were off; all scan readbacks were unchanged. This establishes sustained readout throughput, not ADC freshness under load.

Version 1.4 applies zero added query delay to USBTMC and sets a 10 Hz operating target, with a 15 Hz option to evaluate. Other interfaces retain the previous 25 ms query delay. The historical delay calculations above describe releases before 1.4. Graphs now refresh independently at up to 5 Hz, while all acquired samples remain available for meters, statistics, history and CSV logging. Acquisition timestamps are taken before UI queuing. The full Windows UI has not been physically performance-tested here.
