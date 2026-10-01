"""Resize and move support for the frameless main window.

A frameless window gets no OS resize borders, so this filter watches the
mouse near the window edges and hands the drag to the OS
(``QWindow.startSystemResize``), which also keeps Windows snap working.
"""

from __future__ import annotations

from PyQt6.QtCore import QEvent, QObject, QPoint, Qt
from PyQt6.QtWidgets import QApplication, QLabel, QMainWindow, QWidget

BORDER = 8  # px of grab area along each edge

_CURSORS = {
    Qt.Edge.LeftEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.RightEdge: Qt.CursorShape.SizeHorCursor,
    Qt.Edge.TopEdge: Qt.CursorShape.SizeVerCursor,
    Qt.Edge.BottomEdge: Qt.CursorShape.SizeVerCursor,
}


def _edges_at(window: QWidget, global_pos: QPoint) -> Qt.Edge:
    if window.isMaximized() or window.isFullScreen():
        return Qt.Edge(0)
    pos = window.mapFromGlobal(global_pos)
    rect = window.rect()
    edges = Qt.Edge(0)
    if pos.x() <= BORDER:
        edges |= Qt.Edge.LeftEdge
    elif pos.x() >= rect.width() - BORDER:
        edges |= Qt.Edge.RightEdge
    if pos.y() <= BORDER:
        edges |= Qt.Edge.TopEdge
    elif pos.y() >= rect.height() - BORDER:
        edges |= Qt.Edge.BottomEdge
    return edges


def _cursor_for(edges: Qt.Edge) -> Qt.CursorShape | None:
    diagonal_a = (Qt.Edge.LeftEdge | Qt.Edge.TopEdge, Qt.Edge.RightEdge | Qt.Edge.BottomEdge)
    diagonal_b = (Qt.Edge.RightEdge | Qt.Edge.TopEdge, Qt.Edge.LeftEdge | Qt.Edge.BottomEdge)
    if edges in diagonal_a:
        return Qt.CursorShape.SizeFDiagCursor
    if edges in diagonal_b:
        return Qt.CursorShape.SizeBDiagCursor
    return _CURSORS.get(edges)


class FramelessResizer(QObject):
    """Application-wide event filter adding edge resizing to ``window``."""

    def __init__(self, window: QMainWindow) -> None:
        super().__init__(window)
        self.window = window
        self._cursor_set = False
        window.setMouseTracking(True)
        QApplication.instance().installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if not isinstance(obj, QWidget) or obj.window() is not self.window:
            return False
        kind = event.type()
        if kind == QEvent.Type.MouseMove and not event.buttons():
            obj.setMouseTracking(True)
            cursor = _cursor_for(_edges_at(self.window, event.globalPosition().toPoint()))
            if cursor is not None:
                if not self._cursor_set:
                    QApplication.setOverrideCursor(cursor)
                    self._cursor_set = True
                else:
                    QApplication.changeOverrideCursor(cursor)
            elif self._cursor_set:
                QApplication.restoreOverrideCursor()
                self._cursor_set = False
        elif kind == QEvent.Type.MouseButtonPress and event.button() == Qt.MouseButton.LeftButton:
            edges = _edges_at(self.window, event.globalPosition().toPoint())
            if edges and self.window.windowHandle() is not None:
                self.window.windowHandle().startSystemResize(edges)
                return True
        elif kind == QEvent.Type.Leave and obj is self.window and self._cursor_set:
            QApplication.restoreOverrideCursor()
            self._cursor_set = False
        return False


def start_move(widget: QWidget) -> None:
    """Let the OS move the window (supports snap and drag-out-of-maximized)."""
    handle = widget.window().windowHandle()
    if handle is not None:
        handle.startSystemMove()


def toggle_maximized(widget: QWidget) -> None:
    window = widget.window()
    window.showNormal() if window.isMaximized() or window.isFullScreen() else window.showMaximized()


def is_drag_area(widget: QWidget, local_pos: QPoint) -> bool:
    """True when the press is on the bar itself or a plain label, not a control."""
    child = widget.childAt(local_pos)
    return child is None or isinstance(child, QLabel) or child is widget
