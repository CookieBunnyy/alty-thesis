from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QComboBox, QHBoxLayout, QLineEdit, QTextEdit

from app.views.main.pages._common import DataPage, fill, fmt_date, table


class AuditPage(DataPage):
    title = "Audit Logs"
    subtitle = ("Read-only trail of logins, uploads, document processing, entity changes, "
                "synchronization and user administration.")

    def build(self) -> None:
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search action, entity ID or actor…")
        self.search.returnPressed.connect(self.refresh)
        self.action = QComboBox()
        self.action.addItem("All actions", None)
        self.result = QComboBox()
        for label, value in (("All results", None), ("Success", "SUCCESS"), ("Failed", "FAILED")):
            self.result.addItem(label, value)
        self.action.currentIndexChanged.connect(self.refresh)
        self.result.currentIndexChanged.connect(self.refresh)
        filters.addWidget(self.search, 1)
        filters.addWidget(self.action)
        filters.addWidget(self.result)
        self.layout_.addLayout(filters)
        self.table = table(["Timestamp", "Actor", "Action", "Entity", "Entity ID", "Result"])
        self.table.itemSelectionChanged.connect(self._show_details)
        self.layout_.addWidget(self.table, 1)
        self.details = QTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(160)
        self.details.setPlaceholderText("Select an event to see its details")
        self.layout_.addWidget(self.details)

    def load(self) -> None:
        if self.action.count() == 1:
            self.action.blockSignals(True)
            for action in self.api.get_audit_actions(token=self.token):
                self.action.addItem(action, action)
            self.action.blockSignals(False)
        params = {"limit": 500}
        if self.search.text().strip():
            params["search"] = self.search.text().strip()
        if self.action.currentData():
            params["action"] = self.action.currentData()
        if self.result.currentData():
            params["result"] = self.result.currentData()
        data = self.api.get_audit_events(token=self.token, params=params)
        items = data["items"]
        fill(self.table, ([fmt_date(e["timestamp"]), e["actor"], e["action"], e.get("entity_type"),
                           e.get("entity_id"), e["result"]] for e in items), items)
        self.status.setText(f"Showing {len(items)} of {data['total']} event(s)")

    def _show_details(self) -> None:
        item = self.table.item(self.table.currentRow(), 0)
        event = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.details.setPlainText(json.dumps(event.get("details", {}), indent=2, ensure_ascii=False)
                                  if event else "")
