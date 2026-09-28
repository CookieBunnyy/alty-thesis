from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class MediaPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Digital Preview Management")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for image and video upload, quality review, and approval workflow."))
