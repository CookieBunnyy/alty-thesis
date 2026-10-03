from __future__ import annotations

from datetime import datetime

from PyQt6.QtCore import QRectF, Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api.client import ApiClient
from app.theme import TOKENS


def status_colors() -> dict[str, str]:
    """Donut/legend colours for the active theme (read at paint time)."""
    return {
        "available": TOKENS["accent"],
        "reserved": TOKENS["info"],
        "sold": TOKENS["chart_bar"],
        "on_hold": TOKENS["warning"],
        "unavailable": TOKENS["danger"],
    }


class StatCard(QWidget):
    def __init__(self, value: str, label: str, delta: str, accent: str = "#486b2a") -> None:
        super().__init__()
        # Plain QWidget subclasses only paint stylesheet backgrounds with this.
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setObjectName("statCard")
        self.setStyleSheet(
            """
            QWidget#statCard {
                background: #f7f9f3;
                border: 1px solid #d9e2d0;
                border-radius: 14px;
            }
            QLabel { background: transparent; border: none; }
            """
        )
        self.value = value
        self.label = label
        self.delta = delta
        self.accent = accent
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 14, 18, 14)
        layout.setSpacing(8)

        top = QHBoxLayout()
        self.card_label = QLabel(self.label)
        self.card_label.setStyleSheet("color: #708064; font-size: 12px; font-weight: 600;")
        top.addWidget(self.card_label)
        top.addStretch()

        more = QLabel("")
        more.setStyleSheet("color: #9aa58f; font-size: 16px;")
        top.addWidget(more)
        layout.addLayout(top)

        self.value_label = QLabel(self.value)
        self.value_label.setStyleSheet("color: #17240f; font-size: 30px; font-weight: 800;")
        layout.addWidget(self.value_label)

        self.delta_label = QLabel(self.delta)
        self.delta_label.setStyleSheet(
            f"color: {self.accent}; font-size: 12px; font-weight: 700;"
        )
        layout.addWidget(self.delta_label)

    def set_value(self, value: str) -> None:
        self.value = value
        self.value_label.setText(value)


class TrendChart(QWidget):
    def __init__(self, months=None, values=None) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent; border: none;")
        self.months = months or []
        self.values = values or []
        self.setMinimumHeight(230)

    def set_data(self, months: list[str], values: list[int]) -> None:
        self.months = months
        self.values = values
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(8, 22, -8, -26)
        if not self.values or not any(self.values):
            painter.setPen(QPen(QColor(TOKENS["text_faint"]), 1))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, "Insufficient transaction history")
            return
        count = len(self.values)
        slot = rect.width() / count
        bar_width = max(10.0, min(46.0, slot * 0.62))
        peak = max(self.values) or 1
        small = painter.font()
        small.setPointSizeF(max(7.5, small.pointSizeF() - 1))
        painter.setFont(small)
        for index, value in enumerate(self.values):
            x = rect.left() + slot * index + (slot - bar_width) / 2
            height = max(4.0, (value / peak) * (rect.height() - 18)) if value else 4.0
            y = rect.bottom() - height
            current = index == count - 1
            color = QColor(TOKENS["accent"] if current else (TOKENS["chart_bar"] if value else TOKENS["border_strong"]))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(color)
            painter.drawRoundedRect(QRectF(x, y, bar_width, height), 7, 7)
            if value:
                painter.setPen(QPen(QColor(TOKENS["accent_ink"] if current else TOKENS["text"]), 1))
                label_rect = QRectF(x - 6, y - 18, bar_width + 12, 16)
                painter.drawText(label_rect, Qt.AlignmentFlag.AlignCenter, str(value))
            month = self.months[index] if index < len(self.months) else ""
            painter.setPen(QPen(QColor(TOKENS["text"] if current else TOKENS["text_faint"]), 1))
            painter.drawText(QRectF(x - 10, rect.bottom() + 6, bar_width + 20, 16),
                             Qt.AlignmentFlag.AlignCenter, _month_label(month))


def _month_label(value: str) -> str:
    names = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
    try:
        return names[int(value[5:7]) - 1]
    except (ValueError, IndexError):
        return value


