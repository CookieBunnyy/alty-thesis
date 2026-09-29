from __future__ import annotations

from typing import Any

import httpx

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

import qtawesome as qta

from app.api.client import ApiClient


class AgentProfileDialog(QDialog):
    def __init__(
        self,
        agent: dict[str, Any],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)

        self.agent = agent

        self.setWindowTitle("Agent Profile")
        self.setMinimumSize(620, 520)

        self.setStyleSheet(
            """
            QDialog {
                background-color: #f7f9f3;
                color: #17310a;
            }

            QLabel {
                color: #17310a;
                background: transparent;
            }

            QFrame#profileCard {
                background-color: #ffffff;
                border: 1px solid #d9e2d0;
                border-radius: 10px;
            }

            QPushButton {
                background-color: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 6px;
                padding: 8px 14px;
            }

            QPushButton:hover {
                background-color: #dce8ce;
            }
            """
        )

        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(16)

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        header = QHBoxLayout()

        icon = QLabel()
        icon.setPixmap(
            qta.icon(
                "fa5s.user-tie",
                color="#486b2a",
            ).pixmap(42, 42)
        )

        header.addWidget(icon)

        information = QVBoxLayout()
        information.setSpacing(2)

        full_name = QLabel(
            self.agent.get("full_name") or "Unknown Agent"
        )
        full_name.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 22px;
                font-weight: 700;
            }
            """
        )

        agent_id = QLabel(
            f"Agent ID: {self.agent.get('agent_id', '—')}"
        )
        agent_id.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 12px;
            }
            """
        )

        information.addWidget(full_name)
        information.addWidget(agent_id)

        header.addLayout(information)
        header.addStretch()

        status = str(
            self.agent.get("status") or "ACTIVE"
        ).upper()

        status_label = QLabel(status)
        status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_label.setStyleSheet(
            """
            QLabel {
                background-color: #e5efdc;
                color: #486b2a;
                border-radius: 10px;
                padding: 5px 12px;
                font-size: 10px;
                font-weight: 700;
            }
            """
        )

        header.addWidget(status_label)

        layout.addLayout(header)

        # -------------------------------------------------
        # Profile Information
        # -------------------------------------------------

        profile_layout = QFormLayout()
        profile_layout.setHorizontalSpacing(30)
        profile_layout.setVerticalSpacing(10)

        profile_layout.addRow(
            "Phone Number",
            QLabel(
                str(
                    self.agent.get("phone_number")
                    or "—"
                )
            ),
        )

        profile_layout.addRow(
            "Agent Location",
            QLabel(
                str(
                    self.agent.get("agent_location")
                    or "—"
                )
            ),
        )

        profile_layout.addRow(
            "Latitude",
            QLabel(str(self.agent.get("latitude") or "—")),
        )
        profile_layout.addRow(
            "Longitude",
            QLabel(str(self.agent.get("longitude") or "—")),
        )

        rating = self._rating_text(
            self.agent.get("star_rating")
        )

        rating_label = QLabel(rating)
        rating_label.setStyleSheet(
            """
            QLabel {
                color: #486b2a;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        profile_layout.addRow(
            "Star Rating",
            rating_label,
        )

        layout.addLayout(profile_layout)

        # -------------------------------------------------
        # Performance Summary
        # -------------------------------------------------

        performance_title = QLabel(
            "Assignments & Performance"
        )

        performance_title.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 15px;
                font-weight: 700;
            }
            """
        )

        layout.addWidget(performance_title)

        metrics = QHBoxLayout()
        metrics.setSpacing(10)

        metrics.addWidget(
            self._metric_card(
                "Assignments",
                self.agent.get(
                    "assignments_count",
                    0,
                ),
            )
        )

        metrics.addWidget(
            self._metric_card(
                "Transactions",
                self.agent.get(
                    "transactions_count",
                    0,
                ),
            )
        )

        metrics.addWidget(
            self._metric_card(
                "Completed Sales",
                self.agent.get(
                    "completed_sales",
                    0,
                ),
            )
        )

        metrics.addWidget(
            self._metric_card(
                "Performance",
                self._format_percentage(
                    self.agent.get(
                        "performance_score"
                    )
                ),
            )
        )

        layout.addLayout(metrics)

        # -------------------------------------------------
        # Financial Summary
        # -------------------------------------------------

        financial_title = QLabel(
            "Sales & Commission"
        )

        financial_title.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 15px;
                font-weight: 700;
            }
            """
        )

        layout.addWidget(financial_title)

        financial = QFormLayout()

        financial.addRow(
            "Total Sales",
            QLabel(
                self._format_currency(
                    self.agent.get("total_sales")
                )
            ),
        )

        financial.addRow(
            "Total Commission",
            QLabel(
                self._format_currency(
                    self.agent.get(
                        "total_commission"
                    )
                )
            ),
        )

        layout.addLayout(financial)

        # -------------------------------------------------
        # Close
        # -------------------------------------------------

        close_button = QPushButton("Close")
        close_button.setIcon(
            qta.icon(
                "fa5s.times",
                color="#17310a",
            )
        )

        close_button.clicked.connect(self.accept)

        button_layout = QHBoxLayout()
        button_layout.addStretch()
        button_layout.addWidget(close_button)

        layout.addLayout(button_layout)

    @staticmethod
    def _metric_card(
        title: str,
        value: Any,
    ) -> QWidget:

        card = QWidget()

        card.setStyleSheet(
            """
            QWidget {
                background-color: #ffffff;
                border: 1px solid #d9e2d0;
                border-radius: 8px;
            }
            """
        )

        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 10, 12, 10)

        value_label = QLabel(str(value))

        value_label.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 20px;
                font-weight: 700;
                border: none;
            }
            """
        )

        title_label = QLabel(title)

        title_label.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 10px;
                border: none;
            }
            """
        )

        layout.addWidget(value_label)
        layout.addWidget(title_label)

        return card

    @staticmethod
    def _rating_text(value: Any) -> str:
        try:
            rating = float(value or 0)
        except (TypeError, ValueError):
            rating = 0

        full_stars = int(round(rating))

        stars = "★" * full_stars
        empty = "☆" * max(0, 5 - full_stars)

        return f"{stars}{empty}  {rating:.1f}/5"

    @staticmethod
    def _format_currency(value: Any) -> str:
        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "₱0.00"

    @staticmethod
    def _format_percentage(value: Any) -> str:
        try:
            return f"{float(value):.1f}%"
        except (TypeError, ValueError):
            return "0.0%"


class AgentsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()

        self.controller = controller
        self.api = ApiClient()
        self.agents: list[dict[str, Any]] = []

        self._build_ui()
        if self.token:
            self.load_agents()
        else:
            self.count_label.setText("Sign in to load agents.")

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    # =========================================================
    # UI
    # =========================================================

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)

        layout.setContentsMargins(
            20,
            18,
            20,
            20,
        )

        layout.setSpacing(14)

        # -------------------------------------------------
        # Header
        # -------------------------------------------------

        header = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title = QLabel("Agent Management")

        title.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 26px;
                font-weight: 700;
            }
            """
        )

        subtitle = QLabel(
            "Manage agent profiles, assignments, "
            "transactions, and performance."
        )

        subtitle.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 13px;
            }
            """
        )

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header.addLayout(title_layout)
        header.addStretch()

        self.sync_button = QPushButton("Sync from Supabase")
        self.sync_button.setIcon(qta.icon("fa5s.cloud-download-alt", color="#17310a"))
        self.sync_button.clicked.connect(self.sync_agents)
        header.addWidget(self.sync_button)

        self.refresh_button = QPushButton("Refresh")

        self.refresh_button.setIcon(
            qta.icon(
                "fa5s.sync-alt",
                color="#17310a",
            )
        )

        self.refresh_button.clicked.connect(
            self.load_agents
        )

        header.addWidget(
            self.refresh_button
        )

        layout.addLayout(header)

        # -------------------------------------------------
        # Search
        # -------------------------------------------------

        search_layout = QHBoxLayout()

        search_icon = QLabel()

        search_icon.setPixmap(
            qta.icon(
                "fa5s.search",
                color="#486b2a",
            ).pixmap(16, 16)
        )

        search_layout.addWidget(
            search_icon
        )

        self.search_input = QLineEdit()

        self.search_input.setPlaceholderText(
            "Search agent name, Agent ID, phone, or location..."
        )

        self.search_input.setFixedHeight(38)
        self.search_input.setClearButtonEnabled(True)

        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #ffffff;
                color: #17310a;
                border: 1px solid #cbd6c1;
                border-radius: 7px;
                padding: 0 12px;
                font-size: 13px;
            }

            QLineEdit:focus {
                border: 1px solid #6b8e52;
            }
            """
        )

        self.search_input.textChanged.connect(
            self.filter_agents
        )

        search_layout.addWidget(
            self.search_input
        )

        layout.addLayout(search_layout)

        # -------------------------------------------------
        # Count
        # -------------------------------------------------

        self.count_label = QLabel(
            "0 agents"
        )

        self.count_label.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 12px;
                font-weight: 600;
            }
            """
        )

        layout.addWidget(
            self.count_label
        )

        # -------------------------------------------------
        # Table
        # -------------------------------------------------

        self.table = QTableWidget(
            0,
            9,
        )

        self.table.setHorizontalHeaderLabels(
            [
                "Agent ID",
                "Full Name",
                "Phone Number",
                "Location",
                "Rating",
                "Assignments",
                "Transactions",
                "Performance",
                "Status",
            ]
        )

        self.table.setAlternatingRowColors(
            True
        )

        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )

        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )

        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )

        self.table.setSortingEnabled(True)

        self.table.verticalHeader().setVisible(
            False
        )

        self.table.setShowGrid(False)

        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f5f7f2;
                border: 1px solid #d9e2d0;
                border-radius: 8px;
                color: #26351f;
                font-size: 13px;
                selection-background-color: #d6e8c9;
                selection-color: #17310a;
            }

            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #edf0eb;
            }

            QHeaderView::section {
                background-color: #eef3e5;
                color: #526449;
                padding: 9px;
                border: none;
                border-bottom: 1px solid #d4ddcc;
                font-weight: 700;
            }
            """
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            7,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            8,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.table.cellDoubleClicked.connect(
            self.open_agent_profile
        )

        layout.addWidget(
            self.table,
            1,
        )

    # =========================================================
    # Message Box Styling
    # =========================================================

    def _show_message(
        self,
        title: str,
        message: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    ) -> None:
        """Show a light-themed message box regardless of the global app theme."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(icon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox {
                background-color: #ffffff;
                color: #17310a;
                border: 1px solid #d5dfcc;
            }

            QMessageBox QLabel {
                background-color: #ffffff;
                color: #17310a;
                font-size: 13px;
            }

            QMessageBox QPushButton {
                background-color: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 5px;
                padding: 6px 18px;
                min-width: 60px;
                min-height: 28px;
                font-weight: 600;
            }

            QMessageBox QPushButton:hover {
                background-color: #dcebd3;
                border-color: #9eb78e;
            }

            QMessageBox QPushButton:pressed {
                background-color: #cddfc1;
            }
            """
        )
        box.exec()

    # =========================================================
    # Load Agents
    # =========================================================

    def load_agents(self) -> None:
        if not self.token:
            self.count_label.setText("Sign in to load agents.")
            return
        self.refresh_button.setEnabled(
            False
        )

        self.count_label.setText(
            "Loading agents..."
        )

        try:
            data = self.api.get_agents(token=self.token)

            if not isinstance(data, list):
                raise RuntimeError(
                    "Invalid agent response from server."
                )

            self.agents = data

            self.filter_agents()

        except httpx.RequestError as exc:
            self.count_label.setText(
                "Unable to connect to server."
            )

            self._show_message(
                "Connection Error",
                (
                    "Unable to connect to the FastAPI server.\n\n"
                    "Make sure the backend is running.\n\n"
                    f"Details: {exc}"
                ),
                QMessageBox.Icon.Warning,
            )

        except httpx.HTTPStatusError as exc:
            self.count_label.setText(
                "Server error."
            )

            self._show_message(
                "Server Error",
                (
                    f"The server returned HTTP "
                    f"{exc.response.status_code}."
                ),
                QMessageBox.Icon.Warning,
            )

        except Exception as exc:
            self.count_label.setText(
                "Unable to load agents."
            )

            self._show_message(
                "Agent Loading Error",
                str(exc),
                QMessageBox.Icon.Warning,
            )

        finally:
            self.refresh_button.setEnabled(
                True
            )

    def sync_agents(self) -> None:
        if not self.token:
            self.count_label.setText("Sign in to synchronize agents.")
            return
        self.sync_button.setEnabled(False)
        self.count_label.setText("Synchronizing agents from Supabase...")
        try:
            result = self.api.sync_agents(token=self.token)
            self.load_agents()
            self._show_message(
                "Agent Sync Complete",
                (
                    f"Supabase records: {result.get('total', 0)}\n"
                    f"Inserted: {result.get('inserted', 0)}\n"
                    f"Updated: {result.get('updated', 0)}\n"
                    f"Skipped with errors: {result.get('errors', 0)}"
                ),
            )
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail", "")
            except ValueError:
                detail = ""
            self._show_message(
                "Agent Sync Failed",
                str(detail or f"The server returned HTTP {exc.response.status_code}."),
                QMessageBox.Icon.Warning,
            )
        except httpx.RequestError as exc:
            self._show_message(
                "Connection Error",
                f"Unable to connect to the FastAPI server.\n\n{exc}",
                QMessageBox.Icon.Warning,
            )
        except Exception as exc:
            self._show_message(
                "Agent Sync Failed",
                str(exc),
                QMessageBox.Icon.Warning,
            )
        finally:
            self.sync_button.setEnabled(True)

    # =========================================================
    # Filtering
    # =========================================================

    def filter_agents(
        self,
        _text: str = "",
    ) -> None:

        search = (
            self.search_input.text()
            .strip()
            .lower()
        )

        if not search:
            filtered = self.agents
        else:
            filtered = []

            for agent in self.agents:
                searchable = " ".join(
                    [
                        str(
                            agent.get(
                                "agent_id"
                            )
                            or ""
                        ),
                        str(
                            agent.get(
                                "full_name"
                            )
                            or ""
                        ),
                        str(
                            agent.get(
                                "phone_number"
                            )
                            or ""
                        ),
                        str(
                            agent.get(
                                "agent_location"
                            )
                            or ""
                        ),
                    ]
                ).lower()

                if search in searchable:
                    filtered.append(agent)

        self.populate_table(
            filtered
        )

    # =========================================================
    # Table
    # =========================================================

    def populate_table(
        self,
        agents: list[dict[str, Any]],
    ) -> None:

        self.table.setSortingEnabled(
            False
        )

        self.table.setRowCount(
            len(agents)
        )

        for row, agent in enumerate(
            agents
        ):

            values = [
                agent.get("agent_id"),
                agent.get("full_name"),
                agent.get("phone_number"),
                agent.get("agent_location"),
                self.rating_display(
                    agent.get("star_rating")
                ),
                agent.get(
                    "assignments_count",
                    0,
                ),
                agent.get(
                    "transactions_count",
                    0,
                ),
                self.format_percentage(
                    agent.get(
                        "performance_score"
                    )
                ),
                agent.get(
                    "status",
                    "ACTIVE",
                ),
            ]

            for column, value in enumerate(
                values
            ):

                item = QTableWidgetItem(
                    str(
                        value
                        if value is not None
                        else "—"
                    )
                )

                if column in (
                    0,
                    4,
                    5,
                    6,
                    7,
                    8,
                ):
                    item.setTextAlignment(
                        Qt.AlignmentFlag.AlignCenter
                    )

                if column == 8:
                    status = str(
                        agent.get(
                            "status",
                            "ACTIVE",
                        )
                    ).upper()

                    if status == "ACTIVE":
                        item.setForeground(
                            Qt.GlobalColor.darkGreen
                        )
                    elif status in (
                        "INACTIVE",
                        "SUSPENDED",
                    ):
                        item.setForeground(
                            Qt.GlobalColor.darkRed
                        )

                self.table.setItem(
                    row,
                    column,
                    item,
                )

            # Store the complete agent record
            # in the first cell.
            self.table.item(
                row,
                0,
            ).setData(
                Qt.ItemDataRole.UserRole,
                agent,
            )

        self.table.setSortingEnabled(
            True
        )

        self.count_label.setText(
            f"{len(agents)} "
            f"{'agent' if len(agents) == 1 else 'agents'}"
        )

    # =========================================================
    # Agent Profile
    # =========================================================

    def open_agent_profile(
        self,
        row: int,
        _column: int,
    ) -> None:

        item = self.table.item(
            row,
            0,
        )

        if item is None:
            return

        agent = item.data(
            Qt.ItemDataRole.UserRole
        )

        if not agent:
            return

        dialog = AgentProfileDialog(
            agent,
            self,
        )

        dialog.exec()

    # =========================================================
    # Helpers
    # =========================================================

    @staticmethod
    def rating_display(
        value: Any,
    ) -> str:

        try:
            rating = float(
                value or 0
            )
        except (
            TypeError,
            ValueError,
        ):
            rating = 0

        rounded = int(
            round(rating)
        )

        return (
            "★" * rounded
            + "☆" * max(
                0,
                5 - rounded,
            )
            + f" {rating:.1f}"
        )

    @staticmethod
    def format_percentage(
        value: Any,
    ) -> str:

        try:
            return f"{float(value):.1f}%"
        except (
            TypeError,
            ValueError,
        ):
            return "0.0%"