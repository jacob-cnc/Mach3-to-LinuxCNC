"""Mock backend for offline development on Windows.

Simulates LinuxCNC responses with simple state transitions: jogs move the
axes over time, MDI moves go to work coordinates, G10 L20 touch-off sets
work offsets, the spindle reports at-speed after the spin-up delay, and a
limit switch trip can be simulated. No dependencies beyond the standard
library.

Copied from the lathe GUI (Industry-CAM-Engine hal/mock_backend.py, dfb1c1a)
and adapted to X/Y/Z: per-axis lists, no diameter conversion, no compound
slide or MPG simulation; flood, software E-stop, work offsets, limit trip and
override added. Lathe difference worth noting: the lathe mock's touch_off
switched the ACTIVE work system; G10 L20 only writes the offset of the P
system, so this mock does that.
"""

import re
import time

from machine.interface import (
    MachineBackend, MachineState, AxisState, SpindleState,
    InterpState, TaskMode, TaskState, HomingState, SpindleDirection,
)
from machine.constants import LIMITS, HOMES, SPINUP_DELAY_S, WCS_NAMES

_AXES = 3
_WORD_RE = re.compile(r"([XYZ])\s*([-+]?\d*\.?\d+)")
_WCS_RE = re.compile(r"\bG5([4-9](?:\.[1-3])?)\b")
# Distance a tripped switch needs before it releases (sim switch sits 0.05 in
# past each soft limit, config/mill-sim.ini).
SWITCH_RELEASE = 0.05


