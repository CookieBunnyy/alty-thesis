import sys

from PyQt6.QtWidgets import QApplication

from app.application import AppController


if __name__ == "__main__":
    app = QApplication(sys.argv)
    controller = AppController()
    controller.start()
    sys.exit(app.exec())
