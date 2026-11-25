# Mill LinuxCNC config

Status: simulation only. Not tested on hardware, and nothing here is approved for the machine.

## Files

| File | Purpose |
|---|---|
| `mill-sim.ini` | Sim config: 3 axes, inch internal, AXIS GUI |
| `mill_core.hal` | Logic shared by the sim and the future machine config: joints, switches, E-stop latch, spindle, coolant, probe, tool change |
| `sim_hardware.hal` | Stands in for the Mesa 7i96S + 7i85S: position loopback and simulated axis switches |
| `tool.tbl` | Starter tool table |

In Phase 3, `mesa_hardware.hal` replaces `sim_hardware.hal` and drives the same signals from real Mesa pins. `mill_core.hal` and the GUI stay the same.

## Running it

On a Linux PC with LinuxCNC 2.9 (no Mesa card or realtime kernel needed):

```
linuxcnc /path/to/Mach3-to-LinuxCNC/config/mill-sim.ini
```

Then in AXIS: release E-stop (F1), machine on (F2), Home All, then jog or run a program. Z homes first, then X and Y together.

## Signal interface

These named signals are the contract between `mill_core.hal` and the hardware layer. A custom GUI should read machine state through them or through LinuxCNC's own pins, not through Mesa pin names. All of them are TRUE when the condition is active.

### Inputs (hardware layer writes)

| Signal | Meaning | Planned Mesa source | In the sim |
|---|---|---|---|
| `joint.0..2.motor-pos-fb` (pins) | Joint position feedback | 7i96S stepgen 0–2 position feedback | `x/y/z-pos-cmd` looped back |
| `x-switch`, `y-switch`, `z-switch` | Axis switch tripped (home and both limits) | 7i96S input, one per axis | Tripped past `SIM_SWITCH_MIN/MAX` |
| `estop-ext-fault` | Hardwired E-stop chain open | 7i96S input plus Mesa watchdog | Set by hand |
| `vfd-fault` | VFD fault; also trips E-stop | 7i96S input | Set by hand |
| `drive-alarm` | Any axis drive alarm | 7i96S input | Set by hand |
| `probe-in` | Probe touching | 7i96S input | Set by hand |
| `toolsetter-in` | Tool setter touching | 7i96S input | Set by hand |

Set a by-hand input from a terminal while the sim runs, for example `halcmd sets vfd-fault 1`, and back to `0` to clear.

### Outputs (hardware layer reads)

| Signal | Meaning | Planned Mesa output |
|---|---|---|
| `x-pos-cmd`, `y-pos-cmd`, `z-pos-cmd` | Joint position command | 7i96S stepgen 0–2 |
| `x-enable`, `y-enable`, `z-enable` | Joint enabled | Stepgen enable |
| `machine-on` | Machine on | Drive enable relay (2 A output) |
| `spindle-cw` | Spindle on, forward | VFD run (100 mA output) |
| `spindle-ccw` | Spindle on, reverse | VFD reverse or unused |
| `spindle-rpm-cmd` | Commanded rpm (absolute) | 7i96S isolated 0–10 V output |
| `coolant-flood` | M8 flood coolant on | Coolant relay (2 A output) |

The spindle cooling pump is not in HAL. It runs whenever the machine has power (decision D6 in the [retrofit plan](../docs/retrofit-plan.md)).

## Placeholders to replace after the Phase 1 survey

| Setting | Value now | Source |
|---|---|---|
| Travel X / Y / Z | 15.5 / 11.5 / 3.0 in | Vendor listing for the steel 3040, 300 × 400 × 80 mm. Which of X and Y is the 400 mm axis is assumed. |
| Max velocity | 0.65 in/s per axis | OEM Mach3 example, 1000 mm/min |
| Max acceleration | 15 in/s² per axis | OEM Mach3 example, 400 mm/s² |
| Steps per inch | 8128 (not used by the sim) | OEM 320 steps/mm; fits a 1605 ballscrew at 1/8 microstep |
| Spindle range | 6,000–24,000 rpm | Typical 2.2 kW water-cooled spindle |
| Spin-up delay | 3.0 s | Guess; measure on the VFD |
| Home switch positions | 0.05 in past each soft limit | Sim only; real positions come from commissioning |

## Known limits of the sim

- Positions follow commands exactly, so following error and step rates are not exercised.
- Spindle at-speed is a fixed delay after spindle on. It does not wait again after a speed change while running.
- The WHB04B pendant is not loaded. It needs the USB device and goes in with the machine config.
