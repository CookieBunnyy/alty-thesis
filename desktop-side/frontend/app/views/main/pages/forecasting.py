from __future__ import annotations

from PyQt6.QtWidgets import QComboBox, QLabel

from app.views.main.pages._common import DataPage, fill, fmt_money, table

METRICS = (("Sales revenue", "revenue"), ("Transactions", "transactions"), ("Completed sales", "sales"))


class ForecastingPage(DataPage):
    title = "Forecasting"
    subtitle = ("Linear-trend forecast over complete months of recorded transactions. A forecast "
                "is produced only when enough history exists; otherwise nothing is estimated.")

    def build(self) -> None:
        self.metric = QComboBox()
        for label, value in METRICS:
            self.metric.addItem(label, value)
        self.metric.currentIndexChanged.connect(self.refresh)
        self.actions.insertWidget(0, self.metric)
        self.headline = QLabel("—")
        self.headline.setWordWrap(True)
        self.headline.setStyleSheet("font-size: 16px; font-weight: 700; color: #17310a;")
        self.layout_.addWidget(self.headline)
        self.forecast = table(["Month", "Forecast", "Lower (≈95%)", "Upper (≈95%)"])
        self.forecast.setMaximumHeight(170)
        self.layout_.addWidget(self.forecast)
        self.layout_.addWidget(QLabel("Monthly history used by the model (complete months)"))
        self.history = table(["Month", "Value"])
        self.layout_.addWidget(self.history, 1)

    def load(self) -> None:
        metric = self.metric.currentData()
        money = metric == "revenue"
        show = (lambda v: fmt_money(v)) if money else (lambda v: f"{float(v):,.1f}")
        result = self.api.get_forecast(token=self.token, metric=metric)
        fill(self.history, ([row["month"], show(row["value"])] for row in result["history"]))
        if result["status"] != "estimated":
            self.headline.setText(result["message"])
            fill(self.forecast, [])
            self.status.setText(
                f"{result['observations']} complete month(s) recorded, {result['nonzero_months']} with "
                f"activity; at least {result['minimum_required']} months (3 with activity) are required."
            )
            return
        fill(self.forecast, ([p["month"], show(p["value"]), show(p["lower"]), show(p["upper"])]
                             for p in result["forecast"]))
        self.headline.setText(
            f"Trend {show(result['slope_per_month'])} per month · R² {result['r_squared']}"
        )
        self.status.setText(f"{result['method']}. {result['observations']} months of history. "
                            f"Interval: {result['interval']}. Indicative only.")
