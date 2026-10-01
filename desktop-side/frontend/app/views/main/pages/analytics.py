from __future__ import annotations

from PyQt6.QtWidgets import QGridLayout, QHBoxLayout, QLabel

from app.views.main.pages._common import INSUFFICIENT, Card, DataPage, fill, fmt_money, table


class AnalyticsPage(DataPage):
    title = "Analytics"
    subtitle = ("Sales volume, revenue, absorption, status distribution, agent performance and "
                "price levels — computed from properties, clients, transactions and agents.")

    def build(self) -> None:
        cards = QGridLayout()
        self.revenue = Card("Sales revenue", "#17310a")
        self.sales = Card("Completed sales", "#477489")
        self.average = Card("Average sale value", "#486b2a")
        self.absorption = Card("Absorption (sold / listings)", "#9a6a13")
        self.reservations = Card("Active reservations", "#486b2a")
        for index, card in enumerate(
            (self.revenue, self.sales, self.average, self.absorption, self.reservations)
        ):
            cards.addWidget(card, index // 3, index % 3)
        self.layout_.addLayout(cards)
        row = QHBoxLayout()
        self.status_table = table(["Property status", "Listings"])
        self.monthly = table(["Month", "Transactions", "Reservations", "Sales", "Revenue", "Average sale"])
        row.addWidget(self.status_table, 1)
        row.addWidget(self.monthly, 3)
        self.layout_.addLayout(row, 1)
        self.layout_.addWidget(QLabel("Agent performance (recorded transactions)"))
        self.agents = table(["Agent", "Status", "Transactions", "Completed sales", "Sales value",
                             "Recorded commission"])
        self.layout_.addWidget(self.agents, 1)
        self.layout_.addWidget(QLabel("Listing price by category"))
        self.prices = table(["Category", "Listings", "Average price", "Minimum", "Maximum"])
        self.prices.setMaximumHeight(180)
        self.layout_.addWidget(self.prices)

    def load(self) -> None:
        data = self.api.get_analytics_overview(token=self.token)
        tx = data["transactions"]
        self.revenue.set(fmt_money(tx["revenue"]))
        self.sales.set(tx["completed_sales"])
        self.average.set(fmt_money(tx["average_sale_value"]) if tx["average_sale_value"] else INSUFFICIENT)
        rate = data["absorption_rate"]
        self.absorption.set(f"{rate * 100:.1f}%" if rate is not None else INSUFFICIENT)
        self.reservations.set(tx["active_reservations"])
        fill(self.status_table, sorted(data["properties"]["by_status"].items()))
        fill(self.monthly, ([m["month"], m["transactions"], m["reservations"], m["sales"],
                             fmt_money(m["revenue"]), fmt_money(m["average_sale"]) if m["average_sale"] else "—"]
                            for m in data["monthly"]))
        fill(self.agents, ([a["full_name"], a["status"], a["transactions"], a["completed_sales"],
                            fmt_money(a["sales_value"]), fmt_money(a["recorded_total_commission"])]
                           for a in data["agents"]))
        fill(self.prices, ([p["category"], p["listings"], fmt_money(p["average_price"]),
                            fmt_money(p["min_price"]), fmt_money(p["max_price"])]
                           for p in data["price_by_category"]))
        has_activity = any(m["transactions"] for m in data["monthly"])
        self.status.setText(
            f"{data['properties']['total']} listings · {tx['total']} transactions · {data['clients']} clients"
            + ("" if has_activity else f" · {INSUFFICIENT} for monthly trends (no transactions in 12 months)")
        )
