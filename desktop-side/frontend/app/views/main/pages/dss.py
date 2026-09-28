from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DssPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Decision Support")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for recommendations, reasoned insights, and review/accept workflow."))
