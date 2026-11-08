# BenchControl B&K 9xxx · 1.9.1

Windows desktop control for the B&K Precision 9130B / 9131B / 9132B through NI-VISA. Python/Tkinter UI, PyVISA transport; no LabVIEW or B&K application required.

## Update

Close the old app. Extract this ZIP over the existing BenchControl-9130B folder, replacing the files and preserving the .venv directory. Run Start.bat. Dependencies are unchanged; no reinstall is required.

For a fresh installation, install Python 3.11 or later with its launcher and Tcl/Tk, install NI-VISA, extract this ZIP and run Install.bat once. That step downloads PyVISA and requires internet access. Run Start.bat afterward. No PowerShell activation is required.

## Version 1.9.1 model heading

The large header now displays the detected model, for example **9130B**, replacing BENCHCONTROL. Removed the separate family/independent-channels subtitle. Before the first connection the heading is POWER SUPPLY. The last detected model remains visible after disconnect; connection state remains in the bottom status bar. Settings and Connect/Disconnect retain their positions on the right. No instrument or control behavior changed.

## Version 1.9.0 model profiles

Added enabled USBTMC profiles for **9131B** (CH1/2 30 V / 6 A) and **9132B** (CH1/2 60 V / 3 A), retaining **9130B**. CH3 stays 5 V / 3 A on every enabled model. The hardware model is detected automatically from its identity. Editor ranges, backend checks, full-range graphs, device information and preset model checks follow that detected profile. All manual and Instant-mode checks remain in place.

No manual hardware model override is provided. Settings > Connection includes a model selector for Demo simulation only. Connection never programs a voltage/current value or changes an output state. Existing 9130B presets retain their model tag. Cross-model presets are refused.

