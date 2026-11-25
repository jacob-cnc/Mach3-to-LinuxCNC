"""Main window for the mill GUI.

QMainWindow with the StatusBar ribbon on top and a QTabWidget below. The tabs
are placeholders in this skeleton; each names what it will hold (see
docs/gui-plan.md).

Copied from the lathe GUI (Industry-CAM-Engine gui/main_window.py, dfb1c1a).
Kept: ribbon + tab layout, error label in the tab row, 5 Hz status poll,
AUTO-idle return to MANUAL, 96 DPI / 1920x1080 live-screen emulation,
offline-mode notice, debug overlay hook. Dropped: lathe tabs and their
signal wiring, green cycle button poll, restore_lathe_modes. Changed: the
software E-stop commands E-stop (the lathe commanded machine off); the
feed readout shows the actual feed rate (the lathe passed feed override).

Run offline:  python -m gui.main_window
"""

import logging
import os
import sys

from PyQt5.QtCore import Qt, QEvent, QPoint, QTimer
from PyQt5.QtGui import QPalette, QColor
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QLabel,
)

from gui.colors import COLORS, STYLESHEET
from gui.components.status_bar import StatusBar
from machine.factory import get_backend
from machine.interface import InterpState, SpindleDirection, TaskMode

logger = logging.getLogger(__name__)

APP_NAME = "Mill 3040"
ENV_OFFLINE_REASON = "MILL_GUI_OFFLINE_REASON"

# (tab title, what the tab will hold). Order = operator priority.
# First letters must stay unique: the debug overlay names pages by them.
TABS = (
    ("Manual", "Jog, homing, limit override, spindle, coolant, MDI, touch-off"),
    ("Run", "Open, preview (2D plane view and 3D), run external or conversational G-code"),
    ("Program", "Conversational programming: ProtoTRAK-style events built on DXF geometry"),
    ("Edit", "G-code editor"),
    ("Tools", "Tool table: diameter, length offset, type, flutes, stickout"),
    ("Offsets", "Work offsets G54 to G59.3"),
    ("Setup", "HAL monitor, commissioning checklist, velocity and acceleration tests"),
    ("Help", "Help and G-code reference"),
)


