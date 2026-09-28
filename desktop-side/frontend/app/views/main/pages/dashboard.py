from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)


class StatCard(QWidget):
    def __init__(self, value: str, label: str, delta: str, accent: str = "#486b2a") -> None:
        super().__init__()
        self.setStyleSheet(
            """
            QWidget {
                background: #f7f9f3;
                border: none;
                border-radius: 16px;
            }
            QLabel { background: transparent; }
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

        more = QLabel("•••")
        more.setStyleSheet("color: #9aa58f; font-size: 16px;")
        top.addWidget(more)
        layout.addLayout(top)

        value_label = QLabel(self.value)
        value_label.setStyleSheet("color: #17240f; font-size: 30px; font-weight: 800;")
        layout.addWidget(value_label)

        delta_label = QLabel(self.delta)
        delta_label.setStyleSheet(f"color: {self.accent}; font-size: 12px; font-weight: 700;")
        layout.addWidget(delta_label)


class TrendChart(QWidget):
    def __init__(self, values=None) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent; border: none;")
        self.values = values or [18, 22, 30, 28, 36, 42, 39, 50, 58, 54, 68, 72]
        self.setMinimumHeight(230)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(10, 12, -10, -12)
        w = rect.width()
        h = rect.height()

        painter.setPen(QPen(QColor(180, 180, 180, 90), 1))
        for i in range(5):
            y = rect.top() + int((i / 4) * h)
            painter.drawLine(rect.left(), y, rect.right(), y)

        max_value = max(self.values) if self.values else 100
        min_value = min(self.values) if self.values else 0
        points = []
        for idx, value in enumerate(self.values):
            x = rect.left() + int(((idx / (len(self.values) - 1)) * (w - 20))) + 10
            y = rect.bottom() - int(((value - min_value) / max(max_value - min_value, 1)) * (h - 28)) - 10
            points.append((x, y))

        painter.setPen(QPen(QColor(72, 107, 42), 3))
        for i in range(len(points) - 1):
            x1, y1 = points[i]
            x2, y2 = points[i + 1]
            painter.drawLine(x1, y1, x2, y2)

        for x, y in points:
            painter.setBrush(QColor(72, 107, 42))
            painter.drawEllipse(x - 4, y - 4, 8, 8)

        for label_idx, label in enumerate(["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]):
            x = rect.left() + int((label_idx / max(len(self.values) - 1, 1)) * (w - 20)) + 10
            painter.drawText(int(x), int(rect.bottom() - 4), label)


class StatusDonutChart(QWidget):
    def __init__(self, available: int, reserved: int, sold: int, on_hold: int, unavailable: int) -> None:
        super().__init__()
        self.setStyleSheet("background: transparent; border: none;")
        self.available = available
        self.reserved = reserved
        self.sold = sold
        self.on_hold = on_hold
        self.unavailable = unavailable
        self.setMinimumHeight(220)

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        center = self.rect().center()
        radius = min(self.rect().width(), self.rect().height()) * 0.30
        total = max(self.available + self.reserved + self.sold + self.on_hold + self.unavailable, 1)
        segments = [
            (self.available / total, QColor(72, 107, 42)),
            (self.reserved / total, QColor(111, 147, 72)),
            (self.sold / total, QColor(63, 107, 39)),
            (self.on_hold / total, QColor(154, 135, 77)),
            (self.unavailable / total, QColor(180, 180, 180)),
        ]

        start_angle = 90 * 16
        for ratio, color in segments:
            span = int(360 * ratio * 16)
            painter.setPen(QPen(color, 12, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
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
        painter.setPen(QPen(QColor(238, 243, 229), 12))
        painter.drawEllipse(
            int(center.x() - inner_radius),
            int(center.y() - inner_radius),
            int(inner_radius * 2),
            int(inner_radius * 2),
        )

        painter.setPen(QPen(QColor(23, 36, 15), 1))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, str(total))


class DashboardPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
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
        stats.addWidget(StatCard("184", "Total Properties", "DEMO DATA", "#486b2a"), 0, 0)
        stats.addWidget(StatCard("1,286", "Active Clients", "+8.4% vs last month", "#486b2a"), 0, 1)
        stats.addWidget(StatCard("97", "Active Transactions", "+12.6% this quarter", "#5d8138"), 0, 2)
        stats.addWidget(StatCard("₱8.4M", "Revenue", "+9.2% this month", "#6f9348"), 1, 0)
        stats.addWidget(StatCard("38", "Active Agents", "Capacity: 82%", "#9a874d"), 1, 1)
        stats.addWidget(StatCard("41", "Pending Documents", "12 require review", "#9b5555"), 1, 2)
        layout.addLayout(stats)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)

        trend_panel = QWidget()
        trend_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        trend_layout = QVBoxLayout(trend_panel)
        trend_layout.setContentsMargins(18, 18, 18, 18)

        trend_heading = QHBoxLayout()
        heading = QLabel("Property / Transaction Trend")
        heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        trend_heading.addWidget(heading)
        trend_heading.addStretch()
        trend_label = QLabel("DEMO DATA")
        trend_label.setStyleSheet("font-size: 10px; font-weight: 700; letter-spacing: 1px; color: #708064; background: #e7eedc; border-radius: 8px; padding: 4px 8px;")
        trend_heading.addWidget(trend_label)
        trend_layout.addLayout(trend_heading)
        trend_layout.addWidget(TrendChart())
        top_row.addWidget(trend_panel, 2)

        status_panel = QWidget()
        status_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        status_layout = QVBoxLayout(status_panel)
        status_layout.setContentsMargins(18, 18, 18, 18)

        status_heading = QLabel("Property Status Distribution")
        status_heading.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        status_layout.addWidget(status_heading)

        donut_row = QHBoxLayout()
        donut_row.addWidget(StatusDonutChart(88, 26, 32, 14, 24), 1)
        legend = QVBoxLayout()
        legend.setSpacing(10)
        legend.addWidget(QLabel("Available: 88"))
        legend.addWidget(QLabel("Reserved: 26"))
        legend.addWidget(QLabel("Sold: 32"))
        legend.addWidget(QLabel("On Hold: 14"))
        legend.addWidget(QLabel("Unavailable: 24"))
        donut_row.addLayout(legend)
        status_layout.addLayout(donut_row)
        top_row.addWidget(status_panel, 1)
        layout.addLayout(top_row)

        second_row = QHBoxLayout()
        second_row.setSpacing(16)

        capacity_panel = QWidget()
        capacity_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        capacity_layout = QVBoxLayout(capacity_panel)
        capacity_layout.setContentsMargins(18, 18, 18, 18)
        capacity_title = QLabel("Workforce Capacity Overview")
        capacity_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        capacity_layout.addWidget(capacity_title)
        capacity_stack = QVBoxLayout()
        capacity_stack.setSpacing(10)
        for label, value, color in [
            ("Current workload", "82%", "#486b2a"),
            ("Available capacity", "18%", "#5d8138"),
            ("Utilization", "74%", "#9a874d"),
            ("Capacity vs demand", "+6.3%", "#6f9348"),
        ]:
            metric_line = QHBoxLayout()
            metric_name = QLabel(label)
            metric_name.setStyleSheet("color: #294c16; font-size: 12px; font-weight: 600;")
            metric_value = QLabel(value)
            metric_value.setStyleSheet(f"color: {color}; font-size: 12px; font-weight: 800;")
            metric_line.addWidget(metric_name)
            metric_line.addStretch()
            metric_line.addWidget(metric_value)
            capacity_stack.addLayout(metric_line)
        capacity_layout.addLayout(capacity_stack)
        second_row.addWidget(capacity_panel, 1)

        forecast_panel = QWidget()
        forecast_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        forecast_layout = QVBoxLayout(forecast_panel)
        forecast_layout.setContentsMargins(18, 18, 18, 18)
        forecast_title = QLabel("Forecast Snapshot")
        forecast_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        forecast_layout.addWidget(forecast_title)
        forecast_rows = QVBoxLayout()
        forecast_rows.setSpacing(10)
        for label, value in [
            ("Sales forecast", "₱12.8M"),
            ("Demand forecast", "+14.2%"),
            ("Revenue forecast", "₱9.7M"),
            ("Commission forecast", "₱1.9M"),
        ]:
            row = QHBoxLayout()
            key = QLabel(label)
            key.setStyleSheet("color: #65745b; font-size: 12px; font-weight: 600;")
            val = QLabel(value)
            val.setStyleSheet("color: #17240f; font-size: 12px; font-weight: 800;")
            row.addWidget(key)
            row.addStretch()
            row.addWidget(val)
            forecast_rows.addLayout(row)
        forecast_layout.addLayout(forecast_rows)
        second_row.addWidget(forecast_panel, 1)

        layout.addLayout(second_row)

        lower_row = QHBoxLayout()
        lower_row.setSpacing(16)

        transactions_panel = QWidget()
        transactions_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        transactions_layout = QVBoxLayout(transactions_panel)
        transactions_layout.setContentsMargins(18, 18, 18, 18)
        transactions_title = QLabel("Recent Transactions")
        transactions_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        transactions_layout.addWidget(transactions_title)

        table = QTableWidget(5, 6)
        table.setHorizontalHeaderLabels(["ID", "Property", "Client", "Type", "Amount", "Status"])
        table.setColumnWidth(0, 90)
        table.setColumnWidth(1, 180)
        table.setColumnWidth(2, 160)
        table.setColumnWidth(3, 120)
        table.setColumnWidth(4, 120)
        table.setColumnWidth(5, 120)
        rows = [
            ("TX-2048", "Aster Hills", "M. Santos", "Sale", "₱4.2M", "Closed"),
            ("TX-2049", "Harbor View", "E. Cruz", "Lease", "₱220K", "In Review"),
            ("TX-2050", "Skyline Residences", "C. Lim", "Sale", "₱6.8M", "Active"),
            ("TX-2051", "Cedar Court", "R. Gomez", "Assignment", "₱1.1M", "Pending"),
            ("TX-2052", "Ember Heights", "A. Ramos", "Sale", "₱3.9M", "Reserved"),
        ]
        for row_index, values in enumerate(rows):
            for col_index, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                item.setTextAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
                table.setItem(row_index, col_index, item)
        table.verticalHeader().setVisible(False)
        table.setAlternatingRowColors(True)
        table.setShowGrid(False)
        transactions_layout.addWidget(table)
        lower_row.addWidget(transactions_panel, 2)

        dss_panel = QWidget()
        dss_panel.setStyleSheet("background: #f7f9f3; border: none; border-radius: 18px;")
        dss_layout = QVBoxLayout(dss_panel)
        dss_layout.setContentsMargins(18, 18, 18, 18)
        dss_title = QLabel("DSS Recommendations Requiring Review")
        dss_title.setStyleSheet("font-size: 18px; font-weight: 700; color: #17240f;")
        dss_layout.addWidget(dss_title)

        recs = [
            ("Increase pricing on Aster Hills units", "Demand remains strong in the north branch; recent comps support a +3% pricing adjustment."),
            ("Prioritize document review for Harbor View", "Several transaction files are overdue and may delay close."),
            ("Reassign agent capacity in Laguna branch", "Utilization exceeds target by 11% and support is needed on active listings."),
        ]
        for title, text in recs:
            card = QWidget()
            card.setStyleSheet("background: #e7eedc; border: none; border-radius: 12px;")
            c_layout = QVBoxLayout(card)
            c_layout.setContentsMargins(12, 10, 12, 10)
            c_title = QLabel(title)
            c_title.setStyleSheet("font-size: 12px; font-weight: 700; color: #17240f;")
            c_text = QLabel(text)
            c_text.setWordWrap(True)
            c_text.setStyleSheet("font-size: 11px; color: #65745b; line-height: 1.4;")
            c_layout.addWidget(c_title)
            c_layout.addWidget(c_text)
            dss_layout.addWidget(card)

        lower_row.addWidget(dss_panel, 1)
        layout.addLayout(lower_row)
