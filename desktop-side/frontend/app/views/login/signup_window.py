from __future__ import annotations

from PyQt6.QtCore import QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)
import qtawesome as qta

from app.api.client import ApiClient


class FloatingLabelInput(QFrame):
    """Login/signup themed floating-label input."""

    textChanged = pyqtSignal(str)

    def __init__(self, label_text: str, password: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._label_text = label_text
        self._password = password

        self.setObjectName("floatingLabelInput")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        self.label = QLabel(label_text, self)
        self.label.setObjectName("floatingLabel")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)

        from PyQt6.QtWidgets import QLineEdit

        self.line_edit = QLineEdit(self)
        self.line_edit.setObjectName("floatingLineEdit")
        self.line_edit.setFrame(False)
        self.line_edit.textChanged.connect(self._handle_text_changed)
        self.line_edit.textChanged.connect(self.textChanged)

        if password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button = QToolButton(self)
            self.toggle_button.setObjectName("togglePassword")
            self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle_button.setAutoRaise(True)
            self.toggle_button.setIcon(qta.icon("fa5.eye", color="#294c16"))
            self.toggle_button.setIconSize(QSize(18, 18))
            self.toggle_button.clicked.connect(self._toggle_visibility)
        else:
            self.toggle_button = None

        self.apply_styles()
        self.update_label_state()

    def apply_styles(self):
        self.setStyleSheet("""
            QFrame#floatingLabelInput {
                background: #edf0e9;
                border: 1px solid #607e49;
                border-radius: 8px;
            }

            QFrame#floatingLabelInput[focused="true"] {
                border: 1px solid #2b4713;
            }

            QLabel#floatingLabel {
                color: #999999;
                background: transparent;
                font-size: 8px;
                font-weight: bold;
                padding: 0;
                margin: 0;
            }

            QLineEdit#floatingLineEdit {
                background: transparent;
                border: none;
                color: #17240f;
                font-size: 13px;
                padding: 0;
                margin: 0;
            }

            QToolButton#togglePassword {
                background: transparent;
                border: none;
                padding: 0;
                margin: 0;
            }

            QToolButton#togglePassword:hover {
                background: rgba(72, 107, 42, 0.08);
                border-radius: 6px;
            }
        """)

        self.setProperty("focused", self.line_edit.hasFocus())
        self.style().polish(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_label_state()

    def update_label_state(self):
        floating = self.line_edit.hasFocus() or bool(self.line_edit.text())
        self.setProperty("focused", self.line_edit.hasFocus())
        self.style().polish(self)

        if floating:
            self.label.setGeometry(14, 5, self.width() - 28, 16)
            self.label.setStyleSheet("""
                QLabel#floatingLabel {
                    color: #486b2a;
                    background: transparent;
                    font-size: 8px;
                    font-weight: 500;
                    letter-spacing: 0.3px;
                }
            """)
            self.line_edit.setGeometry(
                10, 20,
                self.width() - 22 - (42 if self._password else 0),
                30,
            )
        else:
            self.label.setGeometry(14, 0, self.width() - 28, self.height())
            self.label.setStyleSheet("""
                QLabel#floatingLabel {
                    color: #999999;
                    background: transparent;
                    font-size: 10px;
                    font-weight: 500;
                    letter-spacing: 0.3px;
                }
            """)
            self.line_edit.setGeometry(
                10, 0,
                self.width() - 22 - (42 if self._password else 0),
                self.height(),
            )

        if self._password:
            self.toggle_button.setGeometry(self.width() - 38, 11, 32, 32)
            self.toggle_button.raise_()

        self.label.raise_()

    def _handle_text_changed(self, text):
        self.update_label_state()

    def _toggle_visibility(self):
        from PyQt6.QtWidgets import QLineEdit

        if self.line_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_button.setIcon(qta.icon("fa5.eye-slash", color="#294c16"))
        else:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button.setIcon(qta.icon("fa5.eye", color="#294c16"))

    def text(self):
        return self.line_edit.text()

    def clear(self):
        self.line_edit.clear()

    def setFocus(self):
        self.line_edit.setFocus()


class SignUpWindow(QWidget):
    """
    Basic employee account registration window.

    Expected ApiClient method:
        register(username, password, full_name)

    The backend should assign the default role (Employee) and save the
    password as a bcrypt hash. The desktop client must never send a role
    selected by the user.
    """

    signup_completed = pyqtSignal()

    def __init__(self, api: ApiClient | None = None, login_window=None) -> None:
        super().__init__()
        self.api = api or ApiClient()
        self.login_window = login_window

        self.setWindowTitle("ALTY - Create Account")
        self.setObjectName("signupWindow")
        self.setMinimumSize(760, 560)
        self.resize(820, 590)
        self._drag_position = None

        self.setStyleSheet("""
            QWidget#signupWindow {
                background: #d8ecb6;
            }

            QWidget#signupCard {
                background: #f7f9f3;
                border: 1px solid #b4b4b4;
                border-radius: 18px;
            }

            QWidget#signupBrand {
                background: qlineargradient(
                    x1:0, y1:0, x2:1, y2:1,
                    stop:0 #17310a,
                    stop:1 #294c16
                );
                border-radius: 18px;
            }

            QLabel#brand {
                color: #d8ecb6;
                font-size: 28px;
                font-weight: 900;
                letter-spacing: 2px;
                background: transparent;
            }

            QLabel#brandSmall {
                color: #b4b4b4;
                font-size: 11px;
                letter-spacing: 1.8px;
                background: transparent;
            }

            QLabel#title {
                color: #17310a;
                font-size: 25px;
                font-weight: 800;
                background: transparent;
            }

            QLabel#subtitle {
                color: #65745b;
                font-size: 12px;
                background: transparent;
            }

            QLabel#message {
                color: #9b5555;
                font-size: 11px;
                background: transparent;
            }

            QPushButton#signupButton {
                background: #486b2a;
                color: white;
                border: none;
                border-radius: 10px;
                padding: 12px 18px;
                font-size: 15px;
                font-weight: 700;
            }

            QPushButton#signupButton:hover {
                background: #5d8138;
            }

            QPushButton#signupButton:pressed {
                background: #294c16;
            }

            QPushButton#backButton {
                background: transparent;
                color: #486b2a;
                border: none;
                font-size: 12px;
                font-weight: 700;
                padding: 5px;
            }

            QPushButton#backButton:hover {
                color: #294c16;
            }
        """)

        root = QHBoxLayout(self)
        root.setContentsMargins(22, 22, 22, 22)
        root.setSpacing(0)

        card = QWidget()
        card.setObjectName("signupCard")
        card_layout = QHBoxLayout(card)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        brand = QWidget()
        brand.setObjectName("signupBrand")
        brand.setFixedWidth(270)
        brand_layout = QVBoxLayout(brand)
        brand_layout.setContentsMargins(28, 35, 28, 28)
        brand_layout.addStretch()

        brand_title = QLabel("ALTY")
        brand_title.setObjectName("brand")
        brand_title.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_small = QLabel("REAL ESTATE\nMANAGEMENT")
        brand_small.setObjectName("brandSmall")
        brand_small.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_note = QLabel(
            "Create your account to access\n"
            "the Abellar Realty platform."
        )
        brand_note.setStyleSheet(
            "color:#d8d8d8; font-size:12px; background:transparent;"
        )
        brand_note.setAlignment(Qt.AlignmentFlag.AlignCenter)

        brand_layout.addWidget(brand_title)
        brand_layout.addSpacing(10)
        brand_layout.addWidget(brand_small)
        brand_layout.addSpacing(28)
        brand_layout.addWidget(brand_note)
        brand_layout.addStretch()

        form = QWidget()
        form_layout = QVBoxLayout(form)
        form_layout.setContentsMargins(34, 30, 34, 26)
        form_layout.setSpacing(11)

        title = QLabel("Create Account")
        title.setObjectName("title")

        subtitle = QLabel("Enter your basic information to register.")
        subtitle.setObjectName("subtitle")

        self.full_name = FloatingLabelInput("FULL NAME")
        self.username = FloatingLabelInput("USERNAME")
        self.password = FloatingLabelInput("PASSWORD", password=True)
        self.confirm_password = FloatingLabelInput(
            "CONFIRM PASSWORD",
            password=True,
        )

        self.message = QLabel("")
        self.message.setObjectName("message")
        self.message.setWordWrap(True)
        self.message.setMinimumHeight(18)

        self.signup_button = QPushButton("Create Account")
        self.signup_button.setObjectName("signupButton")
        self.signup_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.signup_button.setMinimumHeight(46)
        self.signup_button.clicked.connect(self.handle_signup)

        self.back_button = QPushButton("← Back to Sign In")
        self.back_button.setObjectName("backButton")
        self.back_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.back_button.clicked.connect(self.back_to_login)

        form_layout.addWidget(title)
        form_layout.addWidget(subtitle)
        form_layout.addSpacing(8)
        form_layout.addWidget(self.full_name)
        form_layout.addWidget(self.username)
        form_layout.addWidget(self.password)
        form_layout.addWidget(self.confirm_password)
        form_layout.addWidget(self.message)
        form_layout.addWidget(self.signup_button)
        form_layout.addWidget(self.back_button)
        form_layout.addStretch()

        card_layout.addWidget(brand)
        card_layout.addWidget(form, 1)
        root.addWidget(card)

        self.username.setFocus()

    def handle_signup(self) -> None:
        full_name = self.full_name.text().strip()
        username = self.username.text().strip()
        password = self.password.text()
        confirm = self.confirm_password.text()

        if not full_name or not username or not password or not confirm:
            self.message.setText("Please complete all required fields.")
            return

        if len(username) < 3:
            self.message.setText("Username must be at least 3 characters.")
            return

        if len(password) < 8:
            self.message.setText("Password must be at least 8 characters.")
            return

        if password != confirm:
            self.message.setText("Passwords do not match.")
            self.confirm_password.setFocus()
            return

        self.signup_button.setEnabled(False)
        self.signup_button.setText("Creating Account...")
        self.message.setText("")

        try:
            register = getattr(self.api, "register", None)
            if not callable(register):
                raise RuntimeError(
                    "Registration API is not connected yet. "
                    "Add ApiClient.register() for POST /api/v1/auth/register."
                )

            response = register(
                username=username,
                password=password,
                full_name=full_name,
            )

            # Accept either a normal dict response or a truthy response.
            if response is False:
                raise RuntimeError("Account registration failed.")

            QMessageBox.information(
                self,
                "Account Created",
                "Your account has been created successfully.\n\n"
                "You can now sign in using your username and password.",
            )

            self.signup_completed.emit()
            self.back_to_login(clear_form=True)

        except Exception as exc:
            self.message.setText(str(exc))
        finally:
            self.signup_button.setEnabled(True)
            self.signup_button.setText("Create Account")

    def back_to_login(self, clear_form: bool = False) -> None:
        if clear_form:
            self.full_name.clear()
            self.username.clear()
            self.password.clear()
            self.confirm_password.clear()

        self.close()
        if self.login_window is not None:
            self.login_window.show()
            self.login_window.raise_()
            self.login_window.activateWindow()

    def closeEvent(self, event):
        if self.login_window is not None:
            self.login_window.show()
            self.login_window.raise_()
            self.login_window.activateWindow()
        event.accept()
