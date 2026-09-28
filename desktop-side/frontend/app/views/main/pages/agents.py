from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AgentsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Agent Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for agent profiles, assignments, transactions, and performance."))
