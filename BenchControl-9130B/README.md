# BenchControl

Windows desktop control and monitoring for B&K Precision 9130B, 9131B and 9132B bench power supplies. Built with Python, Tkinter and PyVISA, using NI-VISA for instrument communication. No LabVIEW or B&K control application is required.

Current version: **1.9.1** · [Changelog](CHANGELOG.md)

## Features

- Independent controls for all three channels, with measured voltage, current and calculated power.
- Manual setpoint application or opt-in Instant mode for live voltage/current edits.
- Main and per-channel graphs, adjustable scales and time windows, and a Minimal UI option.
- Per-channel minimum, maximum and average readings.
- CSV logging with selectable intervals and model-specific JSON setpoint presets.
- Automatic model detection, saved preferences, event logging and a hardware-free Demo mode.

## Supported power supplies

| Model | CH1 and CH2, each | CH3 | Validation status |
| --- | --- | --- | --- |
| 9130B | 0–30 V / 0–3 A | 0–5 V / 0–3 A | User-reported hardware operation in earlier releases |
| 9131B | 0–30 V / 0–6 A | 0–5 V / 0–3 A | Profile enabled; simulation tests only |
| 9132B | 0–60 V / 0–3 A | 0–5 V / 0–3 A | Profile enabled; simulation tests only |

The hardware model is selected from the instrument identity. There is no manual hardware override. C-series profiles remain disabled drafts; other 9xxx families are not supported. Independent channel operation is required; combined/tracking mode is not configured by the app.

See [MODEL-PROFILES.md](MODEL-PROFILES.md) for profile validation, unsupported models and manufacturer references. Physical operation of version 1.9.1 has not been independently verified in the supplied release notes.

## Installation

Requirements:

- Windows.
- Python 3.11 or later, including the Python launcher and Tcl/Tk.
- NI-VISA, with an architecture matching Python, normally 64-bit.
- Internet access for the initial PyVISA installation.

1. Download and extract the source ZIP, or clone the repository.
2. Run `Install.bat` once to install the Python dependencies.
3. Run `Start.bat` to launch BenchControl.

PowerShell environment activation is not required. These instructions describe the Python source distribution.

To update an existing ZIP installation, close BenchControl and extract the new files over the existing application folder, preserving `.venv`. Run `Start.bat`. Version 1.9.1 does not change dependencies. Existing ZIP installations may use the folder name `BenchControl-9130B`.

## Connect

1. Close other PSU control applications and NI MAX VISA test panels.
2. Open **Settings > Preferences > Connection**.
3. Refresh the device list and select the PSU, or paste its working VISA resource address from NI MAX.
4. Leave **Demo** unchecked, save settings, then click **Connect**.

Connection reads the existing setpoints and output states. It does not reset the PSU, apply a preset or enable an output. An output that is already ON remains ON. The header displays the detected model; connection status appears at the bottom right.

For use without hardware, enable **Demo** in Connection settings. Its model selector applies only to simulation, and CSV logs are marked `DEMO`.

## Setpoints and outputs

### Manual mode

Manual mode is the default. Switch the channel OFF, edit its voltage and current limit, then press **Enter** or click **Apply settings**. Both values are applied together, current limit first, and verified by readback. **UNAPPLIED CHANGES** identifies drafts that differ from confirmed settings.

Use Up/Down or the focused mouse wheel to adjust the digit at the caret. Editor steps use 1 mV / 1 mA resolution and clamp to the detected channel range; this is not a statement of instrument accuracy.

Output activation is explicit. The app checks the confirmed settings before enabling a channel. Apply and output-ON confirmations have separate preferences.

### Instant mode

Enable **Settings > General > Instant mode** to allow live setpoint changes while outputs are ON or OFF. Saving this preference sends no setpoints.

- Edits queue after **750 ms** by default; **Instant edit delay (ms)** accepts 100–3000 ms.
- **Enter** queues the edited field immediately. Only that voltage or current-limit field is written.
- Output state is unchanged by an edit. The **LIVE EDITS** label is constant; the smaller PSU line shows confirmed setpoints.
- Loaded presets remain drafts. Edit a field or press Enter in that field to transmit it.

Instant mode bypasses the Apply confirmation. Range checks, independent-mode checks, instrument error checks and readback verification remain active. Output ON is refused while editor values differ from confirmed settings. New queued edits replace older edits for the same field and channel.

### Disconnect and shutdown

