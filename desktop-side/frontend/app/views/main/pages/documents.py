from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class DocumentsPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Document Repository")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for upload, category filtering, preview, archive, and audit trail."))
