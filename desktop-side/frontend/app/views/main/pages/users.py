from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class UsersPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("User Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for user administration, role assignment, and permission management."))
