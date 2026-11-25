"""Manual tab behaviour against the mock backend.

Invariants, not single examples: touch-off must make the touched axis read
the entered value in that work system (any position, value, system, unit);
a step jog moves exactly one step; every jog key moves only its own axis in
its own direction; a tripped switch can only be backed off the safe way.
"""
import random

import pytest

from machine.constants import LIMITS, JOG_INCREMENTS_INCH, JOG_INCREMENTS_MM, WCS_NAMES
from machine.interface import AXIS_X, AXIS_Y, AXIS_Z
from machine.mock_backend import MockBackend, SWITCH_RELEASE


@pytest.fixture
def tab(qapp):
    from gui.manual import ManualTab
    backend = MockBackend()
    t = ManualTab(backend)
    t._poll_timer.stop()          # tests drive polling themselves
    # Park every axis mid-travel so jogs in either direction have room.
    for axis, (lo, hi) in enumerate(LIMITS):
        backend._pos[axis] = (lo + hi) / 2
    backend.poll()
    yield t, backend
    t.deleteLater()
    qapp.processEvents()


# ---------------------------------------------------------------------------
# Touch-off
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", range(15))
def test_touchoff_makes_axis_read_value_in_that_system(seed):
    rng = random.Random(seed)
    b = MockBackend()
    axis = rng.randrange(3)
    lo, hi = LIMITS[axis]
    b._pos[axis] = rng.uniform(lo, hi)
    system = rng.randrange(1, len(WCS_NAMES))
    value = rng.uniform(-5.0, 5.0)
    b.poll()
    before = b.state.axis(axis).position
    assert b.touch_off(axis, value, system)
    b.poll()
    if system != 1:
        # G10 L20 writes the P system only; the active G54 reading is unchanged
        assert b.state.axis(axis).position == pytest.approx(before)
        b.mdi_command(WCS_NAMES[system])
        b.poll()
    assert b.state.active_wcs == WCS_NAMES[system]
    assert b.state.axis(axis).position == pytest.approx(value)
    assert b.state.axis(axis).machine_position == pytest.approx(b._pos[axis])


@pytest.mark.parametrize("metric", [False, True])
def test_touchoff_ui_converts_display_units(tab, metric):
    from gui.unit_state import unit_state
    t, b = tab
    if metric:
        unit_state.toggle()
    t._touchoff["axis"].setCurrentIndex(AXIS_Z)
    t._touchoff["wcs"].setCurrentIndex(0)                 # G54
    entered = 12.7 if metric else 0.5
    t._touchoff["value"].setValue(entered)
    t._touchoff["btn_set"].click()
    b.poll()
    assert b.state.z.position == pytest.approx(0.5, abs=1e-4)
    t._on_poll(force=True)
    shown = float(t.dro_text()[AXIS_Z])
    assert shown == pytest.approx(entered, abs=1e-3)


def test_touchoff_field_keeps_length_across_unit_toggle(tab):
    from gui.unit_state import unit_state
    t, _ = tab
    t._touchoff["value"].setValue(1.25)
    unit_state.toggle()
    assert t._touchoff["value"].value() == pytest.approx(31.75)
    unit_state.toggle()
    assert t._touchoff["value"].value() == pytest.approx(1.25)


# ---------------------------------------------------------------------------
# Jogging
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("metric", [False, True])
@pytest.mark.parametrize("index", range(1, len(JOG_INCREMENTS_INCH)))
def test_step_jog_moves_exactly_one_step(tab, metric, index):
    from gui.unit_state import unit_state
    t, b = tab
    if metric:
        unit_state.toggle()
    t._jog["step_combo"].setCurrentIndex(index)
    step = JOG_INCREMENTS_MM[index] / 25.4 if metric else JOG_INCREMENTS_INCH[index]
    for key, axis, sign in (("x_plus", AXIS_X, 1), ("y_minus", AXIS_Y, -1),
                            ("z_plus", AXIS_Z, 1)):
        before = b._pos[axis]
        t._jog["buttons"][key].pressed.emit()
        t._jog["buttons"][key].released.emit()
        lo, hi = LIMITS[axis]
        expected = min(hi, max(lo, before + sign * step))
        assert b._pos[axis] == pytest.approx(expected, abs=1e-9)
        assert b._jog_vel[axis] == 0.0        # a step never leaves a jog running


def test_continuous_jog_runs_while_held(tab):
    t, b = tab
    t._jog["step_combo"].setCurrentIndex(0)
    t._jog["buttons"]["y_plus"].pressed.emit()
    assert b._jog_vel[AXIS_Y] > 0
    t._jog["buttons"]["y_plus"].released.emit()
    assert b._jog_vel[AXIS_Y] == 0