class MockBackend(MachineBackend):
    """Offline mock: always "connected", starts machine-on and homed so the
    GUI is usable straight away.

    Does NOT simulate motion dynamics, following error or program execution
    (AUTO is a no-op).
    """

    def __init__(self):
        self._task_state = TaskState.ON
        self._task_mode = TaskMode.MANUAL
        self._interp_state = InterpState.IDLE

        self._pos = list(HOMES)                 # machine coordinates
        self._homed = [HomingState.HOMED] * _AXES
        self._jog_vel = [0.0] * _AXES           # units/sec, 0 = not jogging
        self._tripped = [0] * _AXES             # -1 min end, +1 max end, 0 clear
        self._override = False

        self._spindle_rpm = 0.0
        self._spindle_dir = SpindleDirection.STOPPED
        self._spindle_on_since = 0.0

        self._feed_override = 1.0
        self._rapid_override = 1.0
        self._spindle_override = 1.0

        self._tool = 0
        self._flood = False
        self._wcs = 1                           # 1 = G54 ... 9 = G59.3
        self._offsets = [[0.0] * _AXES for _ in range(len(WCS_NAMES))]
        self._error = ""

        self._last_poll = time.time()
        self._state = self._build_state()

    # -- Properties ---------------------------------------------------------

    @property
    def state(self) -> MachineState:
        return self._state

    @property
    def connected(self) -> bool:
        return True

    @property
    def is_offline(self) -> bool:
        return True

    @property
    def _on(self) -> bool:
        return self._task_state == TaskState.ON

    # -- Polling --------------------------------------------------------------

    def poll(self) -> None:
        now = time.time()
        dt = now - self._last_poll
        self._last_poll = now
        for i in range(_AXES):
            if self._jog_vel[i] and self._on:
                self._move_to(i, self._pos[i] + self._jog_vel[i] * dt)
        self._state = self._build_state()
        # Like LinuxCNC's error channel, a message is reported once.
        self._error = ""

    def _move_to(self, axis: int, target: float):
        """Move within travel. Soft limits hold once homed; a tripped switch
        releases after moving SWITCH_RELEASE away from its end."""
        lo, hi = LIMITS[axis]
        end = self._tripped[axis]
        if end:   # on the switch: the axis sits just past its soft limit
            lo, hi = lo - SWITCH_RELEASE, hi + SWITCH_RELEASE
        new = min(hi, max(lo, target))
        if new != target:          # reached the end of travel
            self._jog_vel[axis] = 0.0
        self._pos[axis] = new
        if end:
            switch = (LIMITS[axis][0] - SWITCH_RELEASE if end < 0
                      else LIMITS[axis][1] + SWITCH_RELEASE)
            if abs(new - switch) >= SWITCH_RELEASE - 1e-9:
                self._tripped[axis] = 0
                # Released at the soft limit: drop float step residue
                self._pos[axis] = min(LIMITS[axis][1], max(LIMITS[axis][0], new))
                if not any(self._tripped):
                    self._override = False

    # -- Mode control ---------------------------------------------------------

    def _set_mode(self, mode: TaskMode) -> bool:
        if not self._on:
            return False
        self._task_mode = mode
        return True

    def set_mode_manual(self) -> bool:
        return self._set_mode(TaskMode.MANUAL)

    def set_mode_mdi(self) -> bool:
        return self._set_mode(TaskMode.MDI)

    def set_mode_auto(self) -> bool:
        return self._set_mode(TaskMode.AUTO)

    # -- E-stop and power -----------------------------------------------------

    def estop(self) -> bool:
        self._task_state = TaskState.ESTOP
        self._stop_everything()
        self._error = "E-stop (simulated)"
        return True

    def estop_reset(self) -> bool:
        if self._task_state == TaskState.ESTOP:
            self._task_state = TaskState.ESTOP_RESET
            self._error = ""
            return True
        return False

    def machine_on(self) -> bool:
        if self._task_state in (TaskState.ESTOP_RESET, TaskState.OFF):
            self._task_state = TaskState.ON
            return True
        return False

    def machine_off(self) -> bool:
        if self._task_state == TaskState.ON:
            self._task_state = TaskState.OFF
        self._stop_everything()
        return True

    def _stop_everything(self):
        self._jog_vel = [0.0] * _AXES
        self.spindle_stop()
        self._flood = False

    # -- Limit switches -------------------------------------------------------

    def simulate_limit_trip(self, axis: int, end: int):
        """Test/offline hook: the axis hits its switch at ``end`` (-1 min,
        +1 max). As in LinuxCNC, motion stops and the machine turns off."""
        lo, hi = LIMITS[axis]
        self._pos[axis] = (lo - SWITCH_RELEASE) if end < 0 else (hi + SWITCH_RELEASE)
        self._tripped[axis] = -1 if end < 0 else 1
        self._error = f"Joint {axis} on limit switch error"
        if self._task_state == TaskState.ON:
            self._task_state = TaskState.OFF
        self._stop_everything()

    def override_limits(self) -> bool:
        if not any(self._tripped):
            return False
        self._override = True
        return True

    def _jog_allowed(self, axis: int, direction: float) -> bool:
        if not self._on or self._task_mode != TaskMode.MANUAL:
            return False
        end = self._tripped[axis]
        if any(self._tripped) and not self._override:
            return False
        # With override on, only jogging away from the tripped end is allowed.
        return not end or (direction > 0) == (end < 0)

    # -- Homing ---------------------------------------------------------------

    def home_axis(self, axis: int) -> bool:
        if not self._on:
            return False
        self._homed[axis] = HomingState.HOMED
        self._pos[axis] = HOMES[axis]
        self._tripped[axis] = 0
        return True

    def home_all(self) -> bool:
        if not self._on:
            return False
        for i in range(_AXES):
            self.home_axis(i)
        return True

    def unhome_axis(self, axis: int) -> bool:
        self._homed[axis] = HomingState.NOT_HOMED
        return True

    # -- Jogging ----------------------------------------------------------------

    def jog_continuous(self, axis: int, direction: float, velocity: float) -> bool:
        if not self._jog_allowed(axis, direction):
            return False
        self._jog_vel[axis] = abs(velocity) * (1.0 if direction > 0 else -1.0)
        return True

    def jog_increment(self, axis: int, direction: float, velocity: float,
                      distance: float) -> bool:
        if not self._jog_allowed(axis, direction):
            return False
        delta = abs(distance) * (1.0 if direction > 0 else -1.0)
        self._move_to(axis, self._pos[axis] + delta)
        return True

    def jog_stop(self, axis: int) -> bool:
        self._jog_vel[axis] = 0.0
        return True

    # -- MDI --------------------------------------------------------------------

    def mdi_command(self, command: str) -> bool:
        """Minimal parsing: G54..G59.3 select the work system, G10 L20
        touch-off, X/Y/Z words move there in work coordinates."""
        if not self._on:
            return False
        cmd = command.strip().upper()
        if cmd.startswith("G10"):
            return True
        m = _WCS_RE.search(cmd)
        if m:
            self._wcs = WCS_NAMES.index("G5" + m.group(1))
        offset = self._offsets[self._wcs]
        for letter, value in _WORD_RE.findall(cmd):
            i = "XYZ".index(letter)
            lo, hi = LIMITS[i]
            self._pos[i] = min(hi, max(lo, float(value) + offset[i]))
        return True

    # -- Spindle ----------------------------------------------------------------

    def _spindle_start(self, rpm: float, direction: SpindleDirection) -> bool:
        if not self._on:
            return False
        if self._spindle_dir != direction:
            self._spindle_on_since = time.time()
        self._spindle_rpm = abs(rpm)
        self._spindle_dir = direction
        return True

    def spindle_forward(self, rpm: float) -> bool:
        return self._spindle_start(rpm, SpindleDirection.FORWARD)

    def spindle_reverse(self, rpm: float) -> bool:
        return self._spindle_start(rpm, SpindleDirection.REVERSE)

    def spindle_stop(self) -> bool:
        self._spindle_rpm = 0.0
        self._spindle_dir = SpindleDirection.STOPPED
        return True

    # -- Coolant ----------------------------------------------------------------

    def set_flood(self, on: bool) -> bool:
        if on and not self._on:
            return False
        self._flood = bool(on)
        return True

    # -- Overrides --------------------------------------------------------------

    def set_feed_override(self, value: float) -> bool:
        self._feed_override = max(0.0, min(1.5, value))
        return True

    def set_rapid_override(self, value: float) -> bool:
        self._rapid_override = max(0.0, min(1.0, value))
        return True

    def set_spindle_override(self, value: float) -> bool:
        self._spindle_override = max(0.5, min(1.2, value))
        return True

    # -- Program control (no-ops) -----------------------------------------------

    def program_open(self, path: str) -> bool:
        return True

    def program_run(self, start_line: int = 0) -> bool:
        return self._on

    def program_pause(self) -> bool:
        return True

    def program_resume(self) -> bool:
        return True

    def program_stop(self) -> bool:
        return True

    # -- Tool and offsets -------------------------------------------------------

    def tool_change(self, tool_number: int) -> bool:
        if not self._on or tool_number < 0:
            return False
        self._tool = tool_number
        return True

    def touch_off(self, axis: int, value: float, system: int = 1) -> bool:
        """G10 L20 P<system>: the current position reads ``value`` in that
        system. Does not change the active system."""
        if not self._on or not 1 <= system < len(WCS_NAMES):
            return False
        self._offsets[system][axis] = self._pos[axis] - value
        return True

    # -- Internal ---------------------------------------------------------------

    def _build_state(self) -> MachineState:
        offset = self._offsets[self._wcs]
        axes = []
        for i in range(_AXES):
            lo, hi = LIMITS[i]
            axes.append(AxisState(
                position=self._pos[i] - offset[i],
                machine_position=self._pos[i],
                velocity=self._jog_vel[i],
                commanded=self._pos[i],
                homed=self._homed[i],
                at_limit=bool(self._tripped[i]),
                limit_end=self._tripped[i],
                enabled=self._on,
                min_limit=lo,
                max_limit=hi,
            ))
        speed = sum(v * v for v in self._jog_vel) ** 0.5
        running = self._spindle_dir != SpindleDirection.STOPPED
        spindle = SpindleState(
            commanded_speed=self._spindle_rpm * self._spindle_override,
            direction=self._spindle_dir,
            at_speed=running and time.time() - self._spindle_on_since >= SPINUP_DELAY_S,
            override=self._spindle_override,
        )
        return MachineState(
            task_state=self._task_state,
            task_mode=self._task_mode,
            interp_state=self._interp_state,
            program_busy=False,
            paused=self._interp_state == InterpState.PAUSED,
            x=axes[0], y=axes[1], z=axes[2],
            spindle=spindle,
            current_feed=speed * 60.0,
            feed_override=self._feed_override,
            rapid_override=self._rapid_override,
            active_gcodes=f"G17 G20 G40 G49 {WCS_NAMES[self._wcs]} G80 G90 G94",
            active_wcs=WCS_NAMES[self._wcs],
            work_origin=tuple(offset),
            tool_in_spindle=self._tool,
            estop_active=self._task_state == TaskState.ESTOP,
            machine_on=self._on,
            all_homed=all(h == HomingState.HOMED for h in self._homed),
            flood_on=self._flood,
            error_message=self._error,
        )
