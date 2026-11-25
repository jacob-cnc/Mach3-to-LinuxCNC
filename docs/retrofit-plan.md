# Retrofit plan: 3040 mill, Mach3 USB to LinuxCNC

Status: high-level plan, 2026-11-25. Nothing here approves wiring or settings. Each phase gets its own detailed document before work starts on it.

Sources: [machine baseline](machine-baseline.md) and the [OEM manual transcription](3040-mach3-oem-manual.md). Where the manual is silent or contradicts itself, the item is marked unknown and moves to the Phase 1 survey.

## Decisions

| # | Topic | Decision (2026-11-25) |
|---|---|---|
| D1 | Control box | Reuse the OEM control box and the components in it that survey well. Modify it as needed for the Mesa stack and added panel controls. |
| D2 | PC and GUI | PC is either the HP EliteDesk 800 G2 (65 W) or the lathe's DreamQuest, if the EliteDesk goes to the lathe instead. Custom GUI similar to the lathe's, built before the retrofit; AXIS stays available for first power-up and as a fallback. |
| D3 | Units | Inch and mm both supported, as on the lathe: the machine runs in inch internally and the GUI displays and accepts either unit. |
| D4 | Axis switches | Keep the mill's 2 limit switches per axis. One input per axis, as on the lathe: both switches on an axis share its input. |
| D5 | Pendant | Off-the-shelf WHB04B for now; possibly a custom pendant later. |
| D6 | Spindle cooling | Pump runs whenever the machine has power. Fallback if that causes trouble: manual switches for spindle cooling and flood coolant. |
| — | Motion controller | Mesa 7i96S + 7i85S, the same stack as the lathe. See [ADR-001](../decisions/ADR-001-motion-controller.md). |

## Target hardware

| Function | Now (per OEM manual) | Planned | Notes |
|---|---|---|---|
| Control box | OEM box with XHC card, drives, PSUs, VFD | Same box, modified (D1) | Panel cut-outs for added controls |
| Motion controller | XHC NcUsbPod USB card running Mach3 | 7i96S + 7i85S on Ethernet | XHC card is Mach3-only |
| PC | Windows PC running Mach3 | EliteDesk 800 G2 or the lathe's DreamQuest, running LinuxCNC (D2) | Mesa needs its own Ethernet port; see Phase 3 |
| X/Y/Z drives and motors | Models unknown; 320 steps/unit example | Keep OEM drives if they survey well; 7i96S step/dir 0–2 | 320 steps/mm fits a 5 mm lead screw at 1/8 microstep, which is exactly 8128 steps/inch. Confirm. |
| 4th axis | Not fitted (A disabled) | 7i96S step/dir 3 reserved | |
| Spindle | 2.2 kW water-cooled spindle on a VFD; Mach3 set to PWM speed control | 7i96S isolated 0–10 V output for speed, digital output for run | VFD model and terminals unknown |
| Spindle cooling pump | Separate pump | On whenever main power is on, wired upstream of the E-stop circuit so it keeps cooling after an E-stop (D6). Not a Mesa output. | Fallback: manual switch |
| Cutting coolant pump | Separate pump | Relay on a Mesa output (M8/M9) | Fallback: manual switch |
| Limit/home switches | 2 per axis (6 total) | Keep both switches. One input per axis (D4): the two switches on an axis wired in series (normally closed) to that input, so it works as the home switch and as a hard limit at both ends. | The OEM manual's second input example already puts X++ and X-- on one pin, so the mill may be wired this way now. Confirm switch type and NC wiring in the survey. |
| Probe / tool setter | Probe input | 7i96S inputs | Probe type unknown |
| E-stop | Input to the USB card (software stop) | Hardwired E-stop chain that removes drive enable and VFD run, plus a 7i96S status input | |
| Pendant | WHB04B manual in vendor bundle | WHB04B (D5). It connects over USB (LinuxCNC `xhc-whb04b-6` driver) and uses no Mesa I/O. | |
| 7i85S encoder inputs | — | Reserved for a future custom pendant (MPGs, as on the lathe), linear scales or closed-loop motors | |

## Preliminary I/O budget (7i96S)

Counts assume the planned functions above. They get replaced by a real I/O map in Phase 2.

### Inputs (11 available)