Disconnecting or closing while connected offers three choices: leave outputs at their current state, switch off all outputs and disconnect, or cancel.

OFF requests take priority over queued Apply and output-ON requests and cancel pending live edits. An in-flight VISA operation can finish before an OFF request is processed. All-off attempts and verifies every channel. A communication failure can leave output state unknown; check the PSU front panel when shutdown is unconfirmed. Software controls are not a hardware emergency stop.

## Monitoring and logging

Click a channel header or **DETAILS** for larger controls, graphs and minimum/maximum/average voltage, current and power. Statistics include output-OFF samples and cover the period since connection or **Reset statistics**. Resetting statistics does not change outputs or remove graph history.

Graphs offer channel-setpoint, full-range and manual scales. Time windows range from 10 seconds to one hour, or all retained history. Scaling affects the display only; clipped samples remain in history and CSV data. **Minimal UI** hides the main graph without stopping acquisition, statistics or logging.

CSV intervals range from **Every sample** to **60 s** and are independent of graph timing. Logging uses newly acquired scans; it does not interpolate or repeat measurements. Each complete scan produces three rows containing timestamps, source, channel, voltage, current, calculated power, output state, setpoints and estimated near-limit state. Monitoring setpoints may be cached for up to two seconds. Disconnect or a file-write error stops logging.

### Current-limit indication

An enabled channel turns red when measured current approaches its configured current limit. The green **OUTPUT ON** status continues to identify the confirmed output state.

This indication estimates limiting from sampled current and its setpoint; it is not a hardware CC flag or short-circuit detector. It does not cut power or change PSU protection. Events between samples can be missed. After a clear sample, the red indication clears once the 0.5-second hold has expired; switching OFF clears it immediately.

## Settings and presets

Settings include acquisition target, graph defaults, CSV interval, confirmations, Instant mode, VISA resource, I/O timeout and query delay. Connection fields are locked while connected. Save preferences to retain them between launches:

```text
%LOCALAPPDATA%\BenchControl9130B\preferences.json
```

**Save preset / Load preset** manages voltage/current drafts separately from application preferences. Presets never store output activation states and are restricted to the exact instrument model. Loading a preset does not send commands.

## Performance and benchmarks

Acquisition targets are 1, 2, 5, 10 and 15 Hz, with a 10 Hz default. Targets are not guaranteed rates or fresh ADC measurement rates. Channels are sampled sequentially. Graphs redraw separately at up to 5 Hz.

A supplied 9130B USB test completed **3407 full three-channel scans in 180.03 s**, approximately **18.92 scans/s**, with zero errors and no added query delay. All outputs were OFF and readings were unchanged. This measures readout throughput; it does not establish measurement freshness, performance under load, complete UI throughput or performance on other models.

- `Benchmark.bat`: short voltage/current query-pair tests at 25 ms, 10 ms and zero added delay.
- `SustainedBenchmark.bat`: 180-second three-channel acquisition test with periodic settings/error checks.

Close BenchControl and other instrument clients before running a benchmark. Neither benchmark changes setpoints or outputs. The sustained test selects channels and ends on CH3. Reports are saved as JSON beside the scripts. See [INTERFACE-NOTES.md](INTERFACE-NOTES.md) for methods, historical timings and results.

## Troubleshooting

| Symptom | Check |
| --- | --- |
| PSU missing from the list | Refresh discovery or paste the complete working VISA resource address from NI MAX. |
| VISA load or connection failure | Check NI-VISA installation and matching Python/NI-VISA architectures; close competing instrument sessions. |
| Timeout or instrument error | Read the failed query/write in the event log. Resolve instrument errors or unread replies before repeatedly reconnecting. Review acquisition target, query delay and timeout settings. |
| Setpoint or output-ON request refused | Check channel range, independent mode and unapplied drafts. Manual setpoint changes require the output OFF. |
| Shutdown unconfirmed | Check output states at the PSU front panel. Communication loss does not guarantee outputs are OFF. |

Timed output sequences and combined-mode configuration are not implemented. There is no automatic output restoration or reconnection.

## Development

Run the simulated controller, worker, timing, UI-logic, compatibility and benchmark tests from the project directory, using the installed environment:

```bat
.venv\Scripts\python.exe -m unittest discover -s tests -v
```

See [CHANGELOG.md](CHANGELOG.md) for release history. The supplied notes report 167 passing tests and two skipped Tk event-log tests for the release; those results do not verify Windows layout or physical operation of version 1.9.1.
