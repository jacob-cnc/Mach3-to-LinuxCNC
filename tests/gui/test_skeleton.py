"""Skeleton checks: mock backend invariants, status bar display, main window.

Invariants rather than fixed examples: positions must stay inside the soft
limits for any jog, any display value must round-trip through the unit
conversion, and the ribbon must fit the machine's 1920 px screen.
"""
import random

import pytest

from machine.constants import LIMITS, HOMES
from machine.interface import AXIS_X, AXIS_Y, AXIS_Z, TaskState
from machine.mock_backend import MockBackend


# ---------------------------------------------------------------------------
# Mock backend
# ---------------------------------------------------------------------------

def _advance(backend, seconds):
    backend._last_poll -= seconds   # pretend time passed
    backend.poll()


@pytest.mark.parametrize("seed", range(20))
def test_mock_jogs_never_leave_soft_limits(seed):
    rng = random.Random(seed)
    b = MockBackend()
    for _ in range(40):
        axis = rng.choice((AXIS_X, AXIS_Y, AXIS_Z))
        if rng.random() < 0.5:
            b.jog_continuous(axis, rng.choice((-1, 1)), rng.uniform(0.01, 5.0))
            _advance(b, rng.uniform(0.0, 30.0))
            b.jog_stop(axis)
        else:
            b.jog_increment(axis, rng.choice((-1, 1)), 1.0, rng.uniform(0.0, 50.0))
            b.poll()
        for i, (lo, hi) in enumerate(LIMITS):
            assert lo <= b.state.axis(i).machine_position <= hi


def test_mock_home_all_returns_every_axis_home():
    b = MockBackend()
    for axis in (AXIS_X, AXIS_Y, AXIS_Z):
        b.jog_increment(axis, 1, 1.0, 1.0)
        b.unhome_axis(axis)
    b.poll()
    assert not b.state.all_homed
    assert b.home_all()
    b.poll()
    assert b.state.all_homed
    assert tuple(b.state.axis(i).position for i in range(3)) == HOMES


def test_mock_estop_stops_everything_and_reports_once():
    b = MockBackend()
    b.spindle_forward(12000)
    b.set_flood(True)
    b.jog_continuous(AXIS_X, 1, 0.5)
    b.estop()
    b.poll()
    s = b.state
    assert s.estop_active and not s.machine_on
    assert s.spindle.commanded_speed == 0 and not s.flood_on
    assert s.error_message
    b.poll()
    assert b.state.error_message == ""          # reported once, like LinuxCNC
    assert not b.jog_continuous(AXIS_X, 1, 0.5)  # no motion while in E-stop
    assert b.estop_reset() and b.machine_on()
    b.poll()
    assert b.state.task_state == TaskState.ON


def test_mock_mdi_words_clamped_to_limits():
    b = MockBackend()
    b.mdi_command("G0 X999 Y-999 Z5")
    b.poll()
    (xlo, xhi), (ylo, yhi), (zlo, zhi) = LIMITS
    assert b.state.x.position == xhi
    assert b.state.y.position == ylo
    assert b.state.z.position == zhi


# ---------------------------------------------------------------------------
# Status bar
# ---------------------------------------------------------------------------

def test_dro_shows_each_axis_and_round_trips_units(qapp):
    from gui.components.status_bar import StatusBar
    from gui.unit_state import unit_state
    bar = StatusBar()
    rng = random.Random(1)
    for _ in range(25):
        pos = tuple(rng.uniform(-30.0, 30.0) for _ in range(3))
        bar.update_position(*pos)
        shown = [float(t) for t in bar.dro_text()]
        assert all(abs(a - b) <= 0.5e-4 for a, b in zip(shown, pos))
        unit_state.toggle()                       # metric
        shown_mm = [float(t) for t in bar.dro_text()]
        assert all(abs(a - b * 25.4) <= 0.5e-3 for a, b in zip(shown_mm, pos))
        unit_state.toggle()                       # back to inch


def test_rpm_box_fits_full_spindle_range(qapp):
    """Every RPM up to the spindle maximum is drawn without clipping."""
    from PyQt5.QtGui import QGuiApplication
    if QGuiApplication.platformName() == "offscreen":
        pytest.skip("offscreen platform has no fonts; widths are meaningless")
    from gui.components.status_bar import StatusBar
    from machine.constants import SPINDLE_MAX_RPM
    bar = StatusBar()
    label = bar._rpm_display
    for rpm in (0, 6000, 12000, 18888, SPINDLE_MAX_RPM):
        bar.update_rpm(rpm, "FWD")
        assert label.fontMetrics().horizontalAdvance(label.text()) <= label.minimumWidth()


def test_offline_badge_follows_backend(qapp):
    from gui.components.status_bar import StatusBar
    bar = StatusBar()
    assert not bar.is_offline
    bar.set_offline(True)
    assert bar.is_offline


# ---------------------------------------------------------------------------
# Main window
# ---------------------------------------------------------------------------

def test_main_window_tabs_and_ribbon_fit_screen(qapp):
    from gui.main_window import MainWindow, LIVE_SCREEN_SIZE
    w = MainWindow(backend=MockBackend())
    titles = [w.tab_widget.tabText(i) for i in range(w.tab_widget.count())]
    assert titles[0] == "Manual"
    # The debug overlay names pages by first letter; they must be unique.
    assert len({t[0] for t in titles}) == len(titles)
    assert w.status_bar.is_offline


def test_ribbon_fits_machine_screen(qapp):
    """The X/Y/Z ribbon, OFFLINE badge included, fits the 1920 px screen.
    Lathe reference on this check (Windows fonts, 96 DPI): 1716 px."""
    from PyQt5.QtGui import QGuiApplication
    if QGuiApplication.platformName() == "offscreen":
        pytest.skip("offscreen platform has no fonts; widths are meaningless")
    from gui.main_window import MainWindow, LIVE_SCREEN_SIZE
    w = MainWindow(backend=MockBackend())
    w.resize(*LIVE_SCREEN_SIZE)
    w.show()
    qapp.processEvents()
    try:
        assert w.status_bar.minimumSizeHint().width() <= LIVE_SCREEN_SIZE[0]
    finally:
        w.close()


def test_main_window_poll_updates_dro(qapp):
    from gui.main_window import MainWindow
    b = MockBackend()
    w = MainWindow(backend=b)
    b.jog_increment(AXIS_Y, 1, 1.0, 2.5)
    w._poll_status_bar_inner()
    assert w.status_bar.dro_text()[1] == "2.5000"
