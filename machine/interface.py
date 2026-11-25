"""Abstract interface for LinuxCNC backend communication.

Defines the contract between the GUI and the machine control layer.
All GUI code programs against this interface, never against linuxcnc directly.

The interface is designed around polling (call poll() each cycle) rather
than callbacks, matching LinuxCNC's stat.poll() pattern.

Copied from the lathe GUI (Industry-CAM-Engine hal/interface.py, dfb1c1a)
and adapted to the 3-axis mill: X/Y/Z axes, no diameter mode, commanded
spindle speed only (no spindle encoder), current feed rate added.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum


# =============================================================================
# State Enums
# =============================================================================

class InterpState(Enum):
    """LinuxCNC interpreter state."""
    IDLE = "idle"
    READING = "reading"
    PAUSED = "paused"
    WAITING = "waiting"


class TaskMode(Enum):
    """LinuxCNC task mode."""
    MANUAL = "manual"
    AUTO = "auto"
    MDI = "mdi"


class TaskState(Enum):
    """LinuxCNC task state."""
    ESTOP = "estop"
    ESTOP_RESET = "estop_reset"
    OFF = "off"
    ON = "on"


class HomingState(Enum):
    """Per-axis homing state."""
    NOT_HOMED = "not_homed"
    HOMING = "homing"
    HOMED = "homed"


class SpindleDirection(Enum):
    """Spindle rotation direction."""
    STOPPED = "stopped"
    FORWARD = "forward"
    REVERSE = "reverse"


# Axis indices used by every method that takes an ``axis`` argument.
AXIS_X = 0
AXIS_Y = 1
AXIS_Z = 2
AXIS_LETTERS = ("X", "Y", "Z")


# =============================================================================
# State Dataclasses
# =============================================================================

@dataclass(frozen=True)
class AxisState:
    """Current state of a single axis. All lengths in machine units (inch).

    position: WORK position (active G5x, G92 and tool offsets applied)
    machine_position: MACHINE (G53) position
    velocity: joint velocity (units/sec)
    commanded: commanded joint position (machine coordinates)
    following_error: joint following error
    homed: homing state
    at_limit: the axis's limit switch is tripped (hard limit, either end)
    enabled: joint enabled
    min_limit / max_limit: soft limits (machine coordinates)
    """
    position: float = 0.0
    machine_position: float = 0.0
    velocity: float = 0.0
    commanded: float = 0.0
    following_error: float = 0.0
    homed: HomingState = HomingState.NOT_HOMED
    at_limit: bool = False
    limit_end: int = 0              # -1 min-end switch, +1 max-end, 0 clear
    enabled: bool = False
    min_limit: float = 0.0
    max_limit: float = 0.0


@dataclass(frozen=True)
class SpindleState:
    """Current spindle state. The mill has no spindle encoder, so there is
    no measured speed: ``commanded_speed`` is what the VFD is told."""
    commanded_speed: float = 0.0    # RPM, override applied
    direction: SpindleDirection = SpindleDirection.STOPPED
    at_speed: bool = False          # spin-up delay elapsed (mill_core.hal)
    override: float = 1.0


@dataclass(frozen=True)
class MachineState:
    """Complete snapshot of machine state, rebuilt each poll cycle.

    Immutable (frozen) so it can be safely passed between threads.
    """
    # Task state
    task_state: TaskState = TaskState.OFF
    task_mode: TaskMode = TaskMode.MANUAL
    interp_state: InterpState = InterpState.IDLE
    # True while an AUTO program has anything left to do. NOT the same as
    # interp_state != IDLE: the interpreter reports IDLE once it has read the
    # whole file while motions are still queued (lathe, 2026-11-08).
    program_busy: bool = False
    paused: bool = False

    # Axes
    x: AxisState = field(default_factory=AxisState)
    y: AxisState = field(default_factory=AxisState)
    z: AxisState = field(default_factory=AxisState)

    # Spindle
    spindle: SpindleState = field(default_factory=SpindleState)

    # Feed
    current_feed: float = 0.0       # actual tool path speed, units/min
    feed_override: float = 1.0
    rapid_override: float = 1.0

    # Program
    program_file: str = ""
    current_line: int = 0
    motion_line: int = 0

    # Active modal codes
    active_gcodes: str = ""
    active_mcodes: str = ""
    active_wcs: str = "G54"
    # Machine position of the active work zero (G5x + G92), per axis
    work_origin: tuple = (0.0, 0.0, 0.0)

    # Tool
    tool_in_spindle: int = 0
    tool_length_offset: float = 0.0  # Z offset from G43

    # Flags
    estop_active: bool = False
    machine_on: bool = False
    all_homed: bool = False
    optional_stop: bool = False
    block_delete: bool = False
    flood_on: bool = False

    # Error/message
    error_message: str = ""

    def axis(self, index: int) -> AxisState:
        """AxisState by index (AXIS_X / AXIS_Y / AXIS_Z)."""
        return (self.x, self.y, self.z)[index]


# =============================================================================
# Abstract Backend Interface
# =============================================================================

class MachineBackend(ABC):
    """Abstract interface for machine control communication.

    Implementations:
        LiveBackend: real LinuxCNC connection via the linuxcnc module
        MockBackend: offline simulation for Windows development

    Usage pattern (in a GUI timer callback):
        backend.poll()
        state = backend.state
    """

    @property
    @abstractmethod
    def state(self) -> MachineState:
        """Current machine state snapshot (read after poll())."""

    @property
    @abstractmethod
    def connected(self) -> bool:
        """Whether the backend is connected to LinuxCNC."""

    @property
    def is_offline(self) -> bool:
        """True for the offline mock, so the GUI can label simulated data."""
        return False

    # -- Polling ----------------------------------------------------------

    @abstractmethod
    def poll(self) -> None:
        """Poll LinuxCNC for updated state (once per GUI timer cycle)."""

    # -- Mode control -----------------------------------------------------

    @abstractmethod
    def set_mode_manual(self) -> bool: ...

    @abstractmethod
    def set_mode_mdi(self) -> bool: ...

    @abstractmethod
    def set_mode_auto(self) -> bool: ...

    # -- E-stop and power -------------------------------------------------

    @abstractmethod
    def estop(self) -> bool:
        """Command LinuxCNC into E-stop (software E-stop button)."""

    @abstractmethod
    def estop_reset(self) -> bool: ...

    @abstractmethod
    def machine_on(self) -> bool: ...

    @abstractmethod
    def machine_off(self) -> bool: ...

    # -- Homing -----------------------------------------------------------

    @abstractmethod
    def home_axis(self, axis: int) -> bool: ...

    @abstractmethod
    def home_all(self) -> bool: ...

    @abstractmethod
    def unhome_axis(self, axis: int) -> bool: ...

    @abstractmethod
    def override_limits(self) -> bool:
        """Allow jogging off a tripped limit switch (one switch shares home
        and both limits per axis, so a trip needs this to back off)."""

    # -- Jogging (axis: AXIS_X / AXIS_Y / AXIS_Z, velocity in units/sec) ----

    @abstractmethod
    def jog_continuous(self, axis: int, direction: float, velocity: float) -> bool: ...

    @abstractmethod
    def jog_increment(self, axis: int, direction: float, velocity: float,
                      distance: float) -> bool: ...

    @abstractmethod
    def jog_stop(self, axis: int) -> bool: ...

    # -- MDI ----------------------------------------------------------------

    @abstractmethod
    def mdi_command(self, command: str) -> bool: ...

    # -- Spindle (VFD) ------------------------------------------------------

    @abstractmethod
    def spindle_forward(self, rpm: float) -> bool: ...

    @abstractmethod
    def spindle_reverse(self, rpm: float) -> bool: ...

    @abstractmethod
    def spindle_stop(self) -> bool: ...

    # -- Coolant --------------------------------------------------------------

    @abstractmethod
    def set_flood(self, on: bool) -> bool: ...

    # -- Overrides ------------------------------------------------------------

    @abstractmethod
    def set_feed_override(self, value: float) -> bool: ...

    @abstractmethod
    def set_rapid_override(self, value: float) -> bool: ...

    @abstractmethod
    def set_spindle_override(self, value: float) -> bool: ...

    # -- Program control ------------------------------------------------------

    @abstractmethod
    def program_open(self, path: str) -> bool: ...

    @abstractmethod
    def program_run(self, start_line: int = 0) -> bool: ...

    @abstractmethod
    def program_pause(self) -> bool: ...

    @abstractmethod
    def program_resume(self) -> bool: ...

    @abstractmethod
    def program_stop(self) -> bool: ...

    # -- Tool -----------------------------------------------------------------

    @abstractmethod
    def tool_change(self, tool_number: int) -> bool:
        """Tn M6 then G43 (manual tool change prompt comes from HAL/GUI)."""

    # -- Work offsets -----------------------------------------------------------

    @abstractmethod
    def touch_off(self, axis: int, value: float, system: int = 1) -> bool:
        """Set the work offset so the current position reads ``value``.

        system: 1 = G54, 2 = G55, ... 9 = G59.3
        """
