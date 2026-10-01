from __future__ import annotations

from PyQt6.QtWidgets import QHBoxLayout, QLabel

from app.views.main.pages._common import Card, DataPage, fill, table


class WorkforcePage(DataPage):
    title = "Workforce Management"
    subtitle = "Users by role, account activity, and agent assignments and transaction activity."

    def build(self) -> None:
        cards = QHBoxLayout()
        self.users_card = Card("Users")
        self.active_card = Card("Active users", "#486b2a")
        self.agents_card = Card("Agents", "#477489")
        self.active_agents_card = Card("Active agents", "#486b2a")
        for card in (self.users_card, self.active_card, self.agents_card, self.active_agents_card):
            cards.addWidget(card)
        self.layout_.addLayout(cards)
        self.layout_.addWidget(QLabel("Users by role"))
        self.roles = table(["Role", "Users", "Active", "Signed in (30 days)"])
        self.roles.setMaximumHeight(220)
        self.layout_.addWidget(self.roles)
        self.layout_.addWidget(QLabel("Agent assignments and activity (recorded transactions)"))
        self.agents = table(["Agent ID", "Agent", "Status", "Assigned clients", "Transactions",
                             "Active reservations", "Sales (90 days)"])
        self.layout_.addWidget(self.agents, 1)

    def load(self) -> None:
        data = self.api.get_workforce(token=self.token)
        users, agents = data["users"], data["agents"]
        self.users_card.set(users["total"])
        self.active_card.set(users["active"])
        self.agents_card.set(agents["total"])
        self.active_agents_card.set(agents["active"])
        fill(self.roles, ([r["role"], r["users"], r["active"], r["logged_in_30d"]] for r in users["by_role"]))
        fill(self.agents, ([a["agent_id"], a["full_name"], a["status"], a["assigned_clients"],
                            a["transactions"], a["active_reservations"], a["sales_last_90_days"]]
                           for a in agents["rows"]))
        self.status.setText("Computed from users, agents, clients and transactions records.")