def test_each_jog_key_moves_only_its_axis(tab):
    from PyQt5.QtCore import QEvent, Qt
    from PyQt5.QtGui import QKeyEvent
    from gui.manual.manual_tab import KEY_JOGS
    t, b = tab
    for key, (axis, direction) in KEY_JOGS.items():
        t.keyPressEvent(QKeyEvent(QEvent.KeyPress, key, Qt.NoModifier))
        vel = list(b._jog_vel)
        assert vel[axis] * direction > 0
        assert all(v == 0 for i, v in enumerate(vel) if i != axis)
        t.keyReleaseEvent(QKeyEvent(QEvent.KeyRelease, key, Qt.NoModifier))
        assert b._jog_vel == [0.0, 0.0, 0.0]


def test_jog_speed_is_unit_independent(tab):
    from gui.unit_state import unit_state
    t, _ = tab
    t._jog["speed_spin"].setValue(0.4)
    unit_state.toggle()
    assert t._jog["speed_spin"].value() == pytest.approx(10.2, abs=0.05)
    assert t._jog_velocity == pytest.approx(0.4)
    unit_state.toggle()
    assert t._jog_velocity == pytest.approx(0.4)


# ---------------------------------------------------------------------------
# Limit switch back-off
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("axis,end", [(a, e) for a in range(3) for e in (-1, 1)])
def test_limit_trip_back_off_flow(tab, axis, end):
    t, b = tab
    letter = "XYZ"[axis]
    t._jog["step_combo"].setCurrentIndex(3)               # 0.01 in steps
    b.simulate_limit_trip(axis, end)
    t._on_poll(force=True)
    text = t._limit["text"].text()
    assert not t._limit_banner.isHidden()
    assert letter in text and "machine ON" in text and "Override" in text

    away = "plus" if end < 0 else "minus"
    toward = "minus" if end < 0 else "plus"
    key = f"{letter.lower()}_{away}"
    start = b._pos[axis]

    # Refused until machine on + override
    t._jog["buttons"][key].pressed.emit()
    assert b._pos[axis] == start
    assert b.machine_on()
    t._limit["btn_override"].click()
    assert t._limit["btn_override"].isChecked()
    # Never further onto the switch, even with override
    t._jog["buttons"][f"{letter.lower()}_{toward}"].pressed.emit()
    assert b._pos[axis] == start

    for _ in range(int(round(SWITCH_RELEASE / 0.01))):
        t._jog["buttons"][key].pressed.emit()
        t._jog["buttons"][key].released.emit()
    t._on_poll(force=True)
    assert t._limit_banner.isHidden()
    assert not t._limit["btn_override"].isChecked()
    lo, hi = LIMITS[axis]
    assert lo <= b._pos[axis] <= hi


# ---------------------------------------------------------------------------
# Plane view, spindle, coolant
# ---------------------------------------------------------------------------

def test_plane_view_maps_axes_and_envelope(tab):
    from gui.components.position_graph import PLANES
    t, _ = tab
    g = t.graph
    p = (1.0, 2.0, -0.5)
    for name, (h, v) in PLANES.items():
        t._plane_buttons[name].click()
        assert g.plane == name
        assert g.plot_point(p) == (p[h], p[v])
        xs, ys = g._envelope.getData()
        assert (min(xs), max(xs)) == LIMITS[h]
        assert (min(ys), max(ys)) == LIMITS[v]


def test_spindle_and_flood_controls(tab):
    t, b = tab
    t._spindle["rpm_spin"].setValue(18000)
    t._spindle["btn_fwd"].click()
    b.poll()
    assert b.state.spindle.commanded_speed == 18000
    t._spindle["btn_stop"].click()
    b.poll()
    assert b.state.spindle.commanded_speed == 0
    t._coolant["btn_flood"].click()
    b.poll()
    assert b.state.flood_on
    b.set_flood(False)                        # changed elsewhere (M9)
    t._on_poll(force=True)
    assert not t._coolant["btn_flood"].isChecked()


def test_machine_coords_toggle(tab):
    t, b = tab
    b.touch_off(AXIS_X, 0.0, 1)
    t._on_poll(force=True)
    assert float(t.dro_text()[AXIS_X]) == pytest.approx(0.0)
    t._coord_toggle.click()
    assert float(t.dro_text()[AXIS_X]) == pytest.approx(b._pos[AXIS_X], abs=1e-4)
    assert "G53" in t._coord_toggle.text()
