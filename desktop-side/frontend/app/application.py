from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.session import SessionManager
from app.views.login.login_window import LoginWindow
from app.views.main.main_window import MainWindow


class AppController:
    def __init__(self) -> None:
        self.session = SessionManager()

        self.root = QMainWindow()
        self.root.setWindowTitle("Abellar Realty Management System")
        self.root.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        self.root.setWindowFlag(Qt.WindowType.FramelessWindowHint)
        self.root.setAttribute(
            Qt.WidgetAttribute.WA_TranslucentBackground
        )
        self.root.setStyleSheet(
            "QMainWindow { background: transparent; }"
        )

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.root.setCentralWidget(self.stack)

        self.login_window = LoginWindow(self)
        self.main_window = MainWindow(self)

        self.stack.addWidget(self.login_window)
        self.stack.addWidget(self.main_window)

    def start(self) -> None:
        self.show_login()
        self.root.show()

    def show_login(self) -> None:
        self.stack.setCurrentWidget(self.login_window)
        self.root.setWindowTitle(
            "Abellar Realty Management System | Login"
        )
        self.root.showFullScreen()

    def show_main(self) -> None:
        self.stack.setCurrentWidget(self.main_window)
        self.root.setWindowTitle(
            "Abellar Realty Management System"
        )
        self.root.showFullScreen()
        self.main_window.show_page("dashboard")

    def logout(self) -> None:
        self.session.clear()
        self.show_login()
