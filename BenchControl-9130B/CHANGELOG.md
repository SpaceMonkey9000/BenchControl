# Changelog

Release history for BenchControl, newest first. Version numbers follow the supplied release notes; release dates were not provided.

Installation and current operating instructions are in [README.md](README.md).

## 1.9.1

### Changed

- Replaced the large BENCHCONTROL heading with the detected instrument model, such as **9130B**.
- Removed the separate family/independent-channels subtitle. Before the first connection, the heading reads **POWER SUPPLY**; after disconnecting, the last detected model remains visible.
- Kept Settings and Connect/Disconnect at the right of the header, with connection status in the bottom bar.

No instrument commands or control behavior changed.

## 1.9.0

### Added

- Enabled USBTMC model profiles for **9131B** and **9132B**, alongside **9130B**.
- Automatic model detection and model-specific editor ranges, backend validation, full-range graphs, device information and preset checks.
- A Demo-only model selector in Connection settings.
- Capability files in `profiles/` and disabled C-series rating drafts in `profiles/drafts/`, documented in [MODEL-PROFILES.md](MODEL-PROFILES.md).

### Changed

- Restricted presets to the exact model; cross-model presets are refused.
- Enforced the driver/model allowlist and vetted capability limits independently of profile JSON edits.

9131B and 9132B support was tested in simulation only. Other 9xxx families remain unsupported. The application folder name was retained for compatibility with existing installations.

## 1.8.1

### Added

- Persistent **Instant edit delay (ms)** setting, adjustable from 100 to 3000 ms.

### Changed

- Increased the default Instant edit delay to **750 ms**, including for existing preference files. Enter continues to queue an edited field immediately.
- Replaced changing pending-status text with a constant **LIVE EDITS** label in main and detail views.
- Saving settings cancels pending edits without transmitting existing drafts.

### Fixed

- Prevented pending-status label changes from changing the detail window's requested width.

## 1.8.0

### Added

- Opt-in **Instant mode** for live voltage/current changes with outputs ON or OFF.
- Debounced, field-specific writes; Enter queues a field immediately.
- Range and independent-mode checks, instrument error checks and readback verification for live edits.
- Replacement of older queued edits for the same channel and field.
- Cancellation of scheduled and queued live writes on OFF, all-off, disconnect or disabling Instant mode.

### Changed

- Hid Apply controls in Instant mode and bypassed its setpoint-Apply confirmation. Output-ON confirmation remains independent.
- Kept connection snapshots, detail-window opening and preset loading from scheduling writes. Loaded presets remain drafts.
- Refused output ON while editor values differ from confirmed setpoints.

Instant mode defaults OFF. Manual mode retains its output-OFF requirement. In-flight VISA operations may complete before cancellation; failed commands are not automatically retried. The release retained the 1.7.6 queue, shutdown, logging, preference and graph fixes.

## 1.7.6

### Fixed

- Prevented OFF requests from cancelling other queued OFF requests.
- Made all-off attempt and verify every channel even after a per-channel failure, reporting remaining ON states and failures.
- Kept connections open after validation refusals that send no setpoint or output command. Communication failures and unconfirmed written states still close the session.
- Kept the busy state active until all queued control requests report back.
- Prevented Settings from reverting graph time base or CSV interval when those fields were unchanged.
- Used `%LOCALAPPDATA%` for preferences, including redirected profiles; benchmark preference reads use UTF-8.

### Changed

- Reused one event-log window, retaining 5000 lines and following new entries only when already at the end.
- Reduced graph traces in one pass and throttled long-window redraws to at most once every two seconds, while statistics continue updating with each refresh.
- Routed detail-window resize redraws through the graph scheduler and tolerated small negative readback noise before marking traces clipped.
- Limited CSV flushes to once per second and on close; batched control-state refreshes and removed unused polling code.

## 1.7.5

### Fixed

- Kept the **OUTPUT ON** status green during the channel's red current-limit indication and its hold period.

## 1.7.4

### Changed

- Separated channels, divider and graph into grid rows to prevent overlap and reserve space for complete controls.
- Positioned Settings and Connect/Disconnect at the right of the header.
- Removed near-limit/recent-limit warning text and reduced the red indication hold to **0.5 seconds**.
- Kept the output toggle available for OFF during a detected limiting condition.

