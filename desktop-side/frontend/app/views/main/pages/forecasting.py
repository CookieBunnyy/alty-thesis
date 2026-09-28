from PyQt6.QtWidgets import QLabel, QVBoxLayout, QWidget


class ForecastingPage(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        title = QLabel("Forecasting")
        title.setStyleSheet("font-size: 24px; font-weight: 700;")
        layout.addWidget(title)
        layout.addWidget(QLabel("Placeholder for historical trends, forecast charts, and confidence indicators."))
