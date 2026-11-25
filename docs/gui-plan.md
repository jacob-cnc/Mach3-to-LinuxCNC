# Mill GUI plan

Status: ideation, 2026-11-25. The GUI is built ahead of the retrofit against the [sim config](../config/README.md), as the parallel track in the [retrofit plan](retrofit-plan.md).

## Decisions

| # | Topic | Decision (2026-11-25) |
|---|---|---|
| G1 | Relation to the lathe GUI | Separate codebase in this repo. Pieces are copied from the lathe GUI (jacob-cnc/Industry-CAM-Engine) and then diverge; no shared library. Every copied file is logged below with its lathe commit, so a lesson learned on one machine can be ported to the other by hand. |
| G2 | G-code source | Undecided. No commercial CAM. Investigate open-source CAM and conversational options first; building or modifying a conversational system comes after. |
| G3 | Probing | No probe yet. Design probing and tool-setter support following Probe Basic's approach so a probe can be added later. |
| G4 | Toolpath preview | Build both: a pixel-accurate 2D view with a plane selector (XY / XZ / YZ), like the lathe's coordinate map, and a 3D view. |
| G5 | Screen | Same 15.6 in panel as the lathe. |

## Lathe features, sorted

| Lathe part | Mill | Notes |
|---|---|---|
| Shell: status bar, colors, unit state, error dialog, numeric fields, offline-mode launcher | Copy | Status bar DRO becomes X/Y/Z |
| HAL backend (live and mock) | Copy and adapt | 3 joints; drop lathe quirks (swapped stepgens, radius X) |
| Edit tab | Copy | |
| Run tab | Copy and adapt | Preview replaced per G4 |
| Manual tab | Copy and adapt | Touch-off becomes X/Y/Z work offsets; compound slide dropped |
| Tools tab | Copy and adapt | Mill fields: diameter, length offset, type, flutes, stickout |
| Setup: HAL Monitor | Copy | |
| Setup: Commission | Copy and adapt | Mill checklist steps |
| Setup: Tuning | Replace | Velocity and acceleration testing for open-loop steppers, step timing, backlash |
| Help and G-code reference | Copy and adapt | Mill topics and codes |
| Program tab (lathe CAM), Debug tab | Drop | Turning-specific |

## New for the mill

1. Work offsets page (G54–G59.3).
2. Probing routines: edge, corner, bore/boss, Z surface (G3).
3. Tool change prompt and tool length measurement on a tool setter (G3).
4. Pre-run fit check: program extents in the active work offset against soft limits and stock; tools called but missing from the table.
5. Limit override flow for backing off a tripped shared home/limit switch.
6. Fault panel with plain-language messages: E-stop chain, VFD fault, drive alarm, limit trip.
7. Spindle commanded rpm and a warm-up routine.
8. WHB04B pendant status.
9. Flood coolant toggle.

## Preview approach (G4)

- **One path source for both views.** On the LinuxCNC PC, use LinuxCNC's own interpreter (the Python `gcode` module that AXIS's preview uses) to turn a program into moves. It already handles canned cycles, subroutines, cutter compensation and tool length offsets, so the preview matches what the machine will do. Offline on Windows that module isn't available, so a simpler parser is the fallback and the GUI says so.
- **2D view:** pyqtgraph, as on the lathe, with a plane selector.
- **3D view:** start with pyqtgraph's OpenGL module (same library, lightest addition) for toolpath lines, machine envelope, stock box and tool position. VTK (used by QtPyVCP-based GUIs such as Probe Basic) is the option if material-removal display is wanted later.

## Probing approach (G3), following Probe Basic

Probe Basic is GPLv2, built on QtPyVCP, and runs on LinuxCNC 2.9 / 2.10 on Debian 12 ([repo](https://github.com/kcjengr/probe_basic)). The part worth following is that its probing logic lives in G-code subroutines, not in the GUI:

- The GUI collects parameters and calls an O-word subroutine through MDI.
- The subroutine probes with G38.x and writes results to parameters or work offsets.
- Tool-setter measurement hangs off an M6 remap, so it runs the same from a program or from MDI.

Our GUI can call the same kind of subroutines without using QtPyVCP. If Probe Basic's subroutine files are copied in, they stay GPLv2 with their headers intact.

## G-code source investigation (G2)

Candidates to look at, then trial one or two on the sim with a real part:

| Candidate | What it is | Check |
|---|---|---|
| [PureCutCNC](https://purecutcnc.github.io/) | Open-source (Apache-2.0) 2.5D/3D CAD/CAM, desktop or browser. CAM only. States its exports are checked against LinuxCNC's parser. | Aimed at routers and plasma; check metal-milling suitability, tool library and post output |
| FreeCAD CAM workbench | Mature open-source CAM inside FreeCAD, with a LinuxCNC post | Learning curve; output quality for small metal parts |
| NGCGUI | Ships with LinuxCNC: forms around O-word subroutines, embeddable in a GUI | Basis for our own conversational screens? |
| [LinuxCNC simple-gcode-generators](https://github.com/LinuxCNC/simple-gcode-generators) | Python scripts for simple ops (facing, pockets, bolt circles) | Reuse as conversational ops |
| Probe Basic conversational ops | Conversational screens in Probe Basic | Which ops, and how they generate code |
| dxf2gcode | Open-source 2D DXF to G-code | Pairing with DXF-Tooling output |

## Carryover log

Each file copied from the lathe GUI gets a row: lathe path, lathe commit, mill path, and what changed.

| Lathe file | Lathe commit | Mill file | Changes |
|---|---|---|---|
| — | — | — | Nothing copied yet |
