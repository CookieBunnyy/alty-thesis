from __future__ import annotations

from typing import Any

import httpx
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api.client import ApiClient


class AnalyticsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Analytics")
        title.setStyleSheet("color: #17310a; font-size: 26px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.summary_label = QLabel("Sign in to load analytics.")
        self.summary_label.setStyleSheet("color: #65745b; font-size: 13px;")
        layout.addWidget(self.summary_label)

        section_row = QHBoxLayout()
        section_row.setSpacing(16)
        self.month_table = QTableWidget(0, 2)
        self.month_table.setHorizontalHeaderLabels(["Month", "Transactions"])
        self.month_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.month_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.agent_table = QTableWidget(0, 4)
        self.agent_table.setHorizontalHeaderLabels(
            ["Agent", "Status", "Transactions", "Completed Revenue"]
        )
        self.agent_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        for table in (self.month_table, self.agent_table):
            table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            table.setAlternatingRowColors(True)
            table.setShowGrid(False)
            table.verticalHeader().setVisible(False)
            table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
            table.setStyleSheet(
                "QTableWidget { background: #ffffff; alternate-background-color: #f5f7f2; "
                "border: 1px solid #d4dccf; border-radius: 8px; color: #26351f; }"
                "QHeaderView::section { background: #e4ebdf; color: #17310a; "
                "border: none; padding: 8px; font-weight: 700; }"
            )
        section_row.addWidget(self.month_table, 1)
        section_row.addWidget(self.agent_table, 2)
        layout.addLayout(section_row, 1)

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    def refresh(self) -> None:
        if not self.token:
            self.summary_label.setText("Sign in to load analytics.")
            return
        self.refresh_button.setEnabled(False)
        try:
            summary = self.api.get_dashboard_summary(token=self.token)
            self.summary_label.setText(
                "Database totals: "
                f"{summary.get('total_properties', 0)} properties · "
                f"{summary.get('total_clients', 0)} clients · "
                f"{summary.get('total_transactions', 0)} transactions · "
                f"{self._currency(summary.get('completed_revenue'))} completed revenue"
            )
            self._load_monthly()
            self._load_agents()
        except httpx.HTTPStatusError as exc:
            self._show_error(exc)
        except httpx.RequestError as exc:
            self.summary_label.setText("Unable to connect to the analytics API.")
            QMessageBox.warning(self, "Connection Error", str(exc))
        finally:
            self.refresh_button.setEnabled(True)

    def _load_monthly(self) -> None:
        trend = self.api.get_dashboard_transaction_trend(token=self.token)
        months = list(trend.get("months", []))
        counts = list(trend.get("counts", []))
        self.month_table.setRowCount(len(months))
        for row, (month, count) in enumerate(zip(months, counts)):
            self.month_table.setItem(row, 0, QTableWidgetItem(str(month)))
            self.month_table.setItem(row, 1, QTableWidgetItem(str(count)))

    def _load_agents(self) -> None:
        agents = self.api.get_dashboard_agent_performance(token=self.token)
        self.agent_table.setRowCount(len(agents))
        for row, agent in enumerate(agents):
            values = [
                f"{agent.get('full_name', '—')} ({agent.get('agent_id', '')})",
                str(agent.get("status") or "—"),
                str(agent.get("transactions", 0)),
                self._currency(agent.get("completed_revenue")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                self.agent_table.setItem(row, column, item)

    @staticmethod
    def _currency(value: Any) -> str:
        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "—"

    def _show_error(self, exc: httpx.HTTPStatusError) -> None:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        message = str(detail or f"The server returned HTTP {exc.response.status_code}.")
        self.summary_label.setText(message)
        QMessageBox.warning(self, "Analytics Error", message)
