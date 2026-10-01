import sys

from PyQt6.QtWidgets import QApplication

from app.application import AppController


if __name__ == "__main__":
    app = QApplication(sys.argv)
    from app import theme

    theme.install(app)  # Abellar light/dark design system (tokens, palette, QSS)
    from app.ui_polish import install as install_ui_polish

    install_ui_polish(app)  # themed message boxes, icons, screen-fitting dialogs
    controller = AppController()
    controller.start()
    sys.exit(app.exec())
