from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PartnersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Partners / Developers")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for partner/developer records and accreditation management."))
