import sys

from PyQt6.QtWidgets import QApplication

from app.application import AppController


if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyleSheet(
        """
        QMessageBox, QMessageBox QWidget, QMessageBox QTextEdit {
            background-color: #ffffff;
            color: #17310a;
        }
        QMessageBox QLabel {
            background-color: transparent;
            color: #17310a;
        }
        QMessageBox QPushButton {
            background-color: #e7eedc;
            color: #17310a;
            border: 1px solid #cbd8be;
            border-radius: 5px;
            padding: 6px 16px;
            min-width: 64px;
            min-height: 28px;
        }
        QMessageBox QPushButton:hover {
            background-color: #dcebd3;
        }
        QMessageBox QPushButton:pressed {
            background-color: #cddfc1;
        }
        """
    )
    controller = AppController()
    controller.start()
    sys.exit(app.exec())
