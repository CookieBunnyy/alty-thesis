from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import QComboBox, QTextEdit

from app.views.main.pages._common import kind_colors, DataPage, fill, table

KIND_LABELS = {"DATA": "Data", "ANALYSIS": "Analysis", "RECOMMENDATION": "System-generated recommendation"}


class DssPage(DataPage):
    title = "Decision Support"
    subtitle = ("Indicators computed from properties, transactions, agents, documents and the "
                "forecast. Each item is labelled DATA, ANALYSIS, or SYSTEM-GENERATED "
                "RECOMMENDATION with the rule that produced it.")

    def build(self) -> None:
        self.kind = QComboBox()
        self.kind.addItem("All items", None)
        for kind, label in KIND_LABELS.items():
            self.kind.addItem(label, kind)
        self.kind.currentIndexChanged.connect(self._render)
        self.actions.insertWidget(0, self.kind)
        self.table = table(["Type", "Indicator", "Detail", "Rule"])
        self.table.itemSelectionChanged.connect(self._show_evidence)
        self.layout_.addWidget(self.table, 1)
        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        self.evidence.setMaximumHeight(170)
        self.evidence.setPlaceholderText("Select an item to see the underlying data")
        self.layout_.addWidget(self.evidence)
        self.items: list[dict] = []

    def load(self) -> None:
        self.items = self.api.get_dss(token=self.token)["items"]
        self._render()

    def _render(self) -> None:
        kind = self.kind.currentData()
        items = [item for item in self.items if kind is None or item["kind"] == kind]
        fill(self.table, ([KIND_LABELS[i["kind"]], i["title"], i["detail"], i.get("rule", "")] for i in items),
             items)
        for row, item in enumerate(items):
            for column in range(4):
                self.table.item(row, column).setBackground(QColor(kind_colors()[item["kind"]]))
        recommendations = sum(1 for item in self.items if item["kind"] == "RECOMMENDATION")
        self.status.setText(f"{len(self.items)} item(s), {recommendations} recommendation(s). "
                            "Recommendations appear only when their rule is met by stored data.")

    def _show_evidence(self) -> None:
        item = self.table.item(self.table.currentRow(), 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        self.evidence.setPlainText(json.dumps(data.get("evidence", {}), indent=2, ensure_ascii=False)
                                   if data else "")
