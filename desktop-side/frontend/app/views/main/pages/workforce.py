from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class WorkforcePage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Workforce Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for employee and branch workload / capacity indicators."))