### Fixed

- Distinguished missing readings from confirmed OFF readings so output ON becomes available after the first valid OFF snapshot.
- Initialized editor drafts from the first confirmed setpoints without requiring Apply.
- Preserved shared unapplied drafts when opening detail windows.
- Scheduled clearing of the red hold after a clear sample; switching OFF clears red immediately.

## 1.7.3

### Added

- Persistent **Minimal UI** preference to hide the main graph, selectors and divider while acquisition, history, statistics and CSV logging continue.

### Changed

- Calculated minimum channel and window heights from the complete layout and current font/DPI metrics.
- Used a divider preview during dragging, applying pane sizes on release.
- Deferred resize redraws to the graph scheduler.
- Shortened output action labels to **Output ON** and **Output OFF**, with confirmed state shown separately.

## 1.7.2

### Changed

- Replaced the all-output shutdown command with per-channel OFF commands, followed by output-state and instrument-error checks. Shutdown success requires every output confirmed OFF.
- Replaced separate channel actions with one neutral output toggle, following confirmed hardware state.
- Moved connection identity/disconnected status to the bottom right and event messages to the left.

### Fixed

- Avoided the previous `APPL:OUT 0,0,0` shutdown command associated with reported error 170. The exact meaning of that error was not established.

## 1.7.1

### Fixed

- Applied the green enabled background to the status directly below each channel heading, keeping action buttons neutral.
- Restored Connect/Disconnect and Settings above the channel tiles.
- Replaced the large graph divider handle with a narrow draggable bar.

## 1.7

### Added

- Highlighted confirmed **OUTPUT ON** status in main and detail views.
- Added disconnect/close choices to leave outputs unchanged, switch off all outputs and disconnect, or cancel.
- Added a vertically resizable graph section with controls below the plot.

### Changed

- Removed standalone global all-output-OFF buttons; individual channel OFF controls remain.
- Invalidated queued non-shutdown actions during disconnect and waited for shutdown verification before reporting success.
- Reported unknown output state when shutdown could not be confirmed. A close-time shutdown error leaves the app open with the error message.

The per-channel shutdown sequence was revised in 1.7.2.

## 1.6

### Added

- Graph scale modes: **Channel limits**, **Full range** and **Manual**, with independent main/detail controls and clipped-sample indicators.

### Changed

- Removed connection hints, target/actual rate notices, demo warning checkbox, editor hints and logging-interval explanation from the main UI.
- Kept refresh rate, device selection and Demo mode in Settings.

Graph scaling affects display only; raw history, statistics and CSV data retain their measured values.

## 1.5

### Added

- Nonmodal Settings window with General, Connection and Device tabs, accessible through Settings or `Ctrl+,`.
- Acquisition, graph, logging, confirmation, VISA resource, timeout and query-delay preferences.
- Atomic preference saving to `%LOCALAPPDATA%\BenchControl9130B\preferences.json`, migration of the earlier resource-only file and per-field fallback for malformed settings.
- Independent confirmation preferences for Apply and output enabling.

### Changed

- Renamed voltage/current profile actions to **Save preset / Load preset** to distinguish them from application preferences.
- Locked connection settings while connected and required explicit connection after saving.
- Used existing identity data for Device information without querying or changing the PSU when opening Settings.

No auto-connect or output restoration was added. Disabling confirmations does not bypass validation or readback checks.

## 1.4

### Changed

- Removed the additional 25 ms query delay for USBTMC; other interfaces retain 25 ms pacing.
- Set the default acquisition target to **10 Hz**, with selectable 1, 2, 5, 10 and 15 Hz targets.
- Separated graph refresh, capped at 5 Hz, from acquisition and logging.
- Captured timestamps in the worker at the end of each complete scan, before UI queuing.
- Improved history selection, display reduction and UI event scheduling; retained sampled extrema in reduced traces.
- Retained up to one hour of history with a 60000-sample cap.

The existing SCPI scan sequence was retained. A supplied 180-second 9130B USB benchmark recorded 3407 full scans, approximately 18.92 scans/s, with zero errors. Outputs were OFF and readings unchanged; ADC freshness, loaded operation and full UI throughput were not established. See [INTERFACE-NOTES.md](INTERFACE-NOTES.md).
