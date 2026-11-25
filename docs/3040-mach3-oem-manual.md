# 3040 3-axis Steel Structure 2200W CNC Machine — Mach3 USB version

Manufacturer: Scotle Technology Group Limited / ChinaCNCzone.
Websites: www.chinacnczone.com and www.china-cncrouter.com.

Converted from the owner-supplied 22-page OEM manual. Screenshot settings are transcribed below; photographs and screenshots are not embedded. This is a legacy Mach3 reference, not a LinuxCNC wiring specification.

## Part 1 — Assembly (pages 3–6)

### Packing list

| Item | Quantity |
|---|---:|
| Water pump | 2 |
| Pump mounting feet | 8 |
| Pump inlet | 2 |
| Clamping tool | 6 |
| Power cable | 1 |
| USB cable | 1 |
| Spanner | 2 |
| Water sink outlet pipe | 1 |
| Engraving/milling bits | 5 |
| Water container | 2 |

Included cutters: 4F × 6 × 6 × 19 × 63 mm white steel milling bit; 4F × 6 × 6 × 15 × 50 mm tungsten steel milling bit; 3.175 mm × 20° engraving bits with 0.1, 0.2 and 0.3 tips.

1. Unpack the machine from its wooden crate.
2. Connect machine cables to the controller box and connect the USB cable to the computer.
3. Connect the water pumps and tubing. One pump cools the spindle; the other supplies cutting-tool coolant.

The photographs show the rear controller connections, drain hose, spindle coolant hoses and separate water containers.

## Part 2 — Mach3 installation and settings

### 1. Download Mach3 (page 6)

Obtain Mach3 from the vendor website, supplied CD or seller.

### 2. Install Mach3 (pages 7–8)

- Deselect the parallel port driver during installation.
- Connect the USB controller.
- Copy `NcUsbPod.dll` from the USB card driver folder into the Mach3 `PlugIns` directory.
- The illustrated driver folder is version 2.38.8.
- The manual instructs the operator to clear the Mach3 reset condition before operation.

### 3. Mach3 software settings (pages 8–18)

#### Method 1 — Supplied configuration

Copy the supplied `Mach3Mill.xml` profile into the Mach3 installation folder. The illustration references the four-axis MK4 configuration.

#### Method 2 — Manual configuration

Open Config > Ports and Pins.

Page 10 shows both parallel ports disabled, with example addresses 0x378 and 0x278 and a 25 kHz kernel selection.

| Axis | Enabled | Step pin | Direction pin | Direction active low | Step active low | Step/dir port |
|---|---|---:|---:|---|---|---|
| X | Yes | 2 | 6 | Yes | Yes | 1 |
| Y | Yes | 3 | 7 | Yes | Yes | 1 |
| Z | Yes | 4 | 8 | Yes | Yes | 1 |
| A | No | 5 | 9 | Yes | Yes | 1 |
| B | No | 10 | 11 | Yes | Yes | 0 |
| C | No | 12 | 13 | Yes | Yes | 0 |
| Spindle | Yes | 0 | 0 | Yes | Yes | 0 |

#### Input signals — first example (page 11)

| Signal | Enabled | Port | Pin | Active low |
|---|---|---:|---:|---|
| X home | Yes | 1 | 0 | Yes |
| Y home | Yes | 1 | 1 | Yes |
| Z home | Yes | 1 | 2 | Yes |
| Probe | Yes | 1 | 4 | Yes |
| E-stop | Yes | 1 | 5 | Yes |

Positive and negative XYZ limits are disabled in this screenshot. E-stop hotkey is 46.

#### Output signals — first example (page 12)

Outputs 1–6 enabled, port 1, pins 0–5 respectively, active low. Enable 4–6 and charge pump outputs are disabled in the displayed portion.

#### Motor tuning (pages 12–14)

Open Config > Motor Tuning. The manual states that XYZ settings are identical.

| Parameter | Screenshot value |
|---|---:|
| Steps per unit | 320 |
| Velocity (units/min) | 1000.2 |
| Acceleration (units/s²) | 400 |
| Acceleration (g) | 0.0407904 |
| Step pulse field | 0 |
| Direction pulse field | 0 |

The screenshots show X and Z. The units selector is not shown; verify native units before conversion.

#### Input signals — second example (pages 14–15)

The manual states that the machine does not support motor home/soft limits in this section.

| Signal | Enabled | Port | Pin | Active low |
|---|---|---:|---:|---|
| X++ and X-- | Yes | 2 | 1 | Yes |
| Y++ and Y-- | Yes | 2 | 2 | Yes |
| Z++ and Z-- | Yes | 2 | 3 | Yes |
| X home | No | 2 | 1 | Yes |
| Y home | No | 2 | 2 | Yes |
| Z home | No | 2 | 3 | Yes |
| Probe | Yes | 2 | 10 | Yes |
| E-stop | Yes | 2 | 16 | Yes |

#### Output signals — second example (page 16)

| Signal | Enabled | Port | Pin | Active low |
|---|---|---:|---:|---|
| Enable 1 | Yes | 2 | 16 | Yes |
| Enable 2 | Yes | 2 | 15 | Yes |
| Enable 3 | Yes | 2 | 13 | Yes |
| Enable 4 | Yes | 2 | 14 | Yes |

Enable 5/6 and outputs 1–4 are disabled in the illustrated settings.

#### Spindle control (page 17)

In Spindle Setup, the screenshot selects Use Spindle Motor Output and PWM Control rather than Step/Dir Motor. PWM base frequency appears to be 10; the minimum PWM field is not sufficiently clear to transcribe confidently. The screenshot is not a physical VFD terminal map.

#### USB motion card configuration (pages 17–18)

Open Config > Config Plugins. Select the configuration for NcUsbPod-XHC-Mach3-USB-Motion-Card.

The illustrated XHC configuration is version 2.38.8, with single-stage homing, software limits disabled, pull-off fields of 5 for the axes, and a G-code time buffer of 512 ms. Pulse per rotate shows 4.

When opening Mach3, select NcUsbPod-XHC-Mach3-USB-Motion-Card as the motion device. The manual shows the option to remember this choice.

## Part 3 — FAQ (pages 19–22)

### 1. Incorrect axis direction

The manufacturer instructs changing the direction active-low setting for the affected axis. The illustrated motor outputs use the same step/direction pin assignments described above.

### 2. USB motion card detection

Check the USB connection, VFD grounding and electrical filtering on the VFD input supply to reduce interference.

### 3. Referencing all axes home

The FAQ instructs enabling X, Y and Z home signals, checking the plugin configuration and selecting single-stage homing, then using Ref All Home.

The screenshots on page 20 show positive and negative limits and home inputs enabled, port 1, pins 0 (X), 1 (Y), 2 (Z), active low.

### 4. Manual limit-switch reset

The manual states that each of X, Y and Z has two limit switches. When an axis reaches a limit switch, the machine stops and the controller reset indication turns red. The manufacturer describes switching off the machine, moving the axis away from the switch and resetting before restarting. Page 22 shows photographs of the switches and their mounting locations.

## Conversion notes — not OEM instructions

- The manual contains incompatible examples for home/limit, probe, E-stop and enable mapping. Do not assume any is the installed machine configuration.
- Mach3 USB logical port/pin numbers are not physical Mesa terminal numbers.
- The 320 steps/unit example requires confirmation of native units, screw lead and drive microstepping.
- Identify actual drives, VFD, electrical levels, switch wiring and safe inhibit circuits before designing LinuxCNC HAL/INI.
- The legacy manual is not a validated safety or commissioning procedure. Isolate hazardous energy before accessing wiring or manually moving machinery.
