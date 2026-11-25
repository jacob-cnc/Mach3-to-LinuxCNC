"""Live backend connecting to LinuxCNC via its Python API.

Only importable on a PC with LinuxCNC installed; machine/factory.py guards
the import.

Copied from the lathe GUI (Industry-CAM-Engine hal/live_backend.py, dfb1c1a)
and cut down for the mill. Kept from the lathe: error-channel draining,
program_busy (interp IDLE is not "done"), program_open without a mode switch,
the ensure-mode rules, G-code list formatting. Dropped: compound slide HAL
component, MPG mux, diameter conversion, restore_lathe_modes, spindle
encoder feedback. Added: Y axis, joint-vs-teleop jogging before homing,
flood coolant, software E-stop, current feed, active work offset.

NOT YET RUN against LinuxCNC. First check: the sim config in config/.
"""

import logging

import linuxcnc

try:  # LinuxCNC's own hal module; only used to read spindle at-speed
    import hal as linuxcnc_hal
except ImportError:  # pragma: no cover - outside LinuxCNC
    linuxcnc_hal = None

from machine.interface import (
    MachineBackend, MachineState, AxisState, SpindleState,
    InterpState, TaskMode, TaskState, HomingState, SpindleDirection,
    AXIS_LETTERS,
)
from machine.constants import WCS_NAMES

logger = logging.getLogger(__name__)

_AXES = 3

_TASK_STATE_MAP = {
    linuxcnc.STATE_ESTOP: TaskState.ESTOP,
    linuxcnc.STATE_ESTOP_RESET: TaskState.ESTOP_RESET,
    linuxcnc.STATE_OFF: TaskState.OFF,
    linuxcnc.STATE_ON: TaskState.ON,
}

_TASK_MODE_MAP = {
    linuxcnc.MODE_MANUAL: TaskMode.MANUAL,
    linuxcnc.MODE_AUTO: TaskMode.AUTO,
    linuxcnc.MODE_MDI: TaskMode.MDI,
}

_INTERP_MAP = {
    linuxcnc.INTERP_IDLE: InterpState.IDLE,
    linuxcnc.INTERP_READING: InterpState.READING,
    linuxcnc.INTERP_PAUSED: InterpState.PAUSED,
    linuxcnc.INTERP_WAITING: InterpState.WAITING,
}


