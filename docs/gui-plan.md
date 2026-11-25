# Mill GUI plan

Status: design decided at a high level, 2026-11-25; no GUI code yet. The GUI is built ahead of the retrofit against the [sim config](../config/README.md), as the parallel track in the [retrofit plan](retrofit-plan.md).

## Decisions

| # | Topic | Decision (2026-11-25) |
|---|---|---|
| G1 | Relation to the lathe GUI | Separate codebase in this repo. Pieces are copied from the lathe GUI (jacob-cnc/Industry-CAM-Engine) and then diverge; no shared library. Every copied file is logged below with its lathe commit, so a lesson learned on one machine can be ported to the other by hand. |
| G2 | G-code source | No commercial CAM. Conversational ops are our own Python generators in the GUI, using QtPyVCP's `ops` as the starting point. External G-code runs through the Run tab; PureCutCNC is the first external CAM to trial, FreeCAD CAM the fallback. See the investigation below. |
| G3 | Probing | No probe yet. Design probing and tool-setter support following Probe Basic's approach so a probe can be added later. |
| G4 | Toolpath preview | Build both: a pixel-accurate 2D view with a plane selector (XY / XZ / YZ), like the lathe's coordinate map, and a 3D view. |
| G5 | Screen | Same 15.6 in panel as the lathe. |
| G6 | Conversational and DXF | Conversational programs built in the GUI from DXF geometry, ProtoTRAK style; externally generated G-code stays supported. DXF import is a copy of DXF-Tooling's `dxfclean` package, taken after DXF-Tooling PR #17 merges. |
| G7 | Licensing | No plans to distribute. Copy open-source code (QtPyVCP, NGCGUI, Probe Basic) wherever that integrates most cleanly, keeping the original license headers and logging the source like the lathe carryover. |
| G8 | Cutter compensation | Use LinuxCNC cutter compensation (G41/G42) for profile cuts: the program follows the part contour, and the tool diameter comes from the tool table. |

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

## G-code source investigation (G2), 2026-11-25

Requirements: conversational programming inside the GUI, built on DXF geometry the way ProtoTRAK's DXF option works; externally generated G-code still loads and runs.

| Candidate | What it is | Finding |
|---|---|---|
| [QtPyVCP `ops`](https://github.com/kcjengr/qtpyvcp/tree/main/src/qtpyvcp/ops) (behind Probe Basic's conversational screens) | About 270 lines of Python: facing (zig-zag with arc ramps) and hole ops (G81/G82/G83/G73, G84/G74 tapping, rigid tap, hole circle) emitting plain G-code | Small, readable, same language as the GUI. Covers only facing and holes. GPL. |
| NGCGUI ([library](https://github.com/LinuxCNC/linuxcnc/tree/master/nc_files/ngcgui_lib)) | Ships with LinuxCNC. Each op is a G-code subroutine (slot, hole circle, inside/outside quad and hex, quad pocket, helix ...); the GUI builds a form from the subroutine's parameter header and emits an `o<name> call` | Reliable (runs in LinuxCNC's own interpreter) but limited to fixed shapes: a subroutine can't take an arbitrary DXF profile. Ops are tedious to write in G-code. GPLv2. |
| [simple-gcode-generators](https://github.com/LinuxCNC/simple-gcode-generators) | Standalone Tkinter scripts (face, pocket, bolt circle, counterbore, engrave ...) | Python 2 (`from Tkinter import *`), last change April 2020. Useful only as algorithm reference. GPL-3.0. |
| dxf2gcode ([SourceForge](https://sourceforge.net/projects/dxf2gcode/files/)) | PyQt5 + PyOpenGL desktop app: DXF contours to G-code with cutter compensation and post-processors | Alive (new installer Nov 2026), but a whole app with its own DXF reader and extra tools (pstoedit, pdftops). Better as a reference than as code to embed. GPLv3. |
| [PureCutCNC](https://github.com/PureCutCNC/purecutcnc) | TypeScript browser/desktop 2.5D/3D CAD/CAM; DXF/SVG/STEP import; pockets, edge routes, drilling, V-carve; exports checked against LinuxCNC's parser | Most capable and very active, but young (created March 2026) and not embeddable in a Python GUI. Good external CAM. Apache-2.0. |
| FreeCAD CAM workbench | Full CAM inside FreeCAD, with a LinuxCNC post | Heavy dependency and steep learning curve; external use only. |

### Chosen approach (accepted 2026-11-25)

1. **Conversational engine: our own Python op generators in the GUI**, modeled on ProtoTRAK events (position/drill, bolt circle, line and arc mill with tool left/right/center, pocket, profile, face). QtPyVCP's `ops` is the pattern and the starting point for facing and holes. Output is plain LinuxCNC G-code (canned cycles for holes, G41/G42 for profile finishing), so a program runs, previews and edits like any other file.
2. **DXF importer: copied from DXF-Tooling's `dxfclean` package** (cleanup, spline-to-arc fitting, chaining, circle splitting, with its test suite). It already handles the CAD-export problems seen on the ProtoTRAK work (duplicate arcs, splines, broken chains). Copy after DXF-Tooling PR #17 (closed-spline crash fix) merges. Chained contours become profile/pocket events; circles become hole events.
3. **External G-code: unchanged Run tab path.** PureCutCNC is the first external CAM to trial; FreeCAD CAM is the fallback.
4. Not used: NGCGUI (can't take DXF geometry), simple-gcode-generators (Python 2), dxf2gcode as code (whole app).

### Cutter compensation rules (G8)

LinuxCNC's G41/G42 has requirements the generators must meet, and the GUI should check them before a program is written, with a plain-language message naming the feature and the fix:

- Comp turns on with a straight lead-in move longer than the tool radius, in G17, and turns off (G40) with a lead-out move clear of the part.
- An inside corner arc smaller than the tool radius, or a notch narrower than the tool, makes LinuxCNC stop with a gouge error. The pre-check catches this against the tool table diameter.

### Open design question: pocket roughing

A pocket's finish pass is a G41 profile of its contour. Roughing the inside still needs a clearing pattern. Two options to test on the sim:

1. Repeat the contour with G41.1 and a growing `D` value (tool diameter plus twice the step-over), so LinuxCNC computes each offset. No offset code in the GUI, but it fails where the offset would split the pocket into separate regions or exceed an inside arc radius, and it leaves a centre area for a final pass.
2. Compute roughing offsets in Python and cut them without comp, keeping comp for the finish pass only.

## Carryover log

Each copied file gets a row: source repo and path, source commit, mill path, and what changed. Sources include the lathe GUI, DXF-Tooling, and open-source projects (G7).

| Source file | Source commit | Mill file | Changes |
|---|---|---|---|
| — | — | — | Nothing copied yet |
