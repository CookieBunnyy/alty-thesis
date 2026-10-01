from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QApplication, QMainWindow, QStackedWidget

from app.session import SessionManager
from app.views.login.login_window import LoginWindow
from app.views.main.main_window import MainWindow
from app.views.window_frame import FramelessResizer


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

        # Frameless windows get no OS borders; add edge resizing ourselves.
        self.root.setMinimumSize(1000, 640)
        self.resizer = FramelessResizer(self.root)
        screen = QApplication.primaryScreen()
        if screen is not None:  # size used when the window is restored
            area = screen.availableGeometry()
            self.root.resize(int(area.width() * 0.85), int(area.height() * 0.85))
            self.root.move(area.center() - self.root.rect().center())

    def start(self) -> None:
        self.show_login()
        self.root.show()

    def show_login(self) -> None:
        self.stack.setCurrentWidget(self.login_window)
        self.root.setWindowTitle(
            "Abellar Realty Management System | Login"
        )
        self.root.showMaximized()

    def show_main(self) -> None:
        self.stack.setCurrentWidget(self.main_window)
        self.root.setWindowTitle(
            "Abellar Realty Management System"
        )
        self.root.showMaximized()
        self.main_window.apply_session()
        self.main_window.show_page("dashboard")

    def apply_theme(self, mode: str) -> None:
        """Switch dark/light now: rebuild the windows in the new theme while
        keeping the signed-in session and the current page."""
        from PyQt6.QtCore import QTimer

        from app import theme

        def rebuild() -> None:
            theme.set_mode(mode)
            signed_in = self.session.is_authenticated and self.stack.currentWidget() is self.main_window
            current_page = getattr(self.main_window, "current_page", "dashboard")
            old_login = self.login_window
            old_widgets = (self.login_window, self.main_window)
            self.login_window = LoginWindow(self)
            # Switching on the sign-in screen keeps what was typed there.
            self.login_window.username_input.setText(old_login.username_input.text())
            self.login_window.password_input.setText(old_login.password_input.text())
            self.login_window.remember_check.setChecked(old_login.remember_check.isChecked())
            self.main_window = MainWindow(self)
            self.stack.addWidget(self.login_window)
            self.stack.addWidget(self.main_window)
            if signed_in:
                self.stack.setCurrentWidget(self.main_window)
                self.main_window.apply_session()
                self.main_window.show_page(current_page)
            else:
                self.stack.setCurrentWidget(self.login_window)
            for widget in old_widgets:
                self.stack.removeWidget(widget)
                widget.deleteLater()

        # Deferred: the request comes from a button inside the window being replaced.
        QTimer.singleShot(0, rebuild)

    def logout(self) -> None:
        if self.session.state.token:
            from app.api.client import ApiClient

            ApiClient().logout(self.session.state.token)
        self.session.clear()
        self.show_login()
