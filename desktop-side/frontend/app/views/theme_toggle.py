"""Light/dark switch shared by the login window and the main window header.

Clicking it asks the controller to switch modes; the controller rebuilds the
windows from the central tokens (``app.theme``) and the choice is saved.
"""

from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtWidgets import QToolButton

from app import theme


class ThemeToggleButton(QToolButton):
    def __init__(self, controller, object_name: str = "windowAction", size: int = 30, parent=None) -> None:
        super().__init__(parent)
        self.controller = controller
        self.setObjectName(object_name)
        self.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setFixedSize(size, size)
        self.setIconSize(QSize(15, 15))
        dark = theme.current_mode() == "dark"
        # The icon shows the mode you switch *to*.
        self.setIcon(qta.icon("fa5s.sun" if dark else "fa5s.moon", color=theme.TOKENS["accent"]))
        label = "Switch to light mode" if dark else "Switch to dark mode"
        self.setToolTip(label)
        self.setAccessibleName(label)
        self.clicked.connect(self._toggle)

    def _toggle(self) -> None:
        target = "light" if theme.current_mode() == "dark" else "dark"
        self.controller.apply_theme(target)
