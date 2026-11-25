"""Machine control layer for the mill GUI.

The GUI never imports linuxcnc directly; it goes through this package.
Named ``machine`` (the lathe calls it ``hal``) so it cannot shadow
LinuxCNC's own ``hal`` Python module.

Usage:
    from machine import get_backend
    backend = get_backend()   # LiveBackend on LinuxCNC, MockBackend offline
"""

from machine.interface import MachineBackend, MachineState, AxisState, SpindleState
from machine.factory import get_backend

__all__ = ["get_backend", "MachineBackend", "MachineState", "AxisState", "SpindleState"]
