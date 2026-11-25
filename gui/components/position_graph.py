"""Real-time tool position graph for the Manual tab, with a plane selector.

Shows the tool's MACHINE position as a dot with a trail of recent movement,
inside the machine travel envelope (soft limits), plus a cross at the active
work offset origin. One plane at a time: XY (top), XZ (front) or YZ (side).

Adapted from the lathe GUI (Industry-CAM-Engine
gui/components/position_graph.py, dfb1c1a). Mill changes: plane selector,
three axes, no diameter axis, everything plotted in machine coordinates
(the lathe drew the work position against a machine-coordinate envelope),
values drawn in the current display unit.
"""

from collections import deque

import pyqtgraph as pg
from pyqtgraph.Qt import QtCore

from gui.colors import COLORS
from gui.unit_state import unit_state
from machine.constants import LIMITS

# Max trail points (10 Hz poll = 50 s of history)
TRAIL_MAX_POINTS = 500

# plane name -> (horizontal axis index, vertical axis index)
PLANES = {
    "XY": (0, 1),
    "XZ": (0, 2),
    "YZ": (1, 2),
}
_LETTERS = "XYZ"


class PositionGraphWidget(pg.PlotWidget):
    """Plane view of tool position.

    Public API:
        set_plane("XY" | "XZ" | "YZ")
        update_position(machine_xyz, work_origin_xyz)  - each poll
        clear_trail()
        plot_point(machine_xyz) -> (h, v) in display units (tests)
    """

    def __init__(self, parent=None, limits=LIMITS):
        super().__init__(parent=parent, background=COLORS["graph_bg"])
        self._limits = tuple(limits)
        self._plane = "XY"
        self._trail: deque = deque(maxlen=TRAIL_MAX_POINTS)  # machine xyz
        self._last_pos = (0.0, 0.0, 0.0)
        self._last_origin = (0.0, 0.0, 0.0)

        plot_item = self.getPlotItem()
        plot_item.setAspectLocked(True, ratio=1)
        plot_item.showGrid(x=True, y=True, alpha=0.3)
        plot_item.setMenuEnabled(False)

        self._envelope = self.plot([], [], pen=pg.mkPen(
            COLORS["border_normal"], width=1, style=QtCore.Qt.DashLine))
        self._trail_item = self.plot([], [], pen=pg.mkPen(COLORS["graph_feed"], width=2))
        self._origin = pg.ScatterPlotItem(
            size=16, symbol="+", pen=pg.mkPen(COLORS["status_info"], width=2))
        self.addItem(self._origin)
        self._tool_dot = pg.ScatterPlotItem(
            size=14, brush=pg.mkBrush(COLORS["graph_tool_dot"]),
            pen=pg.mkPen("#000000", width=1))
        self.addItem(self._tool_dot)

        # Bound method, not a lambda: Qt drops the connection when the widget
        # is destroyed, so a closed graph never redraws on a unit toggle.
        unit_state.unit_changed.connect(self._on_unit_changed)
        self._redraw(fit=True)

    def _on_unit_changed(self, _mode: str):
        self._redraw(fit=True)

    # -- Public API ---------------------------------------------------------

    @property
    def plane(self) -> str:
        return self._plane

    def set_plane(self, plane: str):
        if plane not in PLANES:
            raise ValueError(f"unknown plane {plane!r}")
        if plane != self._plane:
            self._plane = plane
            self._redraw(fit=True)

    def plot_point(self, xyz) -> tuple:
        """(horizontal, vertical) plot coordinates of a machine position."""
        h, v = PLANES[self._plane]
        return (unit_state.to_display(xyz[h]), unit_state.to_display(xyz[v]))

    def update_position(self, machine_xyz, work_origin_xyz=(0.0, 0.0, 0.0)):
        pos = tuple(machine_xyz)
        if not self._trail or max(abs(a - b) for a, b in zip(self._trail[-1], pos)) > 0.00005:
            self._trail.append(pos)
        self._last_pos = pos
        self._last_origin = tuple(work_origin_xyz)
        self._redraw()

    def clear_trail(self):
        self._trail.clear()
        self._redraw()

    def mouseDoubleClickEvent(self, event):  # noqa: N802 (Qt naming)
        """Double-click fits the whole travel envelope."""
        self._fit()
        event.accept()

    # -- Drawing ------------------------------------------------------------

    def _redraw(self, fit: bool = False):
        h, v = PLANES[self._plane]
        to = unit_state.to_display
        (h_lo, h_hi), (v_lo, v_hi) = self._limits[h], self._limits[v]
        self._envelope.setData([to(h_lo), to(h_hi), to(h_hi), to(h_lo), to(h_lo)],
                               [to(v_lo), to(v_lo), to(v_hi), to(v_hi), to(v_lo)])
        if len(self._trail) > 1:
            pts = [self.plot_point(p) for p in self._trail]
            self._trail_item.setData([p[0] for p in pts], [p[1] for p in pts])
        else:
            self._trail_item.setData([], [])
        ox, oy = self.plot_point(self._last_origin)
        self._origin.setData([ox], [oy])
        tx, ty = self.plot_point(self._last_pos)
        self._tool_dot.setData([tx], [ty])

        suffix = unit_state.length_suffix
        plot_item = self.getPlotItem()
        plot_item.setLabel("bottom", f"{_LETTERS[h]} ({suffix})")
        plot_item.setLabel("left", f"{_LETTERS[v]} ({suffix})")
        if fit:
            self._fit()

    def _fit(self):
        h, v = PLANES[self._plane]
        to = unit_state.to_display
        (h_lo, h_hi), (v_lo, v_hi) = self._limits[h], self._limits[v]
        self.getViewBox().setRange(xRange=(to(h_lo), to(h_hi)),
                                   yRange=(to(v_lo), to(v_hi)), padding=0.08)
