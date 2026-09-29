from __future__ import annotations

import httpx
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


class ForecastingPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(14)

        header = QHBoxLayout()
        title = QLabel("Forecasting")
        title.setStyleSheet("color: #17310a; font-size: 26px; font-weight: 700;")
        header.addWidget(title)
        header.addStretch()
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.clicked.connect(self.refresh)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        self.forecast_label = QLabel("Sign in to load transaction history.")
        self.forecast_label.setWordWrap(True)
        self.forecast_label.setStyleSheet(
            "background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 8px; "
            "padding: 14px; color: #17310a; font-size: 15px; font-weight: 600;"
        )
        layout.addWidget(self.forecast_label)

        self.history_table = QTableWidget(0, 2)
        self.history_table.setHorizontalHeaderLabels(["Month", "Transactions"])
        self.history_table.horizontalHeader().setSectionResizeMode(
            0, QHeaderView.ResizeMode.Stretch
        )
        self.history_table.horizontalHeader().setSectionResizeMode(
            1, QHeaderView.ResizeMode.ResizeToContents
        )
        self.history_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.history_table.setAlternatingRowColors(True)
        self.history_table.setShowGrid(False)
        self.history_table.verticalHeader().setVisible(False)
        self.history_table.setStyleSheet(
            "QTableWidget { background: #ffffff; alternate-background-color: #f5f7f2; "
            "border: 1px solid #d4dccf; border-radius: 8px; color: #26351f; }"
            "QHeaderView::section { background: #e4ebdf; color: #17310a; "
            "border: none; padding: 8px; font-weight: 700; }"
        )
        layout.addWidget(self.history_table, 1)

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    def refresh(self) -> None:
        if not self.token:
            self.forecast_label.setText("Sign in to load transaction history.")
            return
        self.refresh_button.setEnabled(False)
        try:
            forecast = self.api.get_dashboard_forecast(token=self.token)
            if forecast.get("status") == "insufficient_data":
                self.forecast_label.setText(str(forecast.get("message")))
            else:
                amount = float(forecast.get("next_month_revenue") or 0)
                self.forecast_label.setText(
                    f"Estimated next-month completed revenue: ₱{amount:,.2f}. "
                    f"Method: {forecast.get('method')} using "
                    f"{forecast.get('historical_months', 0)} months of actual data."
                )
            trend = self.api.get_dashboard_transaction_trend(token=self.token)
            months = list(trend.get("months", []))
            counts = list(trend.get("counts", []))
            self.history_table.setRowCount(len(months))
            for row, (month, count) in enumerate(zip(months, counts)):
                self.history_table.setItem(row, 0, QTableWidgetItem(str(month)))
                self.history_table.setItem(row, 1, QTableWidgetItem(str(count)))
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except ValueError:
                detail = None
            message = str(detail or f"The server returned HTTP {exc.response.status_code}.")
            self.forecast_label.setText(message)
            QMessageBox.warning(self, "Forecasting Error", message)
        except httpx.RequestError as exc:
            self.forecast_label.setText("Unable to connect to forecasting data.")
            QMessageBox.warning(self, "Connection Error", str(exc))
        finally:
            self.refresh_button.setEnabled(True)