Capability configs are in **profiles/**. C-series rating drafts are in **profiles/drafts/** and remain disabled because the current C-series programming download labels its contents B-series. Other 9xxx families, including the USB-to-TTL 9129B, are not enabled by these profiles. See **MODEL-PROFILES.md** for the full coverage table, command-verification limits and source references. Editing the JSON cannot bypass the driver/model allowlist or the vetted capability limits.

The new 9131B/9132B profiles are documented and tested in simulation; physical operation is unverified. The existing 9130B timing measurements do not establish new-model throughput. The extracted application folder remains BenchControl-9130B so existing Start.bat and .venv installations can be updated normally.

## Version 1.8.1 configurable Instant delay and stable labels

**Settings > General > Instant edit delay (ms)** controls the pause after typing, digit arrows or mouse-wheel edits before a live command is queued. The default is increased to **750 ms**. Range: **100–3000 ms**, in 50 ms steps through the spinner; valid integer values can also be typed. The delay is saved between launches. Existing preference files receive the new 750 ms default. Saving settings cancels pending edits; it never sends existing drafts. **Enter still queues the field immediately.**

Removed the changing waiting-for-confirmation text in Instant mode. Both main and detail panels use a constant **LIVE EDITS** label and stable colour while edits are pending or confirmed, preventing that label from changing the detail window's requested width. Manual mode retains its unapplied-edit indicator. Command readback verification and error reporting remain active; only the pending-status presentation changed. PSU commands and queue safety behavior are unchanged.

## Version 1.8.0 Instant mode

Based on the supplied 1.7.6 release; its queue, shutdown, logging, preferences and graph fixes are retained.

Enable **Settings > General > Instant mode — live voltage/current edits, no Apply button**, then **Save settings**. The option is off by default and is remembered across launches. Saving/enabling the option sends no setpoints. Disable it to restore the original manual Apply workflow and its output-OFF requirement.

With Instant mode enabled:

- Voltage and current editors remain editable while the channel is ON or OFF. The Apply button is hidden in the main and detail channel views.
- Typing, digit arrows and the focused mouse wheel send after the configured pause (**750 ms** by default). **Enter** queues the edited field immediately, without waiting for that pause. These delays are debounce times, not guaranteed hardware response times.
- Only the edited field is written: a voltage change does not rewrite the current limit, and a current change does not rewrite voltage. The output state is not changed by a live edit.
- Setpoint-Apply confirmation is bypassed in this explicitly enabled mode. Output-ON confirmation retains its separate preference and hardware readback checks. Activation remains an explicit action.
- Each setpoint is range-checked, rounded to 1 mV / 1 mA, checked for independent mode, written, checked for instrument errors and verified by readback. Invalid/incomplete input is not transmitted; the status bar identifies invalid input after the pause. Combined mode refuses the edit without changing configuration.
- Newer queued edits replace older edits for the same field and channel. Returning to the previous value also replaces a pending edit; it is not ignored based on an older snapshot.
- OFF, all-off and Disconnect retain priority. They cancel scheduled edits and queued live writes. Disabling Instant mode also cancels pending writes. A VISA operation already in flight can finish before cancellation takes effect; a failed command/readback is not automatically retried. Communication failure closes the connection and leaves output state unconfirmed, as before.
- Connection snapshots, opening detail windows and loading presets never schedule live writes. Loaded presets remain drafts; press Enter in each field to send it, or edit that field. Genuine user edits in either view use the shared channel values.

The smaller PSU line shows hardware-confirmed setpoints. The draft indicator remains LIVE EDITS without changing text while a command is pending. Output ON is refused while its channel's editor values differ from confirmed settings; there is no automatic enable after an edit completes.

Implementation reference: B&K 9130B Series programming manual, pages 19–20, `CURRent[:LEVel][:IMMediate][:AMPLitude]` and `VOLTage[:LEVel][:IMMediate][:AMPLitude]`:
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9130B_Series_programming_manual.pdf

## Version 1.7.6 review fixes

- **OFF requests no longer cancel each other.** An OFF, all-off or disconnect request cancels only queued Apply and Output ON requests. Previously, clicking OFF on two channels during a scan could silently drop the first OFF. Cancelled requests are now reported in the status bar.
- **Switch off all outputs attempts every channel.** If sending OFF or reading back one channel fails, the remaining channels are still switched off and checked. The error lists every channel still ON and every failure.
- **Declined requests keep the connection.** "Switch this channel OFF before changing its settings", "Settings changed since confirmation", combined-mode and out-of-range refusals send no output or setpoint command, so they now show a warning without disconnecting. Communication failures, readback mismatches after writes and unconfirmed output states still close the session and report unknown output state.
- **Busy state** stays set until every queued control request has reported back (for example, an OFF waiting behind an Apply).
- **Event log** is a single window that appends new lines and only follows the end when you are already there, so you can scroll back and select text. It keeps the last 5000 lines.
- **Settings** no longer reverts the main screen's time base or CSV interval when those fields were not changed in the Settings window.
- **Preferences path** uses `%LOCALAPPDATA%`, which also applies to redirected profiles. Benchmarks read it as UTF-8.
- **Graph performance:** traces are reduced in a single pass. Windows where one pixel covers several seconds redraw less often (at most every 2 s); 10 s and 1 min windows stay at 5 Hz. Detail windows redraw on resize through the same scheduler. Statistics still update with every refresh. Readback noise down to −1% of the axis maximum is not marked clipped.
- CSV logs flush to disk at most once per second and on close. Control states refresh once per batch of events. Output ON selects the channel once. Unused bulk-query demo code and rate-tracking variables were removed.

No SCPI commands, acquisition timing or setpoint behaviour changed, apart from all-off continuing after a per-channel failure.

## Version 1.7.5 output status colour

The OUTPUT ON status under the channel heading stays green during the red current-limit indication and its 0.5-second hold. The rest of the channel remains red. OFF and disconnected statuses remain muted. The action toggle remains neutral. No instrument commands or acquisition changes.

## Version 1.7.4 channel layout, startup and limit indication

Replaced the native split pane with separate grid rows for channel content, the narrow divider and the graph. The channel row is bounded by its full requested height; the graph occupies a different row and cannot overlap it. Dragging continues to show a preview until release. Window height is reserved for complete channel content. Settings and Connect/Disconnect now share the BENCHCONTROL header row, on the right.

Fixed the control-state cache: no reading and an actual OFF reading now have distinct keys, so Output ON becomes available on the first valid OFF snapshot. An initial reading also initializes voltage/current drafts directly from the confirmed PSU setpoints. No Apply command is needed solely to initialize the controls. Opening a detail window preserves shared unapplied edits. Existing range, unapplied-edit and hardware readback checks remain in place.

During a detected current-limit condition, the status below the channel heading remains OUTPUT ON, and the channel turns red. Removed near-limit/recent-limit warning text. The output toggle stays available for switching OFF. The red hold is reduced from 1.5 to 0.5 seconds after the last detected limiting sample; a scheduled repaint clears the remaining hold without waiting for the next acquisition scan once a clear sample has arrived. Switching OFF clears red immediately. Detection remains an estimate from measured current versus setpoint, not a hardware CC flag.

## Version 1.7.3 pane sizing and Minimal UI

The channel pane minimum height is now measured from the full requested layout, including labels, editors, and footer buttons with the current Tk font/DPI metrics. The window minimum height reserves space for the complete channel pane, graph, toolbar and status bar. The divider cannot compress the channel contents. Dragging shows a narrow preview bar; pane sizes update when released, reducing repeated button repaints. Canvas resize events mark the graph dirty for the existing throttled plot refresh instead of redrawing immediately on every event.

Output toggle labels are now **Output ON** and **Output OFF**, indicating the available action. The separate green status below the channel heading continues to show confirmed hardware state.

Open **Settings > Preferences > General**, enable **Minimal UI — hide graph section**, and save. This hides the main graph, graph selectors and divider. Presets, CSV logging and its interval, Event log, channel controls, Connect and Settings remain accessible. The setting persists across launches. Restoring the graph restores its previous divider position where space permits. A hidden graph does not stop acquisition, history, statistics or CSV logging. Channel detail windows remain available.

## Version 1.7.2 shutdown and output toggle

Shutdown now selects CH1, CH2 and CH3 and sends CHAN:OUTP OFF to each, then reads back each channel and checks SYST:ERR? before closing the session. It avoids the previous APPL:OUT 0,0,0 command associated with the reported error 170. The exact meaning of that error code has not been established. The replacement channel commands are documented on page 19 of the manufacturer's 9130B programming manual and are already used by individual OFF actions. No voltage or current setpoints are changed. Shutdown success still requires all three outputs confirmed OFF.

Each channel has one neutral toggle button: Switch output ON while confirmed OFF, Switch output OFF while confirmed ON. ON retains the existing optional confirmation, draft checks and hardware setpoint verification. OFF remains available during a pending operation and takes priority in the command queue. Labels follow confirmed hardware state; disconnected/stale controls are disabled. Main and detail views use the same behavior. The green OUTPUT ON status below the channel heading is unchanged.

Connection identity or Disconnected now appears at the right of the bottom status bar. Event messages appear on the left. Connect and Settings remain at the top; the draggable graph divider is retained.

## Version 1.7.1 layout correction

The **OUTPUT ON status directly below CH1/CH2/CH3** now has the green background when enabled. The ON/OFF action buttons remain neutral. OFF and disconnected statuses are muted; current-limit warnings keep their red indication. Connect/Disconnect and Settings are restored to the top, above the channel tiles. The channel/graph separator is a narrow draggable bar without a large handle. The graph remains vertically resizable, and its plotting/logging controls stay below it.

## Version 1.7 output state, disconnect and layout

- **OUTPUT ON status below the channel heading** has a green box while that channel is confirmed enabled. This applies to main and detail views. Action buttons remain neutral. It clears on confirmed OFF or loss of connection; red current-limit indications take precedence.
- Removed standalone global ALL OUTPUTS OFF buttons from the main and detail windows. Individual channel OFF buttons remain.
- **Disconnect** opens three choices: **Leave outputs at current state**, **Switch off all outputs and disconnect**, or **Cancel**. Escape/window close cancels. Leave does not change output states; switch-off now uses the per-channel OFF sequence described for version 1.7.2 and verifies all three output states before disconnecting. Queued non-shutdown actions are invalidated. If shutdown cannot be verified, no success is reported: the communication session is closed and the UI reports unknown output state, requiring a front-panel check.
- Closing the application while connected uses the same three choices. Shutdown/close waits for the worker result. A shutdown error leaves the application open with its error message.
- Drag the horizontal divider between channel tiles and the lower graph to resize the graph section vertically. Plot controls remain below it. Presets, logging/interval and Event log are below the main plot. Settings and Connect/Disconnect are at the top. Channel ON/OFF controls stay with their channel readings. Detail graph selectors are below their plot as well.

No voltage/current programming commands or acquisition timing changes were introduced by this release.

## Version 1.6 UI cleanup and graph scales

Removed the main-window connection/settings hint, Target/Actual rate notices, demo warning checkbox, per-channel arrow/wheel/Enter hints and logging-interval explanatory sentence. Refresh rate and device selection remain in Settings; Demo mode is available there for simulation. Digit stepping and Enter-to-apply still work. Acquisition continues at the selected rate without the main timing display.

Each graph now has a **Scale** selector:

- **Channel limits** (default): current uses the channel's confirmed current-limit setpoint and voltage uses its confirmed voltage setpoint, both with 10% headroom. A 0.5 A limit gives a 0–0.55 A axis; 5 V gives 0–5.5 V. Unapplied editor changes do not affect scaling. Zero/missing setpoints fall back to the channel's full hardware range.
- **Full range:** 0–3 A, 0–30 V for CH1/2, or 0–5 V for CH3.
- **Manual:** enter a positive maximum and press Enter or leave the field. Voltage and current maxima are remembered separately for that graph for the current session. Main/detail graph controls are independent. The manual Max field is hidden in the automatic modes.

Scale changes affect only the plot. They never modify voltage, current limits, protection or output states. Raw history, statistics and CSV measurements retain their original values. If samples fall outside a chosen axis, the graph title marks them **clipped**. SCPI commands and acquisition timing are unchanged from 1.5.

## Version 1.5 Settings window

Open **Settings > Preferences**, the **Settings…** button, or **Ctrl+,**. The window is nonmodal, so main output controls remain accessible. It has three tabs:

- **General:** acquisition rate (1/2/5/10/15 Hz), default graph window, CSV log interval, and independent confirmation toggles for setpoint Apply and output enabling. Saving applies these options immediately. Output confirmation defaults ON; the optional setpoint-Apply confirmation defaults OFF, matching previous behavior.
- **Connection:** editable VISA address/alias, Refresh device list, Demo mode, I/O timeout (500–10000 ms) and USB query delay (0–100 ms). Disconnect before changing these fields; they are locked during an active or pending connection. Save first, then explicitly Connect. Other interface pacing stays 25 ms. Longer I/O timeouts can delay an OFF command behind an in-flight stalled transaction.
- **Device:** current connection identity and the supported model/channel ranges. This uses existing identity data; opening the window does not query the PSU or alter its configuration.

Turn off **Confirm voltage/current before enabling an output** to suppress the existing output-on dialog. Turn on/off **Confirm before applying voltage/current changes** to control a separate Apply confirmation. Disabling prompts does NOT bypass range checks, unapplied-draft checks, output-OFF requirements for programming, or backend setpoint/output readback verification. Output activation still requires an explicit ON action. Closing/disconnect warnings are separate and retained.

**Save settings** in the window persists all preferences atomically to `%LOCALAPPDATA%\BenchControl9130B\preferences.json`. **Cancel** discards draft edits. The former resource-only file is migrated on load; malformed fields fall back individually to defaults. The successful-connect write no longer replaces other preferences. Device discovery lists resources without opening/querying them. No auto-connect or output restore is added.

The main toolbar now uses **Save preset… / Load preset…** for voltage/current JSON profiles to distinguish them from application preferences. Graph time base and CSV interval remain directly accessible on the main screen; values selected there can be saved through Preferences.

## Version 1.4 speed changes

- **USB query delay: zero.** This removes the old 25 ms added delay per query. Other interfaces retain 25 ms pacing because the zero-delay sustained test was performed on USB only.
- **Default acquisition target: 10 Hz.** Available targets are 1, 2, 5, 10 and 15 Hz. 15 Hz is a higher target to evaluate in the complete UI; no 20 Hz setting is offered. Completed-scan rate is tracked internally; the main timing notice was removed in 1.6. Targets are not guaranteed fresh ADC measurements.
- **Same SCPI scan sequence.** The existing per-channel measurement, output-state and periodic setpoint/error queries are retained. No bulk or extra CC-status commands are introduced.
- **Graphs refresh separately, up to 5 Hz.** Meters, history, statistics and CSV interval selection still process every completed scan. Limiting graph redraws does not drop acquisition samples.
- **Acquisition timestamps are captured in the worker**, at the end of each complete scan, before it enters the UI queue. Log timestamps and displayed acquisition rates therefore do not depend on when the UI handles a queued sample. The three channels are read sequentially, not simultaneously.
- **Short graph windows skip old history efficiently.** Retention is up to one hour with a 60000-sample cap, sufficient for an hour at the 15 Hz target. Long traces preserve sampled extrema when reduced to display pixels. Graph scaling controls determine the visible vertical range independently of stored data.
- **UI event processing yields regularly** so queued readings do not monopolize input handling. Output-off requests retain priority over monitoring, and partial monitoring scans can yield between transactions.

These changes use the supplied USB benchmark: 3407 full scans in 180.03 seconds, 18.92 scans/s, zero errors, with zero added query delay. Normal scans averaged 52.10 ms (worst 56.68 ms); periodic settings-refresh scans averaged 77.62 ms (worst 84.08 ms). All outputs were off, so fresh-measurement speed and warning behavior under load remain unverified. The full app's UI/logging overhead was excluded from that benchmark.

169 tests run: 167 pass and 2 existing Tk event-log tests are skipped because no display is available. Windows layout and physical operation of version 1.9.1 were not verified in this environment. The earlier rate-dependent connection observation was not reproduced or diagnosed; this release does not claim to establish its cause.

## Connect

Close other PSU control applications and NI MAX VISA test panels. Open Settings > Preferences > Connection. Click Refresh device list and choose the PSU resource, or paste its complete working VISA address from NI MAX. Leave Demo unchecked, Save settings, then Connect from the main window. The last successful address is remembered in %LOCALAPPDATA%\BenchControl9130B\preferences.json. Discovery supports VISA aliases.

Demo mode in Settings works without a PSU. It simulates readings; logs are marked DEMO.

Connection reads existing settings and output states. It never resets the PSU, restores a profile automatically or enables an output. An already-enabled output remains enabled. Independent channel operation is required; combined/tracking mode is not configured automatically.

## Channel controls

- Large readings show measured voltage/current and calculated power. Smaller SET and LIMIT fields contain voltage and current-limit drafts.
- Click a measured value to focus its editor, or click the editor directly. In manual mode, type a value and press Enter, or click Apply settings; both draft values are applied together. Instant mode sends only the edited field as described above.
- Select a digit or position the caret at that digit. Up/Down or the mouse wheel changes that decimal position locally. The wheel acts only while the editor is focused. Enter/Apply is still required to send settings. Steps clamp to channel limits at 1 mV / 1 mA resolution.
- UNAPPLIED CHANGES marks drafts differing from hardware settings. Measurement updates do not overwrite drafts. Save/load profiles affect editor values only; profile files never contain output activation states.
- In manual mode, turn a channel OFF before changing settings. Instant mode allows live changes with the output ON. Ranges follow the detected profile; see MODEL-PROFILES.md. CH3 allows 0–5 V and 0–3 A on every enabled model. Manual Apply programs current limit first; Instant mode writes only the edited field. Setpoints are verified by readback. Output ON requires confirmation and checks hardware settings again.
- Individual OUTPUT OFF and shutdown through the Disconnect dialog take priority over queued non-shutdown actions. All-off verifies hardware states before disconnect. A VISA transaction already in flight cannot be interrupted; the default timeout is 1.5 seconds and can be changed in Settings. These are software controls, not a hardware emergency stop.
- Closing or disconnecting offers leave-state, verified all-off, and cancel choices. Communication failure cannot guarantee output shutdown; check the front panel if shutdown is unconfirmed. No automatic output-on retries or reconnections occur.

Click a channel header/DETAILS for larger controls, graphs and minimum/maximum/average voltage, current and power. Main/detail windows share draft values. Statistics include off-state samples and cover the session since connection or Reset statistics. Resetting statistics does not change outputs or discard graph history. The Event log toolbar button opens diagnostic messages.

## Red warning

A channel turns red when enabled current readback approaches its current-limit setpoint. The status remains **OUTPUT ON**; red alone indicates the detected condition. Threshold: measured current >= max(1 mA, setpoint - max(2 mA, 2% of setpoint)), with a positive setpoint. Readback resolution/accuracy especially affects low limits.

This is not confirmed hardware CC or a dedicated short-circuit detector. Normal current-limited loads may also trigger it. It does not cut power or alter PSU protections. Events entirely between samples can be missed. Red stays visible for up to 0.5 seconds after the last detected limiting sample once a clear sample is available; switching output off clears it. Disconnect marks readings stale.

## Graph and CSV timing

Each graph has a full-window time base: 10 s, 30 s, 1 min, 5 min, 15 min, 1 h or All retained. X-axis labels show seconds before the newest scan. A fixed window keeps its width from the start; unused history appears blank. Changing the time base does not change acquisition or the CSV log interval.

CSV log every is separate: Every sample, 0.2 s, 0.5 s, 1 s, 2 s, 5 s, 10 s, 30 s or 60 s. Logging writes the next newly acquired scan at or after that minimum interval. It does not insert repeated, averaged or interpolated measurements. If acquisition is slower, logging is limited to acquired samples. Changes to the interval take effect with the next sample. A queued scan acquired before logging started is not written to the new log.

CSV includes timestamps, source, channel, voltage/current, calculated power, output state, setpoints and estimated near-limit state. Setpoints can be cached for up to two seconds during monitoring and are refreshed after control operations. Every sample logs three rows per complete scan. Disconnect or a file-write error stops logging.

## Benchmarks

Benchmark.bat runs the original short, current-channel voltage/current query-pair test at 25 ms, 10 ms and zero delay. SustainedBenchmark.bat runs the exact three-channel acquisition function at zero added delay for 180 seconds, with periodic settings/error checks and five-second progress checkpoints. JSON reports are saved beside the scripts; partial results are retained on the first error or Ctrl+C.

The sustained test selects each channel and ends on CH3. It never sets voltage/current, enables/disables output, resets the PSU or changes protection. Existing output states remain unchanged. Close the app and other PSU clients before either benchmark. Neither test applies timing settings to the app. See INTERFACE-NOTES.md for research and measured results.

## Troubleshooting and tests

Errors identify the failed query/write. Resolve instrument errors or unread replies before repeatedly reconnecting. Use the VISA resource that responds to *IDN? in NI MAX, then close that test panel. Python and NI-VISA architectures must match (normally both 64-bit).

Run `python -m unittest discover -s tests -v` for simulated controller, worker, timing, UI-logic, compatibility and benchmark tests. Source distribution; no prebuilt Windows executable. Timed output sequences and combined-mode configuration are not implemented. Live setpoint changes are available only through the opt-in Instant mode.
