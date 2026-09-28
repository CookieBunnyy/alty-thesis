from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class TransactionsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Transaction Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for transactions, commission tracking, and status updates."))
