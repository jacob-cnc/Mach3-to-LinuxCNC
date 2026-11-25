"""Backend factory: selects Live or Mock based on environment.

Copied from the lathe GUI (Industry-CAM-Engine hal/factory.py, dfb1c1a);
package renamed hal -> machine.

Usage:
    from machine.factory import get_backend
    backend = get_backend()
"""

import logging
from typing import Optional

from machine.interface import MachineBackend

logger = logging.getLogger(__name__)

_backend_instance: Optional[MachineBackend] = None


def get_backend(force_mock: bool = False) -> MachineBackend:
    """Get or create the singleton machine backend.

    Tries to import linuxcnc. If available and connected, returns LiveBackend.
    Otherwise falls back to MockBackend for offline development.
    """
    global _backend_instance

    if _backend_instance is not None:
        return _backend_instance

    if force_mock:
        logger.info("Machine: using MockBackend (forced)")
        from machine.mock_backend import MockBackend
        _backend_instance = MockBackend()
        return _backend_instance

    try:
        import linuxcnc  # noqa: F401
        from machine.live_backend import LiveBackend
        backend = LiveBackend()
        if backend.connected:
            logger.info("Machine: connected to LinuxCNC (LiveBackend)")
            _backend_instance = backend
            return _backend_instance
        logger.warning("Machine: linuxcnc module found but not connected, "
                       "falling back to MockBackend")
    except ImportError:
        logger.info("Machine: linuxcnc module not available, using MockBackend")
    except Exception as e:  # noqa: BLE001 - any failure means offline
        logger.warning("Machine: failed to connect to LinuxCNC (%s), using MockBackend", e)

    from machine.mock_backend import MockBackend
    _backend_instance = MockBackend()
    return _backend_instance


def reset_backend() -> None:
    """Reset the singleton (for testing only)."""
    global _backend_instance
    _backend_instance = None
