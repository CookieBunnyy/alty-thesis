"""Shared building blocks for data pages (styling matches the existing pages)."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api.client import ApiClient, error_message

INSUFFICIENT = "Insufficient data"

TABLE_STYLE = (
    "QTableWidget { background: #ffffff; alternate-background-color: #f5f7f2; "
    "border: 1px solid #d4dccf; border-radius: 8px; color: #26351f; font-size: 13px; "
    "selection-background-color: #d6e8c9; selection-color: #17310a; }"
    "QTableWidget::item { padding: 6px; border-bottom: 1px solid #edf0eb; }"
    "QHeaderView::section { background: #e4ebdf; color: #17310a; border: none; "
    "border-bottom: 1px solid #cbd5c4; padding: 8px; font-size: 12px; font-weight: 700; }"
)
BUTTON_STYLE = (
    "QPushButton { background: #e7eedc; color: #17310a; border: 1px solid #d1ddc4; "
    "border-radius: 7px; padding: 8px 14px; font-weight: 600; }"
    "QPushButton:hover { background: #dce8ce; }"
    "QPushButton:disabled { color: #9aa894; }"
)
PRIMARY_STYLE = (
    "QPushButton { background: #17310a; color: white; border: none; border-radius: 7px; "
    "padding: 8px 14px; font-weight: 600; }"
    "QPushButton:hover { background: #285214; } QPushButton:disabled { background: #aeb8a7; }"
)
def kind_colors() -> dict[str, str]:
    from app.theme import TOKENS

    return {"DATA": TOKENS["card_2"], "ANALYSIS": TOKENS["info_soft"], "RECOMMENDATION": TOKENS["accent_soft"]}


def fmt_date(value: Any) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%b %d, %Y %H:%M")
    except ValueError:
        return str(value)


def fmt_money(value: Any) -> str:
    try:
        return f"₱{float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def button(text: str, icon: str, primary: bool = False) -> QPushButton:
    widget = QPushButton(text)
    widget.setIcon(qta.icon(icon, color="#ffffff" if primary else "#17310a"))
    widget.setCursor(Qt.CursorShape.PointingHandCursor)
    widget.setStyleSheet(PRIMARY_STYLE if primary else BUTTON_STYLE)
    return widget


class Card(QFrame):
    def __init__(self, title: str, accent: str = "#17310a") -> None:
        super().__init__()
        self.setStyleSheet("QFrame { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 8px; }"
                           "QLabel { border: none; background: transparent; }")
        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        self.value = QLabel("—")
        self.value.setStyleSheet(f"color: {accent}; font-size: 22px; font-weight: 700;")
        caption = QLabel(title)
        caption.setWordWrap(True)
        caption.setStyleSheet("color: #65745b; font-size: 12px; font-weight: 600;")
        layout.addWidget(self.value)
        layout.addWidget(caption)

    def set(self, value: Any) -> None:
        self.value.setText(f"{value:,}" if isinstance(value, int) else str(value))


def table(headers: list[str]) -> QTableWidget:
    widget = QTableWidget(0, len(headers))
    widget.setHorizontalHeaderLabels(headers)
    widget.setAlternatingRowColors(True)
    widget.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
    widget.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
    widget.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
    widget.verticalHeader().setVisible(False)
    widget.setShowGrid(False)
    widget.setStyleSheet(TABLE_STYLE)
    widget.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
    widget.horizontalHeader().setStretchLastSection(True)
    return widget


def fill(widget: QTableWidget, rows: Iterable[Iterable[Any]], data: list[Any] | None = None) -> None:
    rows = [list(row) for row in rows]
    widget.setSortingEnabled(False)
    widget.setRowCount(len(rows))
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            item = QTableWidgetItem("—" if value in (None, "") else str(value))
            item.setToolTip(item.text())
            if c == 0 and data is not None:
                item.setData(Qt.ItemDataRole.UserRole, data[r])
            widget.setItem(r, c, item)
    widget.setSortingEnabled(True)


class DataPage(QWidget):
    """A page with a title, subtitle, action bar and a status line."""

    title = "Page"
    subtitle = ""

    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.layout_ = QVBoxLayout(self)
        self.layout_.setContentsMargins(24, 20, 24, 20)
        self.layout_.setSpacing(12)
        header = QHBoxLayout()
        stack = QVBoxLayout()
        heading = QLabel(self.title)
        heading.setStyleSheet("color: #17310a; font-size: 24px; font-weight: 700;")
        sub = QLabel(self.subtitle)
        sub.setWordWrap(True)
        sub.setStyleSheet("color: #60705a; font-size: 13px;")
        stack.addWidget(heading)
        stack.addWidget(sub)
        header.addLayout(stack, 1)
        self.layout_.addLayout(header)
        # Actions get their own row so the title + buttons never force the
        # page wider than the window.
        self.actions = QHBoxLayout()
        self.refresh_button = button("Refresh", "fa5s.sync-alt")
        self.refresh_button.clicked.connect(self.refresh)
        self.actions.addWidget(self.refresh_button)
        self.actions.addStretch()
        self.layout_.addLayout(self.actions)
        self.status = QLabel("Sign in to load data.")
        self.status.setWordWrap(True)
        self.status.setStyleSheet("color: #65745b; font-size: 12px; font-weight: 600;")
        self.layout_.addWidget(self.status)
        self.build()

    @property
    def token(self) -> str | None:
        return self.controller.session.state.token if self.controller else None

    @property
    def role(self) -> str:
        return self.controller.session.state.role if self.controller else "Employee"

    def build(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def load(self) -> None:  # pragma: no cover - overridden
        raise NotImplementedError

    def refresh(self) -> None:
        if not self.token:
            self.status.setText("Sign in to load data.")
            return
        self.refresh_button.setEnabled(False)
        try:
            self.load()
        except Exception as exc:
            self.status.setText(error_message(exc))
        finally:
            self.refresh_button.setEnabled(True)