class LiveBackend(MachineBackend):
    """Real LinuxCNC backend (NML via the linuxcnc module).

    Requires LinuxCNC to be running (launched from the INI file).
    """

    def __init__(self):
        self._stat = linuxcnc.stat()
        self._cmd = linuxcnc.command()
        self._error = linuxcnc.error_channel()
        self._state = MachineState()
        self._connected = False
        self._last_raw_state = None
        try:
            self._stat.poll()
            self._connected = True
        except linuxcnc.error:
            self._connected = False

    # -- Properties ---------------------------------------------------------

    @property
    def state(self) -> MachineState:
        return self._state

    @property
    def connected(self) -> bool:
        return self._connected

    # -- Polling --------------------------------------------------------------

    def poll(self) -> None:
        try:
            self._stat.poll()
            self._connected = True
        except linuxcnc.error:
            self._connected = False
            return

        # Drain every queued error message; report the latest.
        error_msg = ""
        try:
            while True:
                err = self._error.poll()
                if not err:
                    break
                kind, text = err
                error_msg = text
                logger.error("LinuxCNC error [%s]: %s", kind, text)
        except Exception as e:  # noqa: BLE001
            logger.warning("Error channel poll failed: %s", e)

        s = self._stat
        if s.task_state != self._last_raw_state:
            logger.info("Task state: %s -> %s", self._last_raw_state, s.task_state)
            self._last_raw_state = s.task_state

        task_state = _TASK_STATE_MAP.get(s.task_state, TaskState.OFF)

        axes = []
        for i in range(_AXES):
            joint = s.joint[i] if len(s.joint) > i else {}
            work = (s.actual_position[i] - s.g5x_offset[i]
                    - s.g92_offset[i] - s.tool_offset[i])
            axes.append(AxisState(
                position=work,
                machine_position=s.actual_position[i],
                velocity=joint.get("velocity", 0.0),
                commanded=joint.get("output", 0.0),
                following_error=joint.get("ferror_current", 0.0),
                homed=HomingState.HOMED if s.homed[i] else HomingState.NOT_HOMED,
                at_limit=bool(s.limit[i]),
                enabled=bool(joint.get("enabled", False)),
                min_limit=joint.get("min_position_limit", 0.0),
                max_limit=joint.get("max_position_limit", 0.0),
            ))

        sp = s.spindle[0] if len(s.spindle) > 0 else {}
        direction = sp.get("direction", 0)
        if direction > 0:
            spindle_dir = SpindleDirection.FORWARD
        elif direction < 0:
            spindle_dir = SpindleDirection.REVERSE
        else:
            spindle_dir = SpindleDirection.STOPPED
        spindle = SpindleState(
            # stat "speed" is the commanded speed; there is no encoder.
            commanded_speed=abs(sp.get("speed", 0.0)) * sp.get("override", 1.0),
            direction=spindle_dir,
            at_speed=self._read_bit("spindle.0.at-speed"),
            override=sp.get("override", 1.0),
        )

        # stat.gcodes: element 0 is the line number; the rest are modal codes
        # x10 (171 = G17.1) or -1 when the group is unset.
        gcodes = " ".join(
            f"G{g // 10}" if g % 10 == 0 else f"G{g // 10}.{g % 10}"
            for g in s.gcodes[1:] if g >= 0
        )
        mcodes = " ".join(f"M{m}" for m in s.mcodes[1:] if m >= 0)
        wcs_index = s.g5x_index if 0 < s.g5x_index < len(WCS_NAMES) else 1

        self._state = MachineState(
            task_state=task_state,
            task_mode=_TASK_MODE_MAP.get(s.task_mode, TaskMode.MANUAL),
            interp_state=_INTERP_MAP.get(s.interp_state, InterpState.IDLE),
            program_busy=self._program_busy(s),
            paused=bool(s.paused),
            x=axes[0], y=axes[1], z=axes[2],
            spindle=spindle,
            current_feed=s.current_vel * 60.0,
            feed_override=s.feedrate,
            rapid_override=s.rapidrate,
            program_file=s.file or "",
            current_line=s.current_line,
            motion_line=s.motion_line,
            active_gcodes=gcodes,
            active_mcodes=mcodes,
            active_wcs=WCS_NAMES[wcs_index],
            tool_in_spindle=s.tool_in_spindle,
            tool_length_offset=s.tool_offset[2],
            estop_active=task_state == TaskState.ESTOP,
            machine_on=task_state == TaskState.ON,
            all_homed=all(s.homed[i] for i in range(_AXES)),
            optional_stop=bool(s.optional_stop),
            block_delete=bool(s.block_delete),
            flood_on=bool(s.flood),
            error_message=error_msg,
        )

    @staticmethod
    def _read_bit(name: str) -> bool:
        if linuxcnc_hal is None or not hasattr(linuxcnc_hal, "get_value"):
            return False
        try:
            return bool(linuxcnc_hal.get_value(name))
        except Exception:  # noqa: BLE001 - pin missing or HAL not ready
            return False

    @staticmethod
    def _program_busy(s) -> bool:
        """AUTO program still has work: interpreter, task execution, motion
        queue, pause, or an executing NML command. Interp IDLE alone is not
        enough (it goes IDLE once the whole file is read, before motion ends)."""
        if s.task_mode != linuxcnc.MODE_AUTO:
            return False
        return (s.interp_state != linuxcnc.INTERP_IDLE
                or s.exec_state != linuxcnc.EXEC_DONE
                or s.queue > 0
                or bool(s.paused)
                or s.state == linuxcnc.RCS_EXEC)

    # -- Mode control ---------------------------------------------------------

    def _ensure_mode(self, mode) -> bool:
        """Switch to mode if not already there. Never interrupts a program."""
        self._stat.poll()
        if self._stat.task_mode == mode:
            return True
        if self._program_busy(self._stat):
            return False
        if self._stat.interp_state != linuxcnc.INTERP_IDLE:
            # MDI stuck non-idle (e.g. after a tool change): safe to abort
            self._cmd.abort()
            self._cmd.wait_complete()
        self._cmd.mode(mode)
        self._cmd.wait_complete()
        return True

    def set_mode_manual(self) -> bool:
        return self._ensure_mode(linuxcnc.MODE_MANUAL)

    def set_mode_mdi(self) -> bool:
        return self._ensure_mode(linuxcnc.MODE_MDI)

    def set_mode_auto(self) -> bool:
        return self._ensure_mode(linuxcnc.MODE_AUTO)

    # -- E-stop and power -----------------------------------------------------

    def _set_state(self, state, label: str) -> bool:
        logger.info("%s: sending %s", label, state)
        try:
            self._cmd.state(state)
            return True
        except linuxcnc.error as e:
            logger.error("%s failed: %s", label, e)
            return False

    def estop(self) -> bool:
        return self._set_state(linuxcnc.STATE_ESTOP, "estop")

    def estop_reset(self) -> bool:
        return self._set_state(linuxcnc.STATE_ESTOP_RESET, "estop_reset")

    def machine_on(self) -> bool:
        return self._set_state(linuxcnc.STATE_ON, "machine_on")

    def machine_off(self) -> bool:
        return self._set_state(linuxcnc.STATE_OFF, "machine_off")

    # -- Homing ---------------------------------------------------------------

    def _home(self, joint: int) -> bool:
        try:
            if not self._ensure_mode(linuxcnc.MODE_MANUAL):
                return False
            self._cmd.teleop_enable(0)   # homing is a joint-mode operation
            self._cmd.wait_complete()
            self._cmd.home(joint)
            return True
        except linuxcnc.error:
            return False

    def home_axis(self, axis: int) -> bool:
        return self._home(axis)          # trivkins: joint index == axis index

    def home_all(self) -> bool:
        return self._home(-1)            # -1 = HOME_SEQUENCE order from the INI

    def unhome_axis(self, axis: int) -> bool:
        try:
            if not self._ensure_mode(linuxcnc.MODE_MANUAL):
                return False
            self._cmd.teleop_enable(0)
            self._cmd.wait_complete()
            self._cmd.unhome(axis)
            return True
        except linuxcnc.error:
            return False

    # -- Jogging ----------------------------------------------------------------

    def _prepare_jog(self) -> bool:
        """MANUAL mode, then joint jogging before homing and axis (teleop)
        jogging after, as AXIS does. Returns the joint flag for cmd.jog."""
        if self._stat.task_state != linuxcnc.STATE_ON:
            raise linuxcnc.error("machine is not on")
        if not self._ensure_mode(linuxcnc.MODE_MANUAL):
            raise linuxcnc.error("program active")
        homed = all(self._stat.homed[i] for i in range(_AXES))
        want = linuxcnc.TRAJ_MODE_TELEOP if homed else linuxcnc.TRAJ_MODE_FREE
        if self._stat.motion_mode != want:
            self._cmd.teleop_enable(1 if homed else 0)
            self._cmd.wait_complete()
        return not homed

    def jog_continuous(self, axis: int, direction: float, velocity: float) -> bool:
        try:
            joint_flag = self._prepare_jog()
            vel = abs(velocity) * (1.0 if direction > 0 else -1.0)
            self._cmd.jog(linuxcnc.JOG_CONTINUOUS, joint_flag, axis, vel)
            return True
        except linuxcnc.error:
            return False

    def jog_increment(self, axis: int, direction: float, velocity: float,
                      distance: float) -> bool:
        try:
            joint_flag = self._prepare_jog()
            dist = abs(distance) * (1.0 if direction > 0 else -1.0)
            self._cmd.jog(linuxcnc.JOG_INCREMENT, joint_flag, axis, abs(velocity), dist)
            return True
        except linuxcnc.error:
            return False

    def jog_stop(self, axis: int) -> bool:
        try:
            self._stat.poll()
            homed = all(self._stat.homed[i] for i in range(_AXES))
            self._cmd.jog(linuxcnc.JOG_STOP, not homed, axis)
            return True
        except linuxcnc.error:
            return False

    # -- MDI --------------------------------------------------------------------

    def _mdi(self, command: str, timeout: float = 5.0) -> bool:
        try:
            if not self._ensure_mode(linuxcnc.MODE_MDI):
                return False
            self._cmd.mdi(command)
            self._cmd.wait_complete(timeout)
            return True
        except linuxcnc.error:
            return False

    def mdi_command(self, command: str) -> bool:
        ok = self._mdi(command)
        if ok:
            self._ensure_mode(linuxcnc.MODE_MANUAL)
        return ok

    # -- Spindle ----------------------------------------------------------------

    def spindle_forward(self, rpm: float) -> bool:
        return self._mdi(f"M3 S{rpm:.0f}")

    def spindle_reverse(self, rpm: float) -> bool:
        return self._mdi(f"M4 S{rpm:.0f}")

    def spindle_stop(self) -> bool:
        return self._mdi("M5")

    # -- Coolant ----------------------------------------------------------------

    def set_flood(self, on: bool) -> bool:
        try:
            self._cmd.flood(linuxcnc.FLOOD_ON if on else linuxcnc.FLOOD_OFF)
            return True
        except linuxcnc.error:
            return False

    # -- Overrides --------------------------------------------------------------

    def set_feed_override(self, value: float) -> bool:
        try:
            self._cmd.feedrate(value)
            return True
        except linuxcnc.error:
            return False

    def set_rapid_override(self, value: float) -> bool:
        try:
            self._cmd.rapidrate(value)
            return True
        except linuxcnc.error:
            return False

    def set_spindle_override(self, value: float) -> bool:
        try:
            self._cmd.spindleoverride(value, 0)
            return True
        except linuxcnc.error:
            return False

    # -- Program control --------------------------------------------------------

    def program_open(self, path: str) -> bool:
        """Open a program WITHOUT changing task mode (as stock AXIS does);
        AUTO is entered only at cycle start."""
        try:
            self._stat.poll()
            if (self._stat.interp_state != linuxcnc.INTERP_IDLE
                    or self._program_busy(self._stat)):
                return False
            self._cmd.task_plan_synch()
            self._cmd.wait_complete()
            self._cmd.program_open(path)
            return True
        except linuxcnc.error:
            return False

    def program_run(self, start_line: int = 0) -> bool:
        try:
            if not self._ensure_mode(linuxcnc.MODE_AUTO):
                return False
            self._cmd.auto(linuxcnc.AUTO_RUN, start_line)
            return True
        except linuxcnc.error:
            return False

    def program_pause(self) -> bool:
        try:
            self._cmd.auto(linuxcnc.AUTO_PAUSE)
            return True
        except linuxcnc.error:
            return False

    def program_resume(self) -> bool:
        try:
            self._cmd.auto(linuxcnc.AUTO_RESUME)
            return True
        except linuxcnc.error:
            return False

    def program_stop(self) -> bool:
        try:
            self._cmd.abort()
            return True
        except linuxcnc.error:
            return False

    # -- Tool and offsets -------------------------------------------------------

    def tool_change(self, tool_number: int) -> bool:
        # The operator answers the manual tool change prompt, so allow time.
        ok = self._mdi(f"T{tool_number} M6", timeout=120.0) and self._mdi("G43")
        self._ensure_mode(linuxcnc.MODE_MANUAL)
        return ok

    def touch_off(self, axis: int, value: float, system: int = 1) -> bool:
        ok = self._mdi(f"G10 L20 P{system} {AXIS_LETTERS[axis]}{value:.6f}")
        self._ensure_mode(linuxcnc.MODE_MANUAL)
        return ok
