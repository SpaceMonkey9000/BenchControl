# B&K model profiles · 1.9.0

The existing bk9130b driver now uses per-model channel capabilities from profiles/*.json. Profiles are selected only from the exact model returned by *IDN?. There is no manual hardware model override or generic 9xxx fallback. The model selector in Connection settings is for Demo mode only.

| Model | CH1 and CH2, each | CH3 | Status |
|---|---|---|---|
| 9130B | 30 V / 3 A | 5 V / 3 A | Enabled; user-reported working in earlier releases |
| 9131B | 30 V / 6 A | 5 V / 3 A | Enabled; official shared programming manual, simulated tests only |
| 9132B | 60 V / 3 A | 5 V / 3 A | Enabled; official shared programming manual, simulated tests only |
| 9130C | 30 V / 3 A | 5 V / 3 A | Draft disabled |
| 9131C | 30 V / 6 A | 5 V / 3 A | Draft disabled |
| 9132C | 60 V / 3 A | 5 V / 3 A | Draft disabled |

All listed ranges start at zero. C-series draft JSON files are in profiles/drafts and are not runtime driver profiles. B&K's C-series programming PDF currently identifies its contents as the B-series manual. This is insufficient to enable C-series control under the present verification requirement. Drafts contain ratings and source references only. Merely editing enabled or driver fields does not enable an unapproved model.

Profiles drive backend setpoint validation (manual Apply, live edits and output enabling), editor digit-step limits, typed-value validation, full-range graphs, device information and preset model checks. CH3 never inherits the 9131B six-amp range. Presets are tied to the exact model, including the suffix; cross-model presets are refused. Connection retains existing output states and setpoints. OFF/shutdown, combined-mode refusal, live-edit cancellation and readback verification retain their existing behavior.

Approved capability ranges are checked against the driver registry in model_profiles.py. An unknown model or modified capability profile is refused. New protocol families require a matching driver plus verified capabilities, not just a renamed JSON file.

## Other USB-equipped 9xxx models

- 9129B is not enabled. It uses the IT-E132B USB-to-TTL adapter (virtual COM) and a separate programming manual. Its DB9 is TTL, not a conventional RS-232 port. The adapter/serial configuration and command driver require separate implementation.
- 911x, 917x/918x and 920x families are not enabled. Their channel topology, range/power constraints and command sets cannot be assumed to match this three-channel driver.
- Unknown devices are rejected immediately after identity query, before channel selection, programming or output commands. C-series drafts also remain blocked this way.

## References checked 2026-11-03

B-series programming manual, explicitly covering 9130B / 9131B / 9132B:
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9130B_Series_programming_manual.pdf

B-series ratings and standard USBTMC interfaces:
https://www.bkprecision.com/products/power-supplies/9131B
https://www.bkprecision.com/products/power-supplies/9132B

C-series product ratings:
https://www.bkprecision.com/products/power-supplies/9130C
https://www.bkprecision.com/products/power-supplies/9131C
https://www.bkprecision.com/products/power-supplies/9132C

C-series programming download (contents identify B-series):
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9130C_Series_programming_manual.pdf

9129B programming manual, pages 4–5 for interface:
https://bkpmedia.s3.us-west-1.amazonaws.com/downloads/programming_manuals/en-us/9129B_programming_manual.pdf

No new physical instruments were available for testing. The 9130B USB scan-rate measurements are not evidence of throughput on other models. Acquisition target, query-delay and timeout preferences remain available, but new-model timing has not been measured.
