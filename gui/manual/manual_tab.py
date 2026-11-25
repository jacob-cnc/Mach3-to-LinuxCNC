"""Manual tab: position plane view, DRO and the manual control sections.

Layout (as on the lathe): splitter with the position graph on the left and
the DRO + collapsible sections on the right. UI construction is in
sections.py; this file wires signals, polls the backend and dispatches.

Adapted from the lathe GUI (Industry-CAM-Engine gui/manual/manual_tab.py,
dfb1c1a). Kept: splitter layout, work/machine DRO toggle, hold-to-jog
buttons and arrow-key velocity jog, unit-aware jog speed and touch-off,
MDI history. Dropped: compound slide, MPG mode mux. Added: Y axis, step
jogging, plane selector on the graph, VFD spindle and flood controls,
limit-switch banner with override, G54 to G59.3 touch-off.
"""

import logging
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSplitter, QScrollArea, QButtonGroup,
)

from gui.colors import COLORS, FONTS
from gui.components.position_graph import PositionGraphWidget
from gui.manual.sections import (
    BUTTON_SS, BUTTON_HEIGHT, increment_labels, make_limit_banner,
    build_jog_section, build_homing_section, build_spindle_section,
    build_coolant_section, build_tool_section, build_touchoff_section,
    build_mdi_section,
)
from gui.unit_state import unit_state
from machine.interface import (
    MachineBackend, HomingState, SpindleDirection, AXIS_X, AXIS_Y, AXIS_Z,
    AXIS_LETTERS,
)
from machine.constants import (
    DEFAULT_JOG_VELOCITY, MAX_JOG_VELOCITY, JOG_INCREMENTS_INCH, JOG_INCREMENTS_MM,
)

logger = logging.getLogger(__name__)

# Keyboard jog (continuous, hold to move): AXIS uses the same keys.
KEY_JOGS = {
    Qt.Key_Left: (AXIS_X, -1.0),
    Qt.Key_Right: (AXIS_X, +1.0),
    Qt.Key_Up: (AXIS_Y, +1.0),
    Qt.Key_Down: (AXIS_Y, -1.0),
    Qt.Key_PageUp: (AXIS_Z, +1.0),
    Qt.Key_PageDown: (AXIS_Z, -1.0),
}

_INPUT_OK_SS = ""
_INPUT_BAD_SS = f"border: 1px solid {COLORS['status_error']}; color: {COLORS['status_error']};"
_AXIS_COLORS = (COLORS["status_info"], COLORS["status_ok"], COLORS["graph_threading"])


