"""GUI test setup: headless Qt at the machine screen's 96 DPI."""
import os

import pytest

import sys

# Windows renders with real fonts without showing a window; headless Linux
# needs the offscreen platform, which has no fonts (size checks skip there).
if sys.platform != "win32" and not os.environ.get("DISPLAY"):
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_FONT_DPI", "96")

pytest.importorskip("PyQt5")


@pytest.fixture(scope="session")
def qapp():
    from PyQt5.QtWidgets import QApplication
    from gui.colors import STYLESHEET
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(STYLESHEET)
    return app


@pytest.fixture(autouse=True)
def inch_mode():
    """Every test starts in inch display mode (unit_state is a singleton)."""
    from gui.unit_state import unit_state, UnitMode
    if unit_state.mode != UnitMode.INCH:
        unit_state.toggle()
    yield
    if unit_state.mode != UnitMode.INCH:
        unit_state.toggle()
