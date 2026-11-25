"""Collapsible section builders for the Manual tab.

Each function builds one CollapsibleSection and returns it with a dict of
the widgets that need signal wiring or polling updates.

Pattern copied from the lathe GUI (Industry-CAM-Engine gui/manual/sections.py,
dfb1c1a). Mill sections: Jog (X/Y/Z, step or continuous), Homing (X/Y/Z),
Spindle (VFD start/stop and speed), Coolant (flood), Tool, Touch-Off
(G54 to G59.3), MDI. Dropped: compound slide, MPG mode, lathe machine-state
section (the ribbon has those buttons).
"""

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QWidget, QHBoxLayout, QGridLayout, QFormLayout, QLabel, QPushButton,
    QComboBox, QLineEdit, QDoubleSpinBox, QSpinBox, QSizePolicy,
)

from gui.colors import COLORS, FONTS
from gui.components.collapsible_section import CollapsibleSection
from machine.constants import (
    DEFAULT_JOG_VELOCITY, MAX_JOG_VELOCITY, JOG_INCREMENTS_INCH,
    SPINDLE_MIN_RPM, SPINDLE_MAX_RPM, SPINDLE_DEFAULT_RPM, WCS_NAMES,
)

# One look for every small action button on the tab: the ribbon's rounded
# bubble border, one height, so rows line up (owner preference).
BUTTON_HEIGHT = 44
BUTTON_SS = (
    f"QPushButton {{ background: {COLORS['bg_surface']}; color: {COLORS['text_primary']};"
    f" border: 1px solid {COLORS['border_normal']}; border-radius: 5px;"
    f" font-weight: bold; padding: 0px 10px;"
    f" min-height: {BUTTON_HEIGHT - 2}px; max-height: {BUTTON_HEIGHT - 2}px; }}"
    f"QPushButton:hover {{ background: {COLORS['btn_primary_hover']}; }}"
    f"QPushButton:pressed, QPushButton:checked {{ background: {COLORS['btn_primary']};"
    f" border: 1px solid {COLORS['border_focused']}; }}"
    f"QPushButton:disabled {{ color: {COLORS['text_disabled']}; }}"
)
JOG_BUTTON_WIDTH = 64
LABEL_SS = f"color: {COLORS['text_secondary']}; font-size: 9pt;"
VALUE_SS = (
    f"font-family: '{FONTS['mono_family']}'; font-size: 14pt;"
    f" color: {COLORS['text_primary']}; font-weight: bold;"
)


def _button(text: str, checkable: bool = False, width: int = 0) -> QPushButton:
    btn = QPushButton(text)
    btn.setStyleSheet(BUTTON_SS)
    btn.setFixedHeight(BUTTON_HEIGHT)
    btn.setCheckable(checkable)
    btn.setAutoRepeat(False)
    if width:
        btn.setFixedWidth(width)
    return btn


def _label(text: str, width: int = 0) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet(LABEL_SS)
    if width:
        lbl.setFixedWidth(width)
    return lbl


def increment_labels(metric: bool):
    """Step choices as shown, index-matched to JOG_INCREMENTS_*."""
    if metric:
        return ["Continuous", "0.001 mm", "0.01 mm", "0.1 mm", "1 mm"]
    return ["Continuous"] + [f'{v:g}"' for v in JOG_INCREMENTS_INCH[1:]]


# ======================================================================
# Jog
# ======================================================================

