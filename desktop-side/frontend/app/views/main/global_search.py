"""Results window for the top-bar global search."""

from __future__ import annotations

from typing import Callable

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
)

GROUPS = [
    ("properties", "Properties", "fa5s.home"),
    ("clients", "Clients", "fa5s.users"),
    ("transactions", "Transactions", "fa5s.exchange-alt"),
    ("agents", "Agents", "fa5s.user-tie"),
    ("documents", "Documents", "fa5s.folder-open"),
    ("partners", "Partners / Developers", "fa5s.handshake"),
]
PAGE_ROLE = Qt.ItemDataRole.UserRole


class GlobalSearchDialog(QDialog):
    def __init__(self, query: str, results: dict[str, list[dict]],
                 open_result: Callable[[str, str], None], parent=None) -> None:
        super().__init__(parent)
        self.open_result = open_result
        self.setWindowTitle(f"Search results for “{query}”")
        self.setMinimumSize(620, 420)
        self.setStyleSheet(
            "QDialog { background: #f7f9f3; color: #17310a; }"
            "QLabel { background: transparent; color: #17310a; }"
            "QTreeWidget { background: #ffffff; border: 1px solid #d4dccf; border-radius: 8px;"
            " color: #26351f; font-size: 13px; }"
            "QTreeWidget::item { padding: 5px; }"
            "QTreeWidget::item:selected { background: #d6e8c9; color: #17310a; }"
            "QPushButton { background: #e7eedc; color: #17310a; border: 1px solid #cbd8be;"
            " border-radius: 6px; padding: 7px 14px; }"
            "QPushButton:hover { background: #dce8ce; }"
        )
        total = sum(len(items) for items in results.values())
        heading = QLabel(
            f"{total} result(s) for “{query}”. Double-click a result to open it."
            if total else f"No records match “{query}”."
        )
        heading.setStyleSheet("font-size: 14px; font-weight: 700;")

        self.tree = QTreeWidget()
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels(["Result", "Details"])
        self.tree.setColumnWidth(0, 260)
        for key, label, icon in GROUPS:
            items = results.get(key) or []
            if not items:
                continue
            group = QTreeWidgetItem([f"{label} ({len(items)})", ""])
            group.setIcon(0, qta.icon(icon, color="#486b2a"))
            font = group.font(0)
            font.setBold(True)
            group.setFont(0, font)
            group.setFlags(group.flags() & ~Qt.ItemFlag.ItemIsSelectable)
            for entry in items:
                child = QTreeWidgetItem([entry["title"], entry.get("subtitle") or ""])
                child.setIcon(0, qta.icon(icon, color="#17310a"))
                child.setToolTip(0, entry["title"])
                child.setToolTip(1, entry.get("subtitle") or "")
                child.setData(0, PAGE_ROLE, (entry["page"], entry["filter"]))
                group.addChild(child)
            self.tree.addTopLevelItem(group)
        self.tree.expandAll()
        self.tree.itemDoubleClicked.connect(lambda item, _col: self._open(item))
        self.tree.itemActivated.connect(lambda item, _col: self._open(item))

        open_button = QPushButton("Open")
        open_button.setIcon(qta.icon("fa5s.external-link-alt", color="#17310a"))
        open_button.clicked.connect(lambda: self._open(self.tree.currentItem()))
        close_button = QPushButton("Close")
        close_button.setIcon(qta.icon("fa5s.times-circle", color="#17310a"))
        close_button.clicked.connect(self.reject)
        buttons = QHBoxLayout()
        buttons.addStretch()
        buttons.addWidget(open_button)
        buttons.addWidget(close_button)

        layout = QVBoxLayout(self)
        layout.addWidget(heading)
        layout.addWidget(self.tree, 1)
        layout.addLayout(buttons)

    def _open(self, item: QTreeWidgetItem | None) -> None:
        target = item.data(0, PAGE_ROLE) if item is not None else None
        if not target:
            return
        self.accept()
        self.open_result(*target)
