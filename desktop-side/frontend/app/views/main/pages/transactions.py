from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.theme import badge_colors
from app.api.client import ApiClient

TRANSACTION_STATUS_COLORS = {
    "RESERVED": "#e8f0dc",
    "COMPLETED": "#dcebf1",
    "CANCELLED": "#f2dfdc",
}


class TransactionsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.transactions: list[dict[str, Any]] = []
        self._build_ui()

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(15)

        header = QHBoxLayout()
        title_stack = QVBoxLayout()
        title_stack.setSpacing(3)
        title = QLabel("Transaction Management")
        title.setStyleSheet("color: #17310a; font-size: 26px; font-weight: 700;")
        subtitle = QLabel("Monitor website and document-generated transactions.")
        subtitle.setStyleSheet("color: #60705a; font-size: 13px;")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()

        self.sync_button = QPushButton("Sync Transactions")
        self.sync_button.setFixedHeight(38)
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setIcon(qta.icon("fa5s.cloud-download-alt", color="#ffffff"))
        self.sync_button.setStyleSheet(self._primary_button_style())
        self.sync_button.clicked.connect(self.sync_transactions)
        header.addWidget(self.sync_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setFixedHeight(38)
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setIcon(qta.icon("fa5s.sync-alt", color="#486b2a"))
        self.refresh_button.clicked.connect(self.load_transactions)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.summary_label = QLabel("Sign in to load transactions.")
        self.summary_label.setStyleSheet(
            "color: #65745b; font-size: 12px; font-weight: 600;"
        )
        layout.addWidget(self.summary_label)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search transaction, client, property, agent..."
        )
        self.search_input.setFixedHeight(38)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.textChanged.connect(self.apply_filters)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #ffffff; border: 1px solid #cbd5c4; "
            "border-radius: 7px; padding: 0 12px; color: #17310a; font-size: 13px; }"
        )
        filters.addWidget(self.search_input, 1)

        self.status_filter = QComboBox()
        self.status_filter.setFixedHeight(38)
        self.status_filter.addItem("All Statuses", "")
        self.status_filter.addItem("Reserved", "RESERVED")
        self.status_filter.addItem("Completed", "COMPLETED")
        self.status_filter.addItem("Cancelled", "CANCELLED")
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        self.table = QTableWidget(0, 8)
        self.table.setHorizontalHeaderLabels(
            [
                "Transaction ID",
                "Client",
                "Property",
                "Agent",
                "Type",
                "Transaction Date",
                "Amount",
                "Status",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet(
            "QTableWidget { background: #ffffff; alternate-background-color: #f5f7f2; "
            "border: 1px solid #d4dccf; border-radius: 8px; color: #26351f; "
            "font-size: 13px; selection-background-color: #d6e8c9; "
            "selection-color: #17310a; }"
            "QTableWidget::item { padding: 8px; border-bottom: 1px solid #edf0eb; }"
            "QTableWidget::item:selected { background: #c8dfb7; color: #17310a; }"
            "QHeaderView::section { background: #e4ebdf; color: #17310a; border: none; "
            "border-bottom: 1px solid #cbd5c4; padding: 9px; font-size: 12px; "
            "font-weight: 700; }"
        )
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate([100, 150, 230, 140, 95, 125, 130, 110]):
            self.table.setColumnWidth(column, width)
        layout.addWidget(self.table, 1)

    @staticmethod
    def _primary_button_style() -> str:
        return (
            "QPushButton { background: #17310a; color: white; border: none; "
            "border-radius: 7px; padding: 0 14px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #285214; }"
            "QPushButton:disabled { background: #aeb8a7; }"
        )

    def load_transactions(self) -> None:
        if not self.token:
            self.summary_label.setText("Sign in to load transactions.")
            return
        self.refresh_button.setEnabled(False)
        try:
            self.transactions = self.api.get_transactions(token=self.token)
            summary = self.api.get_transaction_summary(token=self.token)
            self.summary_label.setText(
                f"{int(summary.get('total', 0)):,} transactions  ·  "
                f"{int(summary.get('reserved', 0)):,} reserved  ·  "
                f"{int(summary.get('completed', 0)):,} completed sales  ·  "
                f"{int(summary.get('cancelled', 0)):,} cancelled  ·  "
                f"Sales revenue: {self._format_currency(summary.get('amount_total'))}"
            )
            self.apply_filters()
        except httpx.HTTPStatusError as exc:
            self._show_error(exc)
        except httpx.RequestError as exc:
            self.summary_label.setText("Unable to connect to the server.")
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Unable to load transaction records.\n\n{exc}",
            )
        finally:
            self.refresh_button.setEnabled(True)

    def sync_transactions(self) -> None:
        if not self.token:
            self.summary_label.setText("Sign in to synchronize transactions.")
            return
        self.sync_button.setEnabled(False)
        try:
            result = self.api.sync_transactions(token=self.token)
            self.load_transactions()
            QMessageBox.information(
                self,
                "Transaction Sync Complete",
                f"Cloud rows: {result.get('total', 0)}\n"
                f"Added: {result.get('inserted', 0)}\n"
                f"Updated: {result.get('updated', 0)}\n"
                f"Errors: {result.get('errors', 0)}",
            )
        except httpx.HTTPStatusError as exc:
            self._show_error(exc, "Transaction Sync Failed")
        except httpx.RequestError as exc:
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Unable to synchronize transactions.\n\n{exc}",
            )
        finally:
            self.sync_button.setEnabled(True)

    def apply_filters(self, *_args: Any) -> None:
        search = self.search_input.text().strip().casefold()
        status_filter = str(self.status_filter.currentData() or "")
        visible = []
        for transaction in self.transactions:
            status = str(transaction.get("status") or "").upper()
            if status_filter and status != status_filter:
                continue
            search_text = " ".join(
                str(transaction.get(field) or "")
                for field in (
                    "transaction_id",
                    "client_name",
                    "property_title",
                    "agent_name",
                    "agent_id",
                    "property_id",
                )
            ).casefold()
            if search and search not in search_text:
                continue
            visible.append(transaction)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible))
        for row, transaction in enumerate(visible):
            transaction_id = str(transaction.get("transaction_id") or "")
            status = str(transaction.get("status") or "").upper()
            values = [
                transaction_id[:8],
                str(transaction.get("client_name") or "—"),
                str(transaction.get("property_title") or "—"),
                str(transaction.get("agent_name") or "—"),
                str(transaction.get("transaction_type") or "").title(),
                self._format_date(transaction.get("transaction_date")),
                self._format_currency(transaction.get("amount")),
                status,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(
                    transaction_id if column == 0 else value
                )
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, transaction_id)
                if column == 7:
                    _text, _bg = badge_colors(status)
                    item.setForeground(_text)
                    item.setBackground(_bg)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)

    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return "—"
        try:
            return datetime.fromisoformat(
                str(value).replace("Z", "+00:00")
            ).strftime("%b %d, %Y")
        except ValueError:
            return str(value)

    @staticmethod
    def _format_currency(value: Any) -> str:
        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "—"

    def _show_error(
        self,
        exc: httpx.HTTPStatusError,
        title: str = "Transaction Management Error",
    ) -> None:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        message = str(detail or f"The server returned HTTP {exc.response.status_code}.")
        self.summary_label.setText(message)
        QMessageBox.warning(self, title, message)
