from __future__ import annotations

import json

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QFont
from PyQt6.QtWidgets import QAbstractItemView, QComboBox, QHeaderView, QSplitter, QTableWidgetItem, QTextEdit

from app.theme import TOKENS
from app.views.main.pages._common import DataPage, kind_colors, table

KIND_LABELS = {"DATA": "Data", "ANALYSIS": "Analysis", "RECOMMENDATION": "Recommendation"}
COLUMNS = ["Type", "Indicator", "Finding", "Recommendation", "Basis"]
# Initial widths (px); every column can be dragged wider or narrower.
WIDTHS = [110, 210, 300, 320]  # Basis stretches into the rest
ORDER = {"RECOMMENDATION": 0, "ANALYSIS": 1, "DATA": 2}


class DssPage(DataPage):
    title = "Decision Support"
    subtitle = ("Indicators computed from properties, transactions, agents, documents and the "
                "forecast. Recommendations appear only when their rule is met by stored data, and "
                "each one shows the rule it is based on.")

    def build(self) -> None:
        self.kind = QComboBox()
        self.kind.addItem("All items", None)
        for kind, label in KIND_LABELS.items():
            self.kind.addItem(label, kind)
        self.kind.currentIndexChanged.connect(self._render)
        self.actions.insertWidget(0, self.kind)

        self.table = table(COLUMNS)
        self.table.setProperty("altyFixedColumns", True)  # keep WIDTHS; the user drags to resize
        self.table.setWordWrap(True)
        self.table.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # drag to resize
        header.setStretchLastSection(True)
        header.setMinimumSectionSize(90)
        header.sectionResized.connect(lambda *_: self.table.resizeRowsToContents())
        for column, width in enumerate(WIDTHS):
            self.table.setColumnWidth(column, width)
        self.table.itemSelectionChanged.connect(self._show_evidence)

        self.evidence = QTextEdit()
        self.evidence.setReadOnly(True)
        self.evidence.setPlaceholderText("Select an item to see the data it was computed from")

        # Drag the divider to give the table (or the evidence) more room.
        self.splitter = QSplitter(Qt.Orientation.Vertical)
        self.splitter.addWidget(self.table)
        self.splitter.addWidget(self.evidence)
        self.splitter.setStretchFactor(0, 4)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setChildrenCollapsible(False)
        self.splitter.setSizes([520, 150])
        self.layout_.addWidget(self.splitter, 1)
        self.items: list[dict] = []

    def load(self) -> None:
        self.items = self.api.get_dss(token=self.token)["items"]
        self._render()

    @staticmethod
    def _row(item: dict) -> list[str]:
        if item["kind"] == "RECOMMENDATION":
            # The advice is the recommendation; the rule is why it appeared.
            return [KIND_LABELS["RECOMMENDATION"], item["title"], "Rule met by current data",
                    item["detail"], item.get("rule") or "—"]
        return [KIND_LABELS[item["kind"]], item["title"], item["detail"], "Information only — no action required",
                "Computed from stored records"]

    def _render(self) -> None:
        kind = self.kind.currentData()
        items = sorted((item for item in self.items if kind is None or item["kind"] == kind),
                       key=lambda item: ORDER.get(item["kind"], 9))
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(items))
        colors = kind_colors()
        bold = QFont()
        bold.setBold(True)
        for row, item in enumerate(items):
            for column, value in enumerate(self._row(item)):
                cell = QTableWidgetItem(value)
                cell.setToolTip(value)
                cell.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)
                if column == 0:
                    cell.setData(Qt.ItemDataRole.UserRole, item)
                    cell.setBackground(QColor(colors[item["kind"]]))
                    cell.setFont(bold)
                if column == 3:
                    if item["kind"] == "RECOMMENDATION":
                        cell.setFont(bold)
                        cell.setForeground(QColor(TOKENS["accent"]))
                    else:
                        cell.setForeground(QColor(TOKENS["text_faint"]))
                self.table.setItem(row, column, cell)
        self.table.resizeRowsToContents()
        recommendations = sum(1 for item in self.items if item["kind"] == "RECOMMENDATION")
        self.status.setText(
            f"{recommendations} recommendation(s) and {len(self.items) - recommendations} indicator(s). "
            + ("Recommendations are listed first." if recommendations else
               "No recommendation rules are met by the current data.")
            + " Drag column edges or the divider below the table to resize."
        )

    def _show_evidence(self) -> None:
        item = self.table.item(self.table.currentRow(), 0)
        data = item.data(Qt.ItemDataRole.UserRole) if item else None
        if not data:
            self.evidence.clear()
            return
        lines = [f"{KIND_LABELS[data['kind']]}: {data['title']}", ""]
        if data["kind"] == "RECOMMENDATION":
            lines += [f"Recommendation: {data['detail']}", f"Basis: {data.get('rule') or '—'}"]
        else:
            lines.append(f"Finding: {data['detail']}")
        evidence = data.get("evidence")
        if evidence:
            lines += ["", "Underlying data:", json.dumps(evidence, indent=2, ensure_ascii=False, default=str)]
        self.evidence.setPlainText("\n".join(lines))
