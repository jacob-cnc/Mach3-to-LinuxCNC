# Retrofit plan: 3040 mill, Mach3 USB to LinuxCNC

Status: high-level plan, 2026-11-25. Nothing here approves wiring or settings. Each phase gets its own detailed document before work starts on it.

Sources: [machine baseline](machine-baseline.md) and the [OEM manual transcription](3040-mach3-oem-manual.md). Where the manual is silent or contradicts itself, the item is marked unknown and moves to the Phase 1 survey.

## Target hardware

Mesa 7i96S with a 7i85S daughtercard, the same stack as the owner's lathe. See [ADR-001](../decisions/ADR-001-motion-controller.md).

| Function | Now (per OEM manual) | Planned | Notes |
|---|---|---|---|
| Motion controller | XHC NcUsbPod USB card running Mach3 | 7i96S on Ethernet to a LinuxCNC PC | XHC card is Mach3-only |
| X/Y/Z drives and motors | Models unknown; 320 steps/unit example | Keep OEM drives if they survey well; 7i96S step/dir 0–2 | 320 steps/mm fits a 5 mm lead screw at 1/8 microstep. Confirm. |
| 4th axis | Not fitted (A disabled) | 7i96S step/dir 3 reserved | |
| Spindle | 2.2 kW water-cooled spindle on a VFD; Mach3 set to PWM speed control | 7i96S isolated 0–10 V output for speed, digital outputs for run | VFD model and terminals unknown |
| Spindle cooling pump | Separate pump | Switched by an output and interlocked with spindle run | Running the spindle dry can damage it |
| Cutting coolant pump | Separate pump | Switched by an output (M8/M9) | |
| Limit/home switches | 2 per axis (6 total) | 7i96S inputs | Switch type and wiring unknown; manual examples conflict |
| Probe / tool setter | Probe input | 7i96S inputs | Probe type unknown |
| E-stop | Input to the USB card (software stop) | Hardwired E-stop chain that removes drive enable and VFD run, plus a 7i96S status input | |
| Pendant | WHB04B manual in vendor bundle | WHB04B on USB (LinuxCNC `xhc-whb04b-6`) or an MPG on the 7i85S | Confirm whether one is owned |
| 7i85S encoder inputs | — | Spare | For an MPG, linear scales or closed-loop motors later |

## Preliminary I/O budget (7i96S)

Counts assume the planned functions above. They get replaced by a real I/O map in Phase 2.

### Inputs (11 available)

| Function | Inputs |
|---|---:|
| E-stop chain status | 1 |
| Axis switches, shared home + both limits per axis | 3 |
| Probe | 1 |
| Tool setter | 1 |
| VFD fault | 1 |
| Drive alarm (all drives combined) | 1 |
| Spindle coolant flow switch (optional) | 1 |
| **Total** | **9** |

If each of the 6 axis switches gets its own input, the total is 12, one more than the card has. That needs either shared switch wiring or a 7i84 I/O card on the RS-485 port.

### Outputs (4 × 2 A, 2 × 100 mA)

| Function | Output type |
|---|---|
| Machine / drive enable relay | 2 A |
| Spindle cooling pump relay | 2 A |
| Flood coolant relay | 2 A |
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
| 2. Design | I/O map, E-stop and safety circuit, protective earth and isolation, power supplies (5 V logic, 24 V field), panel layout, cable plan. | I/O map and schematic reviewed. |
| 3. Config and bench test | LinuxCNC sim config first. Then the Mesa stack on the bench: flash firmware and check every input and output in HAL before any motor is connected. | Every I/O point verified on the bench. |
| 4. Install and commission | Swap controllers. Bring up one axis at a time at reduced speed (direction, scale, travel), then limits and homing, spindle speed calibration, coolant interlock, probe, pendant. | [Commissioning checklist](../commissioning/README.md) complete. |
| 5. Validate | Repeat the Phase 0 measurements and test cut. Fault tests: E-stop, Ethernet unplugged, limit trip, VFD fault. | Results recorded; machine released for use. |

**Rollback:** keep the XHC card and Mach3 PC intact until Phase 5 passes. Wire the Mesa stack so the OEM controller can go back in (connectors or labeled terminals, no cut OEM cables).

## Open decisions

1. Reuse the OEM drives, power supplies and control box, or build a new panel.
2. Mill PC: dedicated machine, and which GUI (AXIS, QtDragon, Probe Basic, or a custom GUI like the lathe's).
3. Machine units: mm (as the OEM set it up) or inch (as on the lathe).
4. Axis switches: shared home/limit inputs, or one input per switch with a 7i84.
5. Pendant: WHB04B on USB, or an MPG on the 7i85S.
6. Spindle cooling interlock: flow switch, or pump runs whenever the machine is enabled.

## Unknowns for the Phase 1 survey

- Drive make and model, microstep and current settings, alarm output, step/dir input levels and timing.
- Motor nameplates; ballscrew lead per axis; travel per axis.
- Power supply voltages and ratings.
- VFD make and model, control terminals, analog input range, RS-485 support.
- Switch type (mechanical or NPN/PNP proximity), NO/NC, and how they are wired.
- Probe and tool setter type.
- E-stop button wiring and what it actually switches today.
- How the pumps are powered and switched.
- Whether a WHB04B pendant is owned.
