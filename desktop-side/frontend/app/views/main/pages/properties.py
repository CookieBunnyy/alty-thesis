from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class PropertiesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Property Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for property listing, filters, status management, and detail views."))
