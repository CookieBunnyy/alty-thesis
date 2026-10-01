from __future__ import annotations

from datetime import datetime
from typing import Any

import httpx
import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
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

STATUS_COLORS = {
    "PROSPECT": "#f3ecd6",
    "RESERVED": "#dcebd3",
    "SOLD": "#d9e8ef",
    "CANCELLED": "#f2dfdc",
}


class ClientSummaryCard(QWidget):
    def __init__(self, title: str, accent: str) -> None:
        super().__init__()
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("summaryCard")
        self.setStyleSheet(
            "QWidget#summaryCard { background: #f7f9f3; border: 1px solid #d9e2d0; "
            "border-radius: 12px; } QLabel { background: transparent; border: none; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(5)

        self.value_label = QLabel("—")
        self.value_label.setStyleSheet(
            f"color: {accent}; font-size: 24px; font-weight: 700; border: none;"
        )
        title_label = QLabel(title)
        title_label.setStyleSheet(
            "color: #65745b; font-size: 12px; font-weight: 600; border: none;"
        )
        layout.addWidget(self.value_label)
        layout.addWidget(title_label)

    def set_value(self, value: int) -> None:
        self.value_label.setText(f"{value:,}")


class ClientProfileDialog(QDialog):
    def __init__(self, client: dict[str, Any], parent=None,
                 profile: dict[str, Any] | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Client Profile")
        self.setMinimumWidth(620)
        self.setStyleSheet(
            "QDialog { background: #f7f9f3; color: #17310a; }"
            "QLabel { background: transparent; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 20, 22, 18)
        layout.setSpacing(14)

        full_name = QLabel(str(client.get("full_name") or "Client"))
        full_name.setStyleSheet(
            "font-size: 21px; font-weight: 700; color: #17310a;"
        )
        layout.addWidget(full_name)

        transaction_type = str(client.get("transaction_type") or "").upper()
        client_status = str(client.get("status") or "").upper()
        outcome = {
            "SOLD": "Purchased / Sold property",
            "CANCELLED": "Cancelled transaction",
            "PROSPECT": "Prospective buyer (no transaction yet)",
        }.get(client_status, "Reserved property")
        outcome_label = QLabel(outcome)
        outcome_label.setStyleSheet(
            f"background: {STATUS_COLORS.get(client_status, '#e7eedc')}; "
            "color: #17310a; border-radius: 6px; padding: 7px 10px; "
            "font-size: 12px; font-weight: 700;"
        )
        layout.addWidget(outcome_label)

        details = QFormLayout()
        details.setHorizontalSpacing(10)
        details.setVerticalSpacing(10)
        fields = [
            ("Client ID", client.get("external_client_id") or client.get("client_id")),
            ("Location", client.get("location")),
            ("Phone Number", client.get("phone_number")),
            ("Email", client.get("email")),
            ("Property ID", client.get("property_id")),
            ("Property Name", client.get("property_title")),
            ("Property Location", client.get("property_location")),
            ("Property Price", self._format_currency(client.get("property_price"))),
            ("Agent ID", client.get("agent_id")),
            ("Agent Name", client.get("agent_name")),
            ("Transaction ID", client.get("transaction_id")),
            ("Transaction Type", transaction_type.title()),
            ("Transaction Date", self._format_date(client.get("transaction_date"))),
            ("Transaction Amount", self._format_currency(client.get("amount"))),
            ("Current Status", client_status),
            ("Occupation", client.get("occupation")),
            ("Civil Status", client.get("civil_status")),
            ("Preferred Contact", client.get("preferred_contact")),
            ("Purpose of Purchase", client.get("purpose_of_purchase")),
            ("Source", client.get("source")),
        ]
        for label, value in fields:
            value_label = QLabel(str(value) if value not in (None, "") else "—")
            value_label.setWordWrap(True)
            value_label.setStyleSheet(
                "color: #26351f; font-size: 13px; padding: 2px;"
            )
            details.addRow(f"{label}:", value_label)
        layout.addLayout(details)

        if profile is not None:
            layout.addWidget(self._section("Transaction History"))
            history = QTableWidget(len(profile.get("transactions", [])), 6)
            history.setHorizontalHeaderLabels(["Date", "Type", "Status", "Amount", "Property", "Agent"])
            for row, item in enumerate(profile.get("transactions", [])):
                values = [
                    self._format_date(item.get("transaction_date")), item.get("transaction_type"),
                    item.get("status"), self._format_currency(item.get("amount")),
                    item.get("property_title"), item.get("agent_name"),
                ]
                for column, value in enumerate(values):
                    history.setItem(row, column, QTableWidgetItem(str(value or "—")))
            history.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            history.horizontalHeader().setStretchLastSection(True)
            history.setMaximumHeight(150)
            layout.addWidget(history)

            layout.addWidget(self._section("Related Documents"))
            documents = profile.get("documents", [])
            docs = QTableWidget(len(documents), 4)
            docs.setHorizontalHeaderLabels(["Document", "Type", "Status", "Uploaded"])
            for row, item in enumerate(documents):
                values = [item.get("document_name"), item.get("document_type"), item.get("status"),
                          self._format_date(item.get("created_at"))]
                for column, value in enumerate(values):
                    docs.setItem(row, column, QTableWidgetItem(str(value or "—")))
            docs.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
            docs.horizontalHeader().setStretchLastSection(True)
            docs.setMaximumHeight(130)
            layout.addWidget(docs)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            return str(value)

    @staticmethod
    def _format_currency(value: Any) -> str:
        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "—"

    @staticmethod
    def _section(text: str) -> QLabel:
        label = QLabel(text)
        label.setStyleSheet("font-size: 14px; font-weight: 700; color: #17310a; padding-top: 6px;")
        return label


class ClientsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.clients: list[dict[str, Any]] = []
        self.clients_by_id: dict[str, dict[str, Any]] = {}
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
        title = QLabel("Client Management")
        title.setStyleSheet(
            "color: #17310a; font-size: 26px; font-weight: 700;"
        )
        subtitle = QLabel(
            "Clients are created automatically from buyer, reservation and sale "
            "documents and from website transactions."
        )
        subtitle.setStyleSheet("color: #60705a; font-size: 13px;")
        title_stack.addWidget(title)
        title_stack.addWidget(subtitle)
        header.addLayout(title_stack)
        header.addStretch()

        self.profile_button = QPushButton("View Profile")
        self.profile_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.profile_button.setFixedHeight(38)
        self.profile_button.setIcon(qta.icon("fa5s.user", color="#486b2a"))
        self.profile_button.setEnabled(False)
        self.profile_button.clicked.connect(self.view_selected_client)
        header.addWidget(self.profile_button)

        self.delete_button = QPushButton("Delete Client")
        self.delete_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_button.setFixedHeight(38)
        self.delete_button.setIcon(qta.icon("fa5s.trash-alt", color="#9b3030"))
        self.delete_button.setEnabled(False)
        self.delete_button.clicked.connect(self.delete_selected_client)
        self._apply_permissions()
        header.addWidget(self.delete_button)

        self.sync_button = QPushButton("Sync from Supabase")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setFixedHeight(38)
        self.sync_button.setIcon(qta.icon("fa5s.cloud-download-alt", color="#ffffff"))
        self.sync_button.setStyleSheet(self._primary_button_style())
        self.sync_button.clicked.connect(self.sync_clients)
        header.addWidget(self.sync_button)

        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.refresh_button.setFixedHeight(38)
        self.refresh_button.setIcon(qta.icon("fa5s.sync-alt", color="#486b2a"))
        self.refresh_button.clicked.connect(self.load_clients)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        summary_row = QHBoxLayout()
        summary_row.setSpacing(12)
        self.total_card = ClientSummaryCard("Total Clients", "#17310a")
        self.prospect_card = ClientSummaryCard("Prospects", "#9a6a13")
        self.reserved_card = ClientSummaryCard("Reserved Clients", "#486b2a")
        self.sold_card = ClientSummaryCard("Completed / Sold", "#477489")
        self.cancelled_card = ClientSummaryCard("Cancelled", "#9b5555")
        summary_row.addWidget(self.total_card)
        summary_row.addWidget(self.prospect_card)
        summary_row.addWidget(self.reserved_card)
        summary_row.addWidget(self.sold_card)
        summary_row.addWidget(self.cancelled_card)
        layout.addLayout(summary_row)

        filters = QHBoxLayout()
        filters.setSpacing(10)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search client, phone, property, or location..."
        )
        self.search_input.setFixedHeight(38)
        self.search_input.setClearButtonEnabled(True)
        self.search_input.setStyleSheet(
            "QLineEdit { background: #ffffff; border: 1px solid #cbd5c4; "
            "border-radius: 7px; padding: 0 12px; color: #17310a; font-size: 13px; }"
            "QLineEdit:focus { border: 1px solid #5d7d4e; }"
        )
        self.search_input.textChanged.connect(self.apply_filters)
        filters.addWidget(self.search_input, 1)

        self.status_filter = QComboBox()
        self.status_filter.setFixedHeight(38)
        self.status_filter.addItem("All Clients", "")
        self.status_filter.addItem("Prospect", "PROSPECT")
        self.status_filter.addItem("Reserved", "RESERVED")
        self.status_filter.addItem("Sold", "SOLD")
        self.status_filter.addItem("Cancelled", "CANCELLED")
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        filters.addWidget(self.status_filter)
        layout.addLayout(filters)

        self.count_label = QLabel("Sign in to load clients.")
        self.count_label.setStyleSheet(
            "color: #65745b; font-size: 12px; font-weight: 600;"
        )
        layout.addWidget(self.count_label)

        self.table = QTableWidget(0, 9)
        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Client Name",
                "Location",
                "Phone Number",
                "Property",
                "Agent",
                "Type",
                "Transaction Date",
                "Status",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QTableWidget.SelectionBehavior.SelectRows
        )
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
            "QTableWidget::item:selected:!active { background: #dcebd3; color: #17310a; }"
            "QHeaderView::section { background: #e4ebdf; color: #17310a; border: none; "
            "border-bottom: 1px solid #cbd5c4; padding: 9px; font-size: 12px; "
            "font-weight: 700; }"
        )
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        for column, width in enumerate(
            [75, 125, 145, 110, 220, 135, 80, 120, 90]
        ):
            self.table.setColumnWidth(column, width)
        self.table.cellDoubleClicked.connect(self.open_client_profile)
        self.table.itemSelectionChanged.connect(self._update_profile_button)
        layout.addWidget(self.table, 1)

    @staticmethod
    def _primary_button_style() -> str:
        return (
            "QPushButton { background: #17310a; color: white; border: none; "
            "border-radius: 7px; padding: 0 14px; font-size: 13px; font-weight: 600; }"
            "QPushButton:hover { background: #285214; }"
            "QPushButton:disabled { background: #aeb8a7; }"
        )

    def load_clients(self) -> None:
        self._apply_permissions()
        if not self.token:
            self.count_label.setText("Sign in to load clients.")
            return
        self.refresh_button.setEnabled(False)
        try:
            self.clients = self.api.get_clients(token=self.token)
            summary = self.api.get_client_summary(token=self.token)
            self.total_card.set_value(int(summary.get("total", 0)))
            self.prospect_card.set_value(int(summary.get("prospect", 0)))
            self.reserved_card.set_value(int(summary.get("reserved", 0)))
            self.sold_card.set_value(int(summary.get("sold", 0)))
            self.cancelled_card.set_value(int(summary.get("cancelled", 0)))
            self.clients_by_id = {
                str(client["client_id"]): client
                for client in self.clients
                if client.get("client_id")
            }
            self.apply_filters()
        except httpx.HTTPStatusError as exc:
            self._show_api_error(exc)
        except httpx.RequestError as exc:
            self.count_label.setText("Unable to connect to the server.")
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Unable to load clients from the FastAPI server.\n\n{exc}",
            )
        finally:
            self.refresh_button.setEnabled(True)

    def sync_clients(self) -> None:
        if not self.token:
            self.count_label.setText("Sign in to synchronize clients.")
            return
        self.sync_button.setEnabled(False)
        try:
            result = self.api.sync_clients(token=self.token)
            self.load_clients()
            QMessageBox.information(
                self,
                "Client Sync Complete",
                "Supabase records: {total}\nAdded: {inserted}\nUpdated: {updated}\n"
                "Kept local (pending push): {skipped_pending}\n"
                "Skipped with errors: {errors}".format(**{"skipped_pending": 0, **result}),
            )
        except httpx.HTTPStatusError as exc:
            self._show_api_error(exc, "Client Sync Failed")
        except httpx.RequestError as exc:
            QMessageBox.warning(
                self,
                "Connection Error",
                f"Unable to synchronize clients from Supabase.\n\n{exc}",
            )
        finally:
            self.sync_button.setEnabled(True)

    def apply_filters(self, *_args: Any) -> None:
        query = self.search_input.text().strip().casefold()
        status = str(self.status_filter.currentData() or "")
        visible_clients = []
        for client in self.clients:
            if status and str(client.get("status", "")).upper() != status:
                continue
            searchable = " ".join(
                str(client.get(field) or "")
                for field in (
                    "full_name",
                    "external_client_id",
                    "location",
                    "phone_number",
                    "email",
                    "property_title",
                    "property_location",
                    "agent_name",
                    "agent_id",
                    "property_id",
                )
            ).casefold()
            if query and query not in searchable:
                continue
            visible_clients.append(client)

        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(visible_clients))
        for row, client in enumerate(visible_clients):
            status_value = str(client.get("status") or "").upper()
            values = [
                str(client.get("external_client_id") or str(client.get("client_id") or "")[:8]),
                str(client.get("full_name") or ""),
                str(client.get("location") or "—"),
                str(client.get("phone_number") or "—"),
                str(client.get("property_title") or "—"),
                str(client.get("agent_name") or "—"),
                str(client.get("transaction_type") or "—").title(),
                self._format_date(client.get("transaction_date")),
                status_value,
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(value)
                item.setTextAlignment(
                    Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
                )
                if column == 0:
                    full_client_id = str(client.get("client_id") or "")
                    item.setData(Qt.ItemDataRole.UserRole, full_client_id)
                    item.setToolTip(full_client_id)
                if column == 8:
                    _text, _bg = badge_colors(status_value)
                    item.setForeground(_text)
                    item.setBackground(_bg)
                    font = item.font()
                    font.setBold(True)
                    item.setFont(font)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)
        self.count_label.setText(
            f"{len(visible_clients):,} of {len(self.clients):,} clients"
        )

    @staticmethod
    def _format_date(value: Any) -> str:
        if not value:
            return "—"
        try:
            parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
            return parsed.strftime("%b %d, %Y")
        except ValueError:
            return str(value)

    def open_client_profile(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        client_id = item.data(Qt.ItemDataRole.UserRole) or item.text()
        client = self.clients_by_id.get(str(client_id))
        if client is None:
            return
        try:
            profile = self.api.get_client_profile(str(client_id), token=self.token)
            client = profile.get("client", client)
        except (httpx.HTTPError, ValueError):
            profile = None  # still show the row data
        ClientProfileDialog(client, self, profile).exec()

    def view_selected_client(self) -> None:
        row = self.table.currentRow()
        if row >= 0:
            self.open_client_profile(row, 0)

    def _update_profile_button(self) -> None:
        selected = self.table.currentRow() >= 0
        self.profile_button.setEnabled(selected)
        self.delete_button.setEnabled(selected)

    def _apply_permissions(self) -> None:
        user_role = (
            self.controller.session.state.role.casefold()
            if self.controller is not None
            else ""
        )
        self.delete_button.setVisible(
            user_role in {"administrator", "general manager", "president"}
        )

    def delete_selected_client(self) -> None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        client_id = item.data(Qt.ItemDataRole.UserRole) if item else None
        client = self.clients_by_id.get(str(client_id)) if client_id else None
        if client is None:
            QMessageBox.warning(self, "Delete Client", "Select a client first.")
            return

        property_title = client.get("property_title") or "the linked property"
        confirmation = QMessageBox(self)
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setWindowTitle("Delete Client and History")
        confirmation.setText(
            f"Permanently delete {client.get('full_name') or 'this client'} "
            f"and their reservation history for {property_title}? "
            "Only clients created in error without a completed sale can be deleted. "
            "A reserved property will return to AVAILABLE. This cannot be undone."
        )
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel
        )
        confirmation.button(QMessageBox.StandardButton.Yes).setText("Delete")
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        answer = confirmation.exec()
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_client(str(client_id), token=self.token)
            self.load_clients()
        except httpx.HTTPStatusError as exc:
            self._show_api_error(exc, "Delete Client Failed")
        except httpx.RequestError as exc:
            QMessageBox.warning(
                self,
                "Delete Client Failed",
                f"Unable to connect to the FastAPI server.\n\n{exc}",
            )
        except Exception as exc:
            QMessageBox.critical(
                self,
                "Delete Client Failed",
                f"The client could not be deleted: {exc}",
            )

    def _show_api_error(
        self, exc: httpx.HTTPStatusError, title: str = "Client Management Error"
    ) -> None:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        message = str(detail or f"The server returned HTTP {exc.response.status_code}.")
        self.count_label.setText(message)
        QMessageBox.warning(self, title, message)
