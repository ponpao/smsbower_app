# -*- coding: utf-8 -*-
"""
Frameless window base — no native title bar.

Removing the OS title bar also removes the OS drag and resize behaviour, so
both are re-implemented here:

  * drag   — QWindow.startSystemMove(), so the window manager still gives us
             aero-snap on Windows and edge-tiling on Linux. Doing it by hand
             with mouse deltas loses both and feels laggy on high-DPI.
  * resize — QWindow.startSystemResize(edges) from an 6px hit zone around the
             frame, with the cursor changing to match the edge.

Maximised state squares off the corners, because a rounded window against the
screen edge shows desktop through the gap.
"""

from PyQt6.QtCore import QPoint, Qt
from PyQt6.QtGui import QCursor
from PyQt6.QtWidgets import QWidget

RESIZE_MARGIN = 6


class FramelessWindow(QWidget):
    """Top-level window with the native frame removed."""

    def __init__(self, *, rounded=True, parent=None):
        super().__init__(parent)
        self._rounded = rounded
        self._edges = Qt.Edge(0)

        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        if rounded:
            # Needed so the rounded corners show the desktop, not black.
            self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMouseTracking(True)

    # -- maximise ---------------------------------------------------------
    def toggle_max_restore(self):
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._sync_maximized_style()

    def _sync_maximized_style(self):
        """Re-polish widgets that key off the `maximized` property."""
        state = "true" if self.isMaximized() else "false"
        for name in ("Root", "TitleBar", "Sidebar", "StatusBar"):
            w = self.findChild(QWidget, name)
            if w is not None:
                w.setProperty("maximized", state)
                w.style().unpolish(w)
                w.style().polish(w)

    def changeEvent(self, event):
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self._sync_maximized_style()

    # -- drag (called by the custom title bar) ----------------------------
    def begin_system_move(self):
        handle = self.windowHandle()
        if handle is not None and not self.isMaximized():
            handle.startSystemMove()
            return True
        return False

    # -- resize -----------------------------------------------------------
    def _edges_at(self, pos: QPoint) -> Qt.Edge:
        if self.isMaximized() or self.isFullScreen():
            return Qt.Edge(0)
        m, r = RESIZE_MARGIN, self.rect()
        edges = Qt.Edge(0)
        if pos.x() <= r.left() + m:
            edges |= Qt.Edge.LeftEdge
        if pos.x() >= r.right() - m:
            edges |= Qt.Edge.RightEdge
        if pos.y() <= r.top() + m:
            edges |= Qt.Edge.TopEdge
        if pos.y() >= r.bottom() - m:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges: Qt.Edge) -> Qt.CursorShape:
        L, R = Qt.Edge.LeftEdge, Qt.Edge.RightEdge
        T, B = Qt.Edge.TopEdge, Qt.Edge.BottomEdge
        if edges in (L | T, R | B):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (R | T, L | B):
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (L | R):
            return Qt.CursorShape.SizeHorCursor
        if edges & (T | B):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor

    def mouseMoveEvent(self, event):
        edges = self._edges_at(event.position().toPoint())
        if edges != self._edges:
            self._edges = edges
            self.setCursor(QCursor(self._cursor_for(edges)))
        super().mouseMoveEvent(event)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            edges = self._edges_at(event.position().toPoint())
            if edges:
                handle = self.windowHandle()
                if handle is not None:
                    handle.startSystemResize(edges)
                    event.accept()
                    return
        super().mousePressEvent(event)

    def leaveEvent(self, event):
        self._edges = Qt.Edge(0)
        self.unsetCursor()
        super().leaveEvent(event)