| Function | Inputs |
|---|---:|
| E-stop chain status | 1 |
| Axis switches, one per axis (D4) | 3 |
| Probe | 1 |
| Tool setter | 1 |
| VFD fault | 1 |
| Drive alarm (all drives combined) | 1 |
| Spindle coolant flow switch (optional; detects a failed pump) | 1 |
| **Subtotal** | **9** |
| Left for panel buttons (cycle start, stop, etc.) | 2 |

With the always-on pump (D6) the flow switch is optional; leaving it out frees a third input for panel buttons. A panel with more buttons than that needs a 7i84 I/O card on the RS-485 port.

### Outputs (4 × 2 A, 2 × 100 mA)

| Function | Output type |
|---|---|
| Machine / drive enable relay | 2 A |
| Flood coolant relay | 2 A |
| Spare | 2 A |
| Spare | 2 A |
| VFD run (forward) | 100 mA (signal level) |
| VFD reverse or spare | 100 mA |

### Other channels

- Analog 0–10 V: spindle speed to the VFD.
- Step/dir: X, Y, Z on channels 0–2; 3 and 4 spare.
- RS-485: free (7i84 expansion or VFD Modbus).
- 25-pin expansion port: used by the 7i85S.

## Phases

Each phase ends with a check that has to pass before the next one starts.

| Phase | Work | Exit check |
|---|---|---|
| 0. Preserve | Save the actual Mach3 profile XML, XHC plugin settings and every VFD parameter. Measure backlash per axis and make a reference test cut. | Backups and measurements are stored outside this public repo, with a summary here. |
| 1. Survey | With power isolated, identify every component in the control box and trace all wiring. | As-built component list and wiring table in `hardware/`. |
| 2. Design | I/O map, E-stop and safety circuit, protective earth and isolation, power supplies (5 V logic, 24 V field), pump power wiring, panel layout and box modifications, cable plan. | I/O map and schematic reviewed. |
| 3. PC, config and bench test | Install LinuxCNC on the mill PC, run a latency test and set up a dedicated Ethernet port for the Mesa. Finish the sim config, then put the Mesa stack on the bench: flash firmware and check every input and output in HAL before any motor is connected. | Latency acceptable; every I/O point verified on the bench. |
| 4. Install and commission | Swap controllers. First power-up on AXIS. Commission on the custom GUI if it is ready, AXIS otherwise. Bring up one axis at a time at reduced speed (direction, scale, travel), then switches and homing, spindle speed calibration, coolant, probe, pendant. | [Commissioning checklist](../commissioning/README.md) complete. |
| 5. Validate | Repeat the Phase 0 measurements and test cut. Fault tests: E-stop, Ethernet unplugged, limit trip, VFD fault. | Results recorded; machine released for use. |

**Rollback:** keep the XHC card and Mach3 PC intact until Phase 5 passes. Wire the Mesa stack so the OEM controller can go back in (connectors or labeled terminals, no cut OEM cables).

### Parallel track: custom GUI

The GUI is built ahead of the retrofit, alongside Phases 0–3, so it is ready for commissioning.

1. Write a sim config (3 axes, inch internal, mill travel) early so the GUI has something to run against. It becomes the starting point for the Phase 3 config. First version: [config/](../config/README.md).
2. Build the mill GUI from the lathe's, reusing its shared parts (such as inch/mm display) and replacing the lathe-specific screens (diameter mode, X/Z layout).
3. Before commissioning, check it against the real HAL pins on the bench (Phase 3).

The mill is simpler than the lathe (open-loop steppers, no dual feedback loop), so AXIS may be enough for commissioning. Having the custom GUI ready means it doesn't have to be.

## Still open

- Which panel buttons to add, which sets whether 11 inputs are enough.
- Whether a WHB04B is already owned.
- Which PC goes on the mill (D2). If the EliteDesk goes to the lathe, the lathe needs its own latency and Mesa link check on the new PC.

## Unknowns for the Phase 1 survey

- Drive make and model, microstep and current settings, alarm output, step/dir input levels and timing.
- Motor nameplates; ballscrew lead per axis; travel per axis.
- Power supply voltages and ratings.
- VFD make and model, control terminals, analog input range, RS-485 support.
- Switch type (mechanical or NPN/PNP proximity), NO/NC, and how they are wired.
- Probe and tool setter type.
- E-stop button wiring and what it actually switches today.
- How the pumps are powered and switched today.
- Free space and mounting room in the control box.