class ManualTab(QWidget):
    """Manual machine control.

    Signals:
        mdi_executed(str): emitted after an MDI command is accepted
    """

    mdi_executed = pyqtSignal(str)

    POLL_MS = 100

    def __init__(self, backend: MachineBackend, parent: Optional[QWidget] = None):
        super().__init__(parent)
        self._backend = backend
        self._jog_velocity = DEFAULT_JOG_VELOCITY      # inch/sec, always
        self._keys_held: set = set()

        self._setup_ui()
        self._connect_signals()

        self._poll_timer = QTimer(self)
        self._poll_timer.timeout.connect(self._on_poll)
        self._poll_timer.start(self.POLL_MS)

        self.setFocusPolicy(Qt.StrongFocus)

    # ==================================================================
    # UI
    # ==================================================================

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(0)

        splitter = QSplitter(Qt.Horizontal, self)
        layout.addWidget(splitter)

        # Left: plane selector + position graph
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        plane_row = QHBoxLayout()
        plane_row.setContentsMargins(4, 4, 4, 0)
        self._plane_buttons = {}
        self._plane_group = QButtonGroup(self)
        self._plane_group.setExclusive(True)
        for name, tip in (("XY", "Top view"), ("XZ", "Front view"), ("YZ", "Side view")):
            btn = QPushButton(name)
            btn.setCheckable(True)
            btn.setStyleSheet(BUTTON_SS)
            btn.setFixedSize(72, BUTTON_HEIGHT)
            btn.setToolTip(tip)
            self._plane_group.addButton(btn)
            self._plane_buttons[name] = btn
            plane_row.addWidget(btn)
        plane_row.addStretch()
        self._plane_buttons["XY"].setChecked(True)
        left_layout.addLayout(plane_row)

        self._graph = PositionGraphWidget(self)
        self._graph.setMinimumWidth(400)
        left_layout.addWidget(self._graph, stretch=1)
        splitter.addWidget(left)

        # Right: DRO, limit banner, sections
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(4, 4, 4, 4)
        right_layout.setSpacing(4)
        right_layout.addWidget(self._build_dro_widget())

        self._limit_banner, self._limit = make_limit_banner()
        right_layout.addWidget(self._limit_banner)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(2)

        jog_section, self._jog = build_jog_section()
        homing_section, self._homing = build_homing_section()
        spindle_section, self._spindle = build_spindle_section()
        coolant_section, self._coolant = build_coolant_section()
        tool_section, self._tool = build_tool_section()
        touchoff_section, self._touchoff = build_touchoff_section()
        mdi_section, self._mdi = build_mdi_section()
        self._sections = {
            "jog": jog_section, "homing": homing_section, "spindle": spindle_section,
            "coolant": coolant_section, "tool": tool_section,
            "touchoff": touchoff_section, "mdi": mdi_section,
        }
        for section in self._sections.values():
            content_layout.addWidget(section)
        content_layout.addStretch()
        scroll.setWidget(content)
        right_layout.addWidget(scroll, stretch=1)

        splitter.addWidget(right)
        splitter.setSizes([1100, 700])
        splitter.setStretchFactor(0, 3)
        splitter.setStretchFactor(1, 2)

    def _build_dro_widget(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(4)

        self._coord_toggle = QPushButton("Work Coords (G54)")
        self._coord_toggle.setCheckable(True)
        self._coord_toggle.setStyleSheet(BUTTON_SS)
        self._coord_toggle.setFixedHeight(BUTTON_HEIGHT)
        layout.addWidget(self._coord_toggle)

        self._dro = []
        for letter, color in zip(AXIS_LETTERS, _AXIS_COLORS):
            row = QHBoxLayout()
            axis_label = QLabel(letter)
            axis_label.setFixedWidth(28)
            axis_label.setAlignment(Qt.AlignCenter)
            axis_label.setStyleSheet(
                f"color: {color}; font-weight: bold; font-size: 16pt;"
                f" font-family: '{FONTS['mono_family']}';")
            value = QLabel("+0.0000")
            value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            value.setMinimumHeight(44)
            value.setStyleSheet(
                f"font-family: '{FONTS['mono_family']}'; font-size: 28pt;"
                f" color: {COLORS['text_primary']}; background: {COLORS['bg_base']};"
                f" border: 1px solid {COLORS['border_normal']}; border-radius: 4px;"
                f" padding: 4px 10px;")
            row.addWidget(axis_label)
            row.addWidget(value, stretch=1)
            layout.addLayout(row)
            self._dro.append(value)
        return widget

    # ==================================================================
    # Signals
    # ==================================================================

    def _connect_signals(self):
        b = self._jog["buttons"]
        for key, (axis, direction) in {
            "x_plus": (AXIS_X, 1.0), "x_minus": (AXIS_X, -1.0),
            "y_plus": (AXIS_Y, 1.0), "y_minus": (AXIS_Y, -1.0),
            "z_plus": (AXIS_Z, 1.0), "z_minus": (AXIS_Z, -1.0),
        }.items():
            b[key].pressed.connect(lambda a=axis, d=direction: self._jog_button_pressed(a, d))
            b[key].released.connect(lambda a=axis: self._jog_button_released(a))
        self._jog["speed_spin"].valueChanged.connect(self._on_jog_speed_changed)
        self._jog["btn_clear_trail"].clicked.connect(self._graph.clear_trail)

        for name, btn in self._plane_buttons.items():
            btn.clicked.connect(lambda _c=False, n=name: self._graph.set_plane(n))

        self._homing["btn_all"].clicked.connect(self._backend.home_all)
        for i, letter in enumerate(AXIS_LETTERS):
            self._homing["axis_buttons"][letter].clicked.connect(
                lambda _c=False, a=i: self._backend.home_axis(a))

        self._spindle["btn_fwd"].clicked.connect(
            lambda: self._backend.spindle_forward(self._spindle["rpm_spin"].value()))
        self._spindle["btn_rev"].clicked.connect(
            lambda: self._backend.spindle_reverse(self._spindle["rpm_spin"].value()))
        self._spindle["btn_stop"].clicked.connect(self._backend.spindle_stop)

        self._coolant["btn_flood"].toggled.connect(self._backend.set_flood)

        self._tool["btn_change"].clicked.connect(self._on_tool_change)
        self._tool["tool_input"].returnPressed.connect(self._on_tool_change)

        self._touchoff["btn_set"].clicked.connect(self._on_touchoff)

        self._mdi["btn_send"].clicked.connect(self._on_mdi_send)
        self._mdi["input"].returnPressed.connect(self._on_mdi_send)
        self._mdi["history"].activated.connect(
            lambda idx: self._mdi["input"].setText(self._mdi["history"].itemText(idx)))

        self._limit["btn_override"].clicked.connect(self._on_override_clicked)
        self._coord_toggle.toggled.connect(lambda _c: self._on_poll(force=True))
        unit_state.unit_changed.connect(self._on_unit_changed)

    # ==================================================================
    # Polling
    # ==================================================================

    def _on_poll(self, force: bool = False):
        """Refresh displays. Skipped while the tab is hidden (the ribbon's
        own poll keeps running)."""
        if not force and not self.isVisible():
            return
        self._backend.poll()
        s = self._backend.state
        axes = (s.x, s.y, s.z)

        machine = self._coord_toggle.isChecked()
        self._coord_toggle.setText(
            "Machine Coords (G53)" if machine else f"Work Coords ({s.active_wcs})")
        dp = unit_state.decimals
        for label, axis in zip(self._dro, axes):
            value = axis.machine_position if machine else axis.position
            label.setText(f"{unit_state.to_display(value):+.{dp}f}")

        self._graph.update_position(tuple(a.machine_position for a in axes), s.work_origin)

        for letter, axis in zip(AXIS_LETTERS, axes):
            lbl = self._homing["status"][letter]
            homed = axis.homed == HomingState.HOMED
            lbl.setText(f"{letter}: {'✓' if homed else '✗'}")
            lbl.setStyleSheet(
                f"color: {COLORS['status_ok'] if homed else COLORS['status_warning']};"
                f" font-size: 11pt; font-weight: bold;")

        t = s.tool_in_spindle
        self._tool["tool_display"].setText(f"T{t}")

        sp = s.spindle
        if sp.direction == SpindleDirection.STOPPED:
            text = "Stopped"
        else:
            word = "FWD" if sp.direction == SpindleDirection.FORWARD else "REV"
            text = (f"{word} {sp.commanded_speed:.0f} rpm commanded"
                    f" - {'at speed' if sp.at_speed else 'spinning up'}")
        self._spindle["status"].setText(text)

        flood = self._coolant["btn_flood"]
        if flood.isChecked() != s.flood_on:
            flood.blockSignals(True)
            flood.setChecked(s.flood_on)
            flood.blockSignals(False)

        self._update_limit_banner(s)

    def _update_limit_banner(self, s):
        tripped = [(AXIS_LETTERS[i], a.limit_end) for i, a in enumerate((s.x, s.y, s.z))
                   if a.at_limit]
        if not tripped:
            self._limit_banner.setVisible(False)
            self._limit["btn_override"].setChecked(False)
            return
        letter, end = tripped[0]
        away = "+" if end < 0 else ("−" if end > 0 else "away")
        where = {-1: "minimum-end", 1: "maximum-end"}.get(end, "")
        steps = []
        if not s.machine_on:
            steps.append("turn the machine ON")
        if not self._limit["btn_override"].isChecked():
            steps.append("press Override Limits")
        steps.append(f"jog {letter}{away} off the switch")
        self._limit["text"].setText(
            f"{letter} is on its {where} limit switch. To back off: "
            + ", then ".join(steps) + ".")
        self._limit_banner.setVisible(True)

    # ==================================================================
    # Handlers
    # ==================================================================

    def _step_inches(self) -> float:
        """Selected step in inches; 0 = continuous."""
        i = self._jog["step_combo"].currentIndex()
        if unit_state.is_metric:
            return JOG_INCREMENTS_MM[i] / unit_state.CONVERSION_FACTOR
        return JOG_INCREMENTS_INCH[i]

    def _jog_button_pressed(self, axis: int, direction: float):
        step = self._step_inches()
        if step:
            self._backend.jog_increment(axis, direction, self._jog_velocity, step)
        else:
            self._backend.jog_continuous(axis, direction, self._jog_velocity)

    def _jog_button_released(self, axis: int):
        if not self._step_inches():
            self._backend.jog_stop(axis)

    def _on_jog_speed_changed(self, value: float):
        self._jog_velocity = unit_state.from_display(value)

    def _on_override_clicked(self, checked: bool):
        if checked and not self._backend.override_limits():
            self._limit["btn_override"].setChecked(False)
        self._on_poll(force=True)

    def _on_tool_change(self):
        field = self._tool["tool_input"]
        text = field.text().strip().upper().lstrip("T")
        try:
            number = int(text)
            if number < 0:
                raise ValueError
        except ValueError:
            field.setStyleSheet(_INPUT_BAD_SS)
            return
        field.setStyleSheet(_INPUT_OK_SS)
        field.clear()
        self._backend.tool_change(number)

    def _on_touchoff(self):
        axis = self._touchoff["axis"].currentIndex()
        value = unit_state.from_display(self._touchoff["value"].value())
        system = self._touchoff["wcs"].currentIndex() + 1
        if self._backend.touch_off(axis, value, system):
            logger.info("Touch-off %s=%.4f in system %d", AXIS_LETTERS[axis], value, system)

    def _on_mdi_send(self):
        cmd = self._mdi["input"].text().strip()
        if not cmd:
            return
        if self._backend.mdi_command(cmd):
            self._mdi["history"].insertItem(0, cmd)
            self._mdi["input"].clear()
            self.mdi_executed.emit(cmd)

    def _on_unit_changed(self, _mode: str):
        metric = unit_state.is_metric

        combo = self._jog["step_combo"]
        index = combo.currentIndex()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(increment_labels(metric))
        combo.setCurrentIndex(index)
        combo.blockSignals(False)

        spin = self._jog["speed_spin"]
        spin.blockSignals(True)
        factor = unit_state.CONVERSION_FACTOR if metric else 1.0
        spin.setSuffix(" mm/s" if metric else " in/s")
        spin.setDecimals(1 if metric else 2)
        spin.setRange(0.01 * factor, MAX_JOG_VELOCITY * factor)
        spin.setSingleStep(1.0 if metric else 0.05)
        spin.setValue(self._jog_velocity * factor)
        spin.blockSignals(False)

        self._convert_touchoff_units(metric)

        self._on_poll(force=True)

    def _convert_touchoff_units(self, metric: bool):
        """Switch the touch-off field's unit, keeping the same length."""
        touch = self._touchoff["value"]
        touch.blockSignals(True)
        value = touch.value()
        if metric:
            touch.setDecimals(3)
            touch.setRange(-100.0 * 25.4, 100.0 * 25.4)
            touch.setSingleStep(0.025)
            touch.setSuffix(" mm")
            touch.setValue(value * unit_state.CONVERSION_FACTOR)
        else:
            touch.setDecimals(4)
            touch.setRange(-100.0, 100.0)
            touch.setSingleStep(0.001)
            touch.setSuffix('"')
            touch.setValue(value / unit_state.CONVERSION_FACTOR)
        touch.blockSignals(False)

    # ==================================================================
    # Keyboard jog
    # ==================================================================

    def keyPressEvent(self, event):  # noqa: N802 (Qt naming)
        key = event.key()
        if key not in KEY_JOGS:
            super().keyPressEvent(event)
            return
        if event.isAutoRepeat() or key in self._keys_held:
            return
        self._keys_held.add(key)
        axis, direction = KEY_JOGS[key]
        self._backend.jog_continuous(axis, direction, self._jog_velocity)

    def keyReleaseEvent(self, event):  # noqa: N802
        key = event.key()
        if key not in KEY_JOGS:
            super().keyReleaseEvent(event)
            return
        if event.isAutoRepeat():
            return
        self._keys_held.discard(key)
        self._backend.jog_stop(KEY_JOGS[key][0])

    # ==================================================================
    # Accessors (tests)
    # ==================================================================

    @property
    def graph(self) -> PositionGraphWidget:
        return self._graph

    def dro_text(self) -> tuple:
        return tuple(label.text() for label in self._dro)