class MainWindow(QMainWindow):
    """Mill GUI main window: StatusBar (top) + tab widget."""

    def __init__(self, parent=None, backend=None):
        super().__init__(parent)
        self.setWindowTitle(APP_NAME)
        self.resize(1400, 900)

        self._backend = backend if backend is not None else get_backend()

        self._setup_ui()
        self._wire_signals()
        self._status_bar.set_offline(self._backend.is_offline)

        self._prev_estop = False
        self._auto_idle_polls = 0

        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._poll_status_bar)
        self._status_timer.start(200)  # 5 Hz

        logger.info("MainWindow initialized (%s backend)",
                    "offline mock" if self._backend.is_offline else "live")

    # ------------------------------------------------------------------
    # UI setup
    # ------------------------------------------------------------------

    def _setup_ui(self):
        central = QWidget(self)
        self.setCentralWidget(central)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._status_bar = StatusBar(self)
        layout.addWidget(self._status_bar)

        self._tab_widget = QTabWidget(self)
        self._tab_widget.setDocumentMode(True)
        layout.addWidget(self._tab_widget)

        self._tabs = {}
        for title, purpose in TABS:
            page = self._make_placeholder(title, purpose)
            self._tabs[title] = page
            self._tab_widget.addTab(page, title)
        self._tab_widget.setCurrentWidget(self._tabs["Manual"])

        # Errors show in the empty right side of the tab row, so a long
        # message never widens the ribbon past the 1920 px screen.
        self._error_label = self._status_bar.error_label
        self._error_label.setParent(self._tab_widget)
        self._tab_widget.installEventFilter(self)
        self._tab_widget.tabBar().installEventFilter(self)

    _ERROR_GAP_LEFT = 16
    _ERROR_GAP_RIGHT = 8

    def eventFilter(self, obj, event):  # noqa: N802 (Qt naming)
        """Keep the error label placed in the tab row as things resize."""
        tabs = getattr(self, "_tab_widget", None)
        if tabs is not None and obj in (tabs, tabs.tabBar()) and \
                event.type() in (QEvent.Resize, QEvent.Show, QEvent.LayoutRequest):
            self._place_error_label()
        return super().eventFilter(obj, event)

    def _place_error_label(self):
        """Fill the tab row from the last tab's right edge to the window edge,
        vertically centred, 40 px tall (or less if the tab row is shorter)."""
        tabs = self._tab_widget
        bar = tabs.tabBar()
        if bar.count() == 0:
            return
        last = bar.tabRect(bar.count() - 1)
        left = bar.mapTo(tabs, last.topRight()).x() + 1 + self._ERROR_GAP_LEFT
        top = bar.mapTo(tabs, bar.rect().topLeft()).y()
        width = tabs.width() - left - self._ERROR_GAP_RIGHT
        height = min(40, max(0, bar.height() - 8))
        self._error_label.setGeometry(
            left, top + (bar.height() - height) // 2, max(0, width), height)
        self._error_label.raise_()

    def _make_placeholder(self, title: str, purpose: str) -> QWidget:
        """Placeholder page: tab title and what the tab will hold."""
        widget = QWidget(self)
        layout = QVBoxLayout(widget)
        layout.setAlignment(Qt.AlignCenter)
        for text, size, style in ((title, 20, "bold"), (purpose, 13, "italic"),
                                  ("Not built yet", 11, "normal")):
            label = QLabel(text)
            label.setAlignment(Qt.AlignCenter)
            weight = "font-weight: bold;" if style == "bold" else ""
            italic = "font-style: italic;" if style == "italic" else ""
            label.setStyleSheet(
                f"color: {COLORS['text_disabled']}; font-size: {size}pt; {weight}{italic}")
            layout.addWidget(label)
        return widget

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _wire_signals(self):
        self._status_bar.estop_clicked.connect(self._on_estop_clicked)
        self._status_bar.reset_clicked.connect(self._backend.estop_reset)
        self._status_bar.machine_on_clicked.connect(self._backend.machine_on)
        self._status_bar.machine_off_clicked.connect(self._backend.machine_off)
        self._status_bar.mode_clicked.connect(self._on_mode_clicked)

    def _on_mode_clicked(self):
        """Ribbon mode chip: return to MANUAL, but never interrupt a running
        or paused program."""
        self._backend.poll()
        s = self._backend.state
        if s.task_mode == TaskMode.MANUAL:
            return
        if s.program_busy:
            self._status_bar.show_error("Program active - stop it before leaving AUTO")
            return
        logger.info("Mode chip click: returning to MANUAL from %s", s.task_mode.value)
        self._backend.set_mode_manual()

    def _on_estop_clicked(self):
        """Software E-stop. Does not replace the hardwired E-stop chain."""
        self._backend.estop()
        logger.warning("Software E-stop triggered from status bar")

    # ------------------------------------------------------------------
    # Status poll (5 Hz)
    # ------------------------------------------------------------------

    def _poll_status_bar(self):
        try:
            self._poll_status_bar_inner()
        except Exception:  # noqa: BLE001 - keep the timer alive
            logger.exception("_poll_status_bar raised unexpectedly")

    def _poll_status_bar_inner(self):
        self._backend.poll()
        s = self._backend.state
        bar = self._status_bar

        bar.update_position(s.x.position, s.y.position, s.z.position)

        if s.estop_active:
            state_str = "ESTOP"
        elif s.interp_state == InterpState.READING:
            state_str = "RUN"
        elif s.interp_state == InterpState.PAUSED:
            state_str = "PAUSE"
        else:
            state_str = "IDLE"
        bar.update_state(state_str)
        bar.update_mode(s.task_mode.value)

        # Return to MANUAL when LinuxCNC sits in AUTO with no program work
        # left. program_busy covers interpreter, task, motion queue and pause;
        # interp IDLE alone is true mid-cut (lathe, 2026-11-08). Two polls.
        if s.task_mode == TaskMode.AUTO and not s.program_busy:
            self._auto_idle_polls += 1
            if self._auto_idle_polls == 2:
                logger.info("AUTO and idle: returning to MANUAL")
                self._backend.set_mode_manual()
        else:
            self._auto_idle_polls = 0

        direction = {SpindleDirection.FORWARD: "FWD",
                     SpindleDirection.REVERSE: "REV"}.get(s.spindle.direction, "")
        bar.update_rpm(int(round(s.spindle.commanded_speed)), direction)
        bar.update_feed(s.current_feed)
        bar.update_tool(s.tool_in_spindle)
        if s.active_gcodes:
            bar.update_gcodes(s.active_gcodes)

        if s.error_message:
            bar.show_error(s.error_message)
        elif s.estop_active and not self._prev_estop:
            bar.show_error("E-STOP")
        self._prev_estop = s.estop_active

    # ------------------------------------------------------------------
    # Accessors (tests, debug overlay)
    # ------------------------------------------------------------------

    @property
    def status_bar(self) -> StatusBar:
        return self._status_bar

    @property
    def tab_widget(self) -> QTabWidget:
        return self._tab_widget

    @property
    def backend(self):
        return self._backend


# --------------------------------------------------------------------------
# Dark palette
# --------------------------------------------------------------------------

def _apply_dark_palette(app: QApplication):
    palette = QPalette()
    palette.setColor(QPalette.Window, QColor(COLORS["bg_base"]))
    palette.setColor(QPalette.WindowText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Base, QColor(COLORS["bg_panel"]))
    palette.setColor(QPalette.AlternateBase, QColor(COLORS["bg_surface"]))
    palette.setColor(QPalette.ToolTipBase, QColor(COLORS["bg_surface"]))
    palette.setColor(QPalette.ToolTipText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Text, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.Button, QColor(COLORS["bg_panel"]))
    palette.setColor(QPalette.ButtonText, QColor(COLORS["text_primary"]))
    palette.setColor(QPalette.BrightText, QColor(COLORS["status_error"]))
    palette.setColor(QPalette.Link, QColor(COLORS["status_info"]))
    palette.setColor(QPalette.Highlight, QColor(COLORS["btn_primary"]))
    palette.setColor(QPalette.HighlightedText, QColor(COLORS["text_primary"]))
    app.setPalette(palette)


# --------------------------------------------------------------------------
# Live-screen emulation (offline preview on a dev PC)
# --------------------------------------------------------------------------

# Same display as the lathe (G5): 15.6" FHD panel, Linux/X11 at 96 DPI.
LIVE_SCREEN_SIZE = (1920, 1080)


def _enable_live_dpi_emulation():
    """Draw the GUI 1:1 at 96 DPI on Windows, as on the machine PC.

    Without this, Qt 5 on a 125-150 % Windows display draws point-sized text
    at 120-144 DPI while px-sized widgets stay the same. Set QT_FONT_DPI
    yourself to override. Must run before QApplication is created.
    """
    if sys.platform != "win32":
        return
    os.environ.setdefault("QT_FONT_DPI", "96")


def _show_at_live_size(window: QMainWindow):
    """Show maximized on a 1920x1080 screen; on a larger one, as a 1920x1080
    window so the offline preview matches the machine screen."""
    screen = window.screen() or QApplication.primaryScreen()
    avail = screen.availableGeometry()
    target_w, target_h = LIVE_SCREEN_SIZE
    if avail.width() <= target_w or avail.height() <= target_h:
        window.showMaximized()
        return
    # Open ON the target screen (moving across monitors with different
    # Windows scaling rescales the window).
    window.move(avail.topLeft() + QPoint(20, 20))
    window.show()
    frame_extra_w = window.frameGeometry().width() - window.width()
    frame_extra_h = window.frameGeometry().height() - window.height()
    window.resize(target_w - frame_extra_w, target_h - frame_extra_h)
    frame = window.frameGeometry()
    frame.moveCenter(avail.center())
    window.move(frame.topLeft())


# --------------------------------------------------------------------------
# Entry point
# --------------------------------------------------------------------------

def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    _enable_live_dpi_emulation()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    _apply_dark_palette(app)
    app.setStyleSheet(STYLESHEET)

    window = MainWindow()
    reason = os.environ.get(ENV_OFFLINE_REASON)
    if reason:
        from PyQt5.QtWidgets import QMessageBox
        QTimer.singleShot(500, lambda: QMessageBox.warning(
            window, "Offline preview mode",
            f"{reason}.\n\nThe GUI is running OFFLINE with simulated data - no "
            "machine control."))
    _show_at_live_size(window)

    from gui.debug_overlay import debug_ui_enabled, install_debug_overlay
    if debug_ui_enabled():
        window._debug_overlay = install_debug_overlay(window)

    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