def build_jog_section() -> tuple:
    """X/Y cross plus a Z column. Continuous = hold to move; a step size
    = one step per click. Keyboard: arrows X/Y, Page Up/Down Z."""
    section = CollapsibleSection("Jog", expanded=True)

    grid = QGridLayout()
    grid.setHorizontalSpacing(6)
    grid.setVerticalSpacing(6)
    buttons = {}
    # (key, text, row, col): X/Y cross on the left, Z column on the right
    for key, text, row, col in (
        ("y_plus", "Y+", 0, 1), ("x_minus", "X−", 1, 0), ("x_plus", "X+", 1, 2),
        ("y_minus", "Y−", 2, 1), ("z_plus", "Z+", 0, 4), ("z_minus", "Z−", 2, 4),
    ):
        btn = _button(text)
        btn.setMinimumWidth(JOG_BUTTON_WIDTH)
        btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        buttons[key] = btn
        grid.addWidget(btn, row, col)
    # Buttons share the panel width (no dead space at the right); a narrow
    # gap column separates the X/Y cross from the Z column.
    for col in (0, 1, 2, 4):
        grid.setColumnStretch(col, 1)
    grid.setColumnMinimumWidth(3, 18)
    section.add_layout(grid)

    step_row = QHBoxLayout()
    step_row.addWidget(_label("Step:", 48))
    step_combo = QComboBox()
    step_combo.addItems(increment_labels(metric=False))
    step_combo.setToolTip("Continuous: hold a button to move.\n"
                          "Step: each click moves one step.")
    step_row.addWidget(step_combo, stretch=1)
    section.add_layout(step_row)

    speed_row = QHBoxLayout()
    speed_row.addWidget(_label("Speed:", 48))
    speed_spin = QDoubleSpinBox()
    speed_spin.setRange(0.01, MAX_JOG_VELOCITY)
    speed_spin.setValue(DEFAULT_JOG_VELOCITY)
    speed_spin.setSingleStep(0.05)
    speed_spin.setDecimals(2)
    speed_spin.setSuffix(" in/s")
    speed_row.addWidget(speed_spin, stretch=1)
    section.add_layout(speed_row)

    btn_clear_trail = _button("Clear Trail")
    section.add_widget(btn_clear_trail)

    widgets = dict(buttons=buttons, step_combo=step_combo, speed_spin=speed_spin,
                   btn_clear_trail=btn_clear_trail)
    return section, widgets


# ======================================================================
# Homing
# ======================================================================

def build_homing_section() -> tuple:
    section = CollapsibleSection("Homing", expanded=True)

    status_row = QHBoxLayout()
    status = {}
    for letter in "XYZ":
        lbl = QLabel(f"{letter}: ✗")
        lbl.setAlignment(Qt.AlignCenter)
        status[letter] = lbl
        status_row.addWidget(lbl, stretch=1)
    section.add_layout(status_row)

    btn_row = QHBoxLayout()
    btn_all = _button("Home All")
    btn_all.setToolTip("Z first, then X and Y together (HOME_SEQUENCE in the INI)")
    btn_row.addWidget(btn_all, stretch=2)
    axis_buttons = {}
    for letter in "XYZ":
        btn = _button(f"Home {letter}")
        axis_buttons[letter] = btn
        btn_row.addWidget(btn, stretch=1)
    section.add_layout(btn_row)

    return section, dict(status=status, btn_all=btn_all, axis_buttons=axis_buttons)


# ======================================================================
# Spindle
# ======================================================================

def build_spindle_section() -> tuple:
    """VFD spindle: speed entry and start/stop. The displayed RPM is the
    commanded speed; there is no spindle encoder."""
    section = CollapsibleSection("Spindle", expanded=False)

    speed_row = QHBoxLayout()
    speed_row.addWidget(_label("RPM:", 48))
    rpm_spin = QSpinBox()
    rpm_spin.setRange(SPINDLE_MIN_RPM, SPINDLE_MAX_RPM)
    rpm_spin.setValue(SPINDLE_DEFAULT_RPM)
    rpm_spin.setSingleStep(1000)
    speed_row.addWidget(rpm_spin, stretch=1)
    section.add_layout(speed_row)

    btn_row = QHBoxLayout()
    btn_fwd = _button("FWD (M3)")
    btn_rev = _button("REV (M4)")
    btn_stop = _button("STOP (M5)")
    for b in (btn_fwd, btn_rev, btn_stop):
        btn_row.addWidget(b, stretch=1)
    section.add_layout(btn_row)

    status = QLabel("Stopped")
    status.setAlignment(Qt.AlignCenter)
    status.setStyleSheet(LABEL_SS)
    section.add_widget(status)

    return section, dict(rpm_spin=rpm_spin, btn_fwd=btn_fwd, btn_rev=btn_rev,
                         btn_stop=btn_stop, status=status)


# ======================================================================
# Coolant
# ======================================================================