class StatusDonutChart(QWidget):
    def __init__(
        self,
        available: int = 0,
        reserved: int = 0,
        sold: int = 0,
        on_hold: int = 0,
        unavailable: int = 0,
    ) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent; border: none;")
        self.set_counts(available, reserved, sold, on_hold, unavailable)
        self.setMinimumHeight(220)

    def set_counts(
        self,
        available: int,
        reserved: int,
        sold: int,
        on_hold: int,
        unavailable: int,
    ) -> None:
        self.available = available
        self.reserved = reserved
        self.sold = sold
        self.on_hold = on_hold
        self.unavailable = unavailable
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        radius = min(self.rect().width(), self.rect().height()) * 0.36
        total = (
            self.available
            + self.reserved
            + self.sold
            + self.on_hold
            + self.unavailable
        )
        segments = []
        if total:
            segments = [
                (self.available / total, QColor(status_colors()["available"])),
                (self.reserved / total, QColor(status_colors()["reserved"])),
                (self.sold / total, QColor(status_colors()["sold"])),
                (self.on_hold / total, QColor(status_colors()["on_hold"])),
                (self.unavailable / total, QColor(status_colors()["unavailable"])),
            ]

        start_angle = 90 * 16
        for ratio, color in segments:
            span = int(360 * ratio * 16)
            painter.setPen(QPen(color, 22, Qt.PenStyle.SolidLine, Qt.PenCapStyle.FlatCap))
            painter.drawArc(
                int(center.x() - radius),
                int(center.y() - radius),
                int(radius * 2),
                int(radius * 2),
                start_angle,
                span,
            )
            start_angle -= span

        inner_radius = radius * 0.72
        painter.setPen(QPen(QColor(TOKENS["card"]), 12))
        painter.drawEllipse(
            int(center.x() - inner_radius),
            int(center.y() - inner_radius),
            int(inner_radius * 2),
            int(inner_radius * 2),
        )

        painter.setPen(QPen(QColor(TOKENS["text"]), 1))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(total))


