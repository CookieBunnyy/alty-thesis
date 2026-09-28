from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class AuditPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Audit Logs")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for system activity, changes, and read-only audit review."))