def build_coolant_section() -> tuple:
    section = CollapsibleSection("Coolant", expanded=False)
    btn_flood = _button("Flood (M8)", checkable=True)
    section.add_widget(btn_flood)
    note = QLabel("Spindle cooling pump runs whenever the machine has power.")
    note.setWordWrap(True)
    note.setStyleSheet(LABEL_SS)
    section.add_widget(note)
    return section, dict(btn_flood=btn_flood)


# ======================================================================
# Tool
# ======================================================================

def build_tool_section() -> tuple:
    section = CollapsibleSection("Tool", expanded=False)

    row = QHBoxLayout()
    row.addWidget(_label("Active:", 48))
    tool_display = QLabel("T0")
    tool_display.setStyleSheet(VALUE_SS)
    row.addWidget(tool_display)
    row.addStretch()
    section.add_layout(row)

    change_row = QHBoxLayout()
    tool_input = QLineEdit()
    tool_input.setPlaceholderText("T#")
    tool_input.setMaximumWidth(90)
    btn_change = _button("Change (M6)")
    change_row.addWidget(tool_input)
    change_row.addWidget(btn_change, stretch=1)
    section.add_layout(change_row)

    return section, dict(tool_display=tool_display, tool_input=tool_input,
                         btn_change=btn_change)


# ======================================================================
# Touch-off
# ======================================================================

def build_touchoff_section() -> tuple:
    """G10 L20: set the chosen work system so the current position reads
    the entered value on the chosen axis."""
    section = CollapsibleSection("Touch-Off (G10 L20)", expanded=False)

    form = QFormLayout()
    form.setSpacing(4)
    axis_combo = QComboBox()
    axis_combo.addItems(["X", "Y", "Z"])
    form.addRow(_label("Axis:"), axis_combo)

    value_spin = QDoubleSpinBox()
    value_spin.setRange(-100.0, 100.0)
    value_spin.setDecimals(4)
    value_spin.setSingleStep(0.001)
    value_spin.setSuffix('"')
    form.addRow(_label("Value:"), value_spin)

    wcs_combo = QComboBox()
    wcs_combo.addItems(WCS_NAMES[1:])
    form.addRow(_label("System:"), wcs_combo)
    section.add_layout(form)

    btn_set = _button("Set Offset")
    section.add_widget(btn_set)

    return section, dict(axis=axis_combo, value=value_spin, wcs=wcs_combo,
                         btn_set=btn_set)


# ======================================================================
# MDI
# ======================================================================

def build_mdi_section() -> tuple:
    section = CollapsibleSection("MDI Command", expanded=False)

    row = QHBoxLayout()
    mdi_input = QLineEdit()
    mdi_input.setPlaceholderText("e.g. G0 X1.0 Y0.5")
    mdi_input.setStyleSheet(f"font-family: '{FONTS['mono_family']}';")
    btn_send = _button("Send", width=80)
    row.addWidget(mdi_input, stretch=1)
    row.addWidget(btn_send)
    section.add_layout(row)

    history = QComboBox()
    history.setPlaceholderText("History")
    history.setMaxCount(10)
    section.add_widget(history)

    return section, dict(input=mdi_input, btn_send=btn_send, history=history)


def make_limit_banner() -> tuple:
    """Hidden until a limit switch trips. Plain-language steps to back off
    a shared home/limit switch, plus the override button."""
    banner = QWidget()
    banner.setStyleSheet(
        f"QWidget#limitBanner {{ background: {COLORS['bg_panel']};"
        f" border: 2px solid {COLORS['status_warning']}; border-radius: 5px; }}")
    banner.setObjectName("limitBanner")
    layout = QHBoxLayout(banner)
    layout.setContentsMargins(10, 6, 10, 6)
    text = QLabel("")
    text.setWordWrap(True)
    text.setStyleSheet(f"color: {COLORS['text_primary']}; font-size: 10pt;")
    btn_override = _button("Override Limits", checkable=True)
    layout.addWidget(text, stretch=1)
    layout.addWidget(btn_override)
    banner.setVisible(False)
    return banner, dict(text=text, btn_override=btn_override)