class DashboardPage(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()

        self.controller = controller
        self.api = ApiClient()
        self.total_properties_card = None
        self.active_clients_card = None
        self.transaction_card = None
        self.revenue_card = None
        self.total_agents_card = None
        self.pending_documents_card = None

        self.setStyleSheet(
            """
            QWidget { background: transparent; }
            QLabel { background: transparent; }
            QTableWidget {
                background: #f7f9f3;
                border: none;
                border-radius: 12px;
                color: #17240f;
            }
            QHeaderView::section {
                background: #eef3e5;
                color: #65745b;
                border: none;
                font-weight: 700;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        stats = QGridLayout()
        stats.setSpacing(16)
        self.total_properties_card = StatCard(
            "—",
            "Total Properties",
            "From property records",
            "#486b2a",
        )
        stats.addWidget(self.total_properties_card, 0, 0)
        self.active_clients_card = StatCard(
            "—",
            "Total Clients",
            "From client records",
            "#486b2a",
        )
        stats.addWidget(self.active_clients_card, 0, 1)
        self.transaction_card = StatCard(
            "—", "Transactions", "From transaction records", "#5d8138"
        )
        stats.addWidget(self.transaction_card, 0, 2)
        self.revenue_card = StatCard(
            "—", "Sales Revenue", "Completed sales", "#6f9348"
        )
        stats.addWidget(self.revenue_card, 1, 0)
        self.total_agents_card = StatCard(
            "—", "Active Agents", "Active agent records", "#9a874d"
        )
        stats.addWidget(self.total_agents_card, 1, 1)
        self.pending_documents_card = StatCard(
            "—", "Documents Needing Attention", "Processing or failed", "#9b5555"
        )
        stats.addWidget(self.pending_documents_card, 1, 2)
        layout.addLayout(stats)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        trend_panel = QWidget()
        trend_panel.setObjectName("dashPanel")
        trend_panel.setStyleSheet(
            "QWidget#dashPanel { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 14px; }"
        )
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(18, 18, 18, 18)

        trend_heading = QVBoxLayout()  # badge sits under the heading, not beside it
        trend_heading.setSpacing(6)
        heading = QLabel("Monthly Transaction Trend")
        heading.setWordWrap(True)
        heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        trend_heading.addWidget(heading)
        self.trend_status_label = QLabel("Awaiting transaction data")
        self.trend_status_label.setStyleSheet(
            "font-size: 10px; font-weight: 700; color: #708064; "
            "background: #e7eedc; border-radius: 8px; padding: 4px 8px;"
        )
        trend_heading.addWidget(self.trend_status_label, 0, Qt.AlignmentFlag.AlignLeft)
        trend_layout.addLayout(trend_heading)
        self.trend_chart = TrendChart()
        trend_layout.addWidget(self.trend_chart)
        top_row.addWidget(trend_panel, 2)

        status_panel = QWidget()
        status_panel.setObjectName("dashPanel")
        status_panel.setStyleSheet(
            "QWidget#dashPanel { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 14px; }"
        )
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 18, 18, 18)

        status_heading_row = QHBoxLayout()
        status_heading = QLabel("Property Status Distribution")
        status_heading.setWordWrap(True)
        status_heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        status_heading_row.addWidget(status_heading, 1)
        status_heading_row.addStretch()
        self.status_refresh_button = QPushButton("Refresh")
        self.status_refresh_button.clicked.connect(self.refresh_property_status)
        status_heading_row.addWidget(self.status_refresh_button)
        status_layout.addLayout(status_heading_row)

        donut_row = QHBoxLayout()
        self.status_chart = StatusDonutChart()
        donut_row.addWidget(self.status_chart, 1)
        legend = QVBoxLayout()
        legend.setSpacing(10)
        self.status_legend = {
            "available": QLabel("Available: 0"),
            "reserved": QLabel("Reserved: 0"),
            "sold": QLabel("Sold: 0"),
            "on_hold": QLabel("On Hold: 0"),
            "unavailable": QLabel("Unavailable: 0"),
        }
        for key, label in self.status_legend.items():
            legend_row = QHBoxLayout()
            color_swatch = QLabel()
            color_swatch.setFixedSize(10, 10)
            color_swatch.setStyleSheet(  # raw: already a theme colour, no legacy mapping
                f"/*alty-raw*/ background-color: {status_colors()[key]}; border-radius: 5px;"
            )
            legend_row.addWidget(color_swatch)
            legend_row.addWidget(label)
            legend_row.addStretch()
            legend.addLayout(legend_row)
        donut_row.addLayout(legend)
        status_layout.addLayout(donut_row)
        top_row.addWidget(status_panel, 1)
        layout.addLayout(top_row)

        second_row = QHBoxLayout()
        second_row.setSpacing(16)

        capacity_panel = QWidget()
        capacity_panel.setObjectName("dashPanel")
        capacity_panel.setStyleSheet(
            "QWidget#dashPanel { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 14px; }"
        )
        capacity_layout = QVBoxLayout(capacity_panel)
        capacity_layout.setContentsMargins(18, 18, 18, 18)
        capacity_title = QLabel("Agent Performance")
        capacity_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        capacity_layout.addWidget(capacity_title)
        self.agent_performance_table = QTableWidget(0, 4)
        self.agent_performance_table.setHorizontalHeaderLabels(
            ["Agent", "Status", "Transactions", "Completed Revenue"]
        )
        self.agent_performance_table.horizontalHeader().setSectionResizeMode(
            0, self.agent_performance_table.horizontalHeader().ResizeMode.Stretch
        )
        for column, width in enumerate([100, 85, 100, 140]):
            if column:
                self.agent_performance_table.setColumnWidth(column, width)
        self.agent_performance_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.agent_performance_table.setAlternatingRowColors(True)
        self.agent_performance_table.setShowGrid(False)
        self.agent_performance_table.verticalHeader().setVisible(False)
        capacity_layout.addWidget(self.agent_performance_table)
        second_row.addWidget(capacity_panel, 1)

        forecast_panel = QWidget()
        forecast_panel.setObjectName("dashPanel")
        forecast_panel.setStyleSheet(
            "QWidget#dashPanel { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 14px; }"
        )
        forecast_layout = QVBoxLayout(forecast_panel)
        forecast_layout.setContentsMargins(18, 18, 18, 18)
        forecast_title = QLabel("Forecast Snapshot")
        forecast_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        forecast_layout.addWidget(forecast_title)
        self.forecast_label = QLabel("Insufficient historical data for a revenue forecast.")
        self.forecast_label.setWordWrap(True)
        self.forecast_label.setStyleSheet(
            "color: #65745b; font-size: 13px; font-weight: 600;"
        )
        forecast_layout.addWidget(self.forecast_label)
        second_row.addWidget(forecast_panel, 1)

        layout.addLayout(second_row)

        lower_row = QHBoxLayout()
        lower_row.setSpacing(16)

        transactions_panel = QWidget()
        transactions_panel.setObjectName("dashPanel")
        transactions_panel.setStyleSheet(
            "QWidget#dashPanel { background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 14px; }"
        )
        transactions_layout = QVBoxLayout(transactions_panel)
        transactions_layout.setContentsMargins(18, 18, 18, 18)
        transactions_title = QLabel("Recent Transactions")
        transactions_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        transactions_layout.addWidget(transactions_title)

        self.recent_transactions_table = QTableWidget(0, 6)
        self.recent_transactions_table.setHorizontalHeaderLabels(
            ["ID", "Client", "Property", "Agent", "Amount", "Status"]
        )
        self.recent_transactions_table.horizontalHeader().setSectionResizeMode(
            2, self.recent_transactions_table.horizontalHeader().ResizeMode.Stretch
        )
        for column, width in enumerate([90, 140, 220, 140, 120, 100]):
            if column != 2:
                self.recent_transactions_table.setColumnWidth(column, width)
        self.recent_transactions_table.setEditTriggers(
            QTableWidget.EditTrigger.NoEditTriggers
        )
        self.recent_transactions_table.setAlternatingRowColors(True)
        self.recent_transactions_table.setShowGrid(False)
        self.recent_transactions_table.verticalHeader().setVisible(False)
        transactions_layout.addWidget(self.recent_transactions_table)
        lower_row.addWidget(transactions_panel, 2)
        layout.addLayout(lower_row)

    @property
    def token(self) -> str | None:
        return self.controller.session.state.token

    def refresh(self) -> None:
        if not self.token:
            self._set_unavailable("Sign in to load dashboard data.")
            return
        self.load_summary()
        self.refresh_property_status()
        self.load_transaction_trend()
        self.load_recent_transactions()
        self.load_agent_performance()
        self.load_forecast()

    def load_summary(self) -> None:
        try:
            summary = self.api.get_dashboard_summary(token=self.token)
            self.total_properties_card.set_value(
                f"{int(summary.get('total_properties', 0)):,}"
            )
            self.active_clients_card.set_value(
                f"{int(summary.get('total_clients', 0)):,}"
            )
            self.transaction_card.set_value(
                f"{int(summary.get('total_transactions', 0)):,}"
            )
            self.revenue_card.set_value(
                self._format_currency(summary.get("completed_revenue"))
            )
            self.total_agents_card.set_value(
                f"{int(summary.get('active_agents', 0)):,}"
            )
            self.pending_documents_card.set_value(
                f"{int(summary.get('pending_documents', 0)):,}"
            )
            self.total_properties_card.delta_label.setText(
                f"{summary.get('available_properties', 0)} available · "
                f"{summary.get('reserved_properties', 0)} reserved · "
                f"{summary.get('sold_properties', 0)} sold"
            )
            self.pending_documents_card.delta_label.setText(
                f"{summary.get('failed_documents', 0)} failed · "
                f"{summary.get('processing_documents', 0)} processing · "
                f"{summary.get('successful_documents', 0)} succeeded"
            )
            self.total_agents_card.delta_label.setText(
                f"of {summary.get('total_agents', 0)} agent records"
            )
        except Exception as exc:
            print(f"Dashboard summary error: {exc}")
            for card in (
                self.total_properties_card,
                self.active_clients_card,
                self.transaction_card,
                self.revenue_card,
                self.total_agents_card,
                self.pending_documents_card,
            ):
                card.set_value("—")

    def refresh_property_status(self) -> None:
        self.status_refresh_button.setEnabled(False)
        try:
            summary = self.api.get_dashboard_property_status(token=self.token)
            counts = {
                key: int(summary.get(key, 0))
                for key in self.status_legend
            }
            self.status_chart.set_counts(
                counts["available"],
                counts["reserved"],
                counts["sold"],
                counts["on_hold"],
                counts["unavailable"],
            )
            labels = {
                "available": "Available",
                "reserved": "Reserved",
                "sold": "Sold",
                "on_hold": "On Hold",
                "unavailable": "Unavailable",
            }
            for key, label in self.status_legend.items():
                label.setText(f"{labels[key]}: {counts[key]}")
        except Exception as exc:
            print(f"Dashboard property status error: {exc}")
            self.status_chart.set_counts(0, 0, 0, 0, 0)
            for label in self.status_legend.values():
                label.setText(label.text().split(":", 1)[0] + ": —")
        finally:
            self.status_refresh_button.setEnabled(True)

    def load_transaction_trend(self) -> None:
        try:
            result = self.api.get_dashboard_transaction_trend(token=self.token)
            months = list(result.get("months", []))
            counts = [int(value) for value in result.get("counts", [])]
            self.trend_chart.set_data(months, counts)
            self.trend_status_label.setText(
                "Last 12 months" if any(counts) else "Insufficient transaction history"
            )
        except Exception as exc:
            print(f"Dashboard transaction trend error: {exc}")
            self.trend_chart.set_data([], [])
            self.trend_status_label.setText("Trend unavailable")

    def load_recent_transactions(self) -> None:
        try:
            transactions = self.api.get_dashboard_recent_transactions(
                token=self.token
            )
        except Exception as exc:
            print(f"Dashboard recent transactions error: {exc}")
            transactions = []
        self.recent_transactions_table.setRowCount(len(transactions))
        for row, transaction in enumerate(transactions):
            transaction_id = str(transaction.get("transaction_id") or "")
            values = [
                transaction_id[:8],
                str(transaction.get("client_name") or "—"),
                str(transaction.get("property_title") or "—"),
                str(transaction.get("agent_name") or "—"),
                self._format_currency(transaction.get("amount")),
                str(transaction.get("status") or "—"),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setToolTip(transaction_id if column == 0 else value)
                self.recent_transactions_table.setItem(row, column, item)

    def load_agent_performance(self) -> None:
        try:
            agents = self.api.get_dashboard_agent_performance(token=self.token)
        except Exception as exc:
            print(f"Dashboard agent performance error: {exc}")
            agents = []
        self.agent_performance_table.setRowCount(len(agents))
        for row, agent in enumerate(agents):
            values = [
                str(agent.get("full_name") or "—"),
                str(agent.get("status") or "—"),
                str(agent.get("transactions", 0)),
                self._format_currency(agent.get("completed_revenue")),
            ]
            for column, value in enumerate(values):
                self.agent_performance_table.setItem(row, column, QTableWidgetItem(value))

    def load_forecast(self) -> None:
        try:
            forecast = self.api.get_dashboard_forecast(token=self.token)
        except Exception as exc:
            print(f"Dashboard forecast error: {exc}")
            self.forecast_label.setText("Forecast unavailable.")
            return
        if forecast.get("status") == "insufficient_data":
            self.forecast_label.setText(str(forecast.get("message")))
            return
        self.forecast_label.setText(
            "Estimated sales revenue this month (linear trend, indicative): "
            f"{self._format_currency(forecast.get('next_month_revenue'))}\n"
            f"Linear trend based on {forecast.get('historical_months', 0)} "
            "months of completed transactions."
        )

    def _set_unavailable(self, message: str) -> None:
        for card in (
            self.total_properties_card,
            self.active_clients_card,
            self.transaction_card,
            self.revenue_card,
            self.total_agents_card,
            self.pending_documents_card,
        ):
            card.set_value("—")
        self.trend_status_label.setText(message)
        self.forecast_label.setText(message)

    @staticmethod
    def _format_currency(value) -> str:
        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "—"
