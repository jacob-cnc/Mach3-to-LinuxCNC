# ChinaCNCzone 3040 machine baseline

Source: MACH3 USB Steel structure 3040 Manual-1.docx (22 pages), supplied by owner. Values below are vendor examples, not measured as-built settings.

- Steel structure, three axes, 2200 W spindle, Mach3 USB version (p. 1).
- Separate spindle cooling and cutting-tool coolant pumps (pp. 3–6).
- XHC NcUsbPod Mach3 USB motion controller; manual shows plugin v2.38.8 (pp. 7, 17–18). Supplied archive includes XPOD v2.59.2; installed version unknown.
- Motor output logical step/direction pins X 2/6, Y 3/7, Z 4/8, port 1, active low in example (p. 10). These are not physical Mesa terminal assignments.
- Motor tuning example: 320 steps/unit, 1000.2 units/min, 400 units/s², same XYZ (pp. 12–14). Assuming mm, 16.67 mm/s velocity; verify units, actual screw lead and microstepping before use.
- Spindle PWM control shown (p. 17); actual VFD model and electrical interface unknown.
- Two limit switches per axis according to p. 21. Conflicting home/limit examples on pp. 11, 14–15 and 20; trace wiring rather than copying logical port/pin numbers.
- Vendor recommends VFD grounding and input filtering (p. 19).

## Retrofit plan

Moved to [retrofit-plan.md](retrofit-plan.md).

No runnable configuration or wiring assignment is approved yet.
