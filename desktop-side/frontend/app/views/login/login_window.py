from __future__ import annotations

from pathlib import Path

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QColor, QPixmap
from PyQt6.QtWidgets import (
    QCheckBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.api.client import ApiClient
from app.views.login.signup_window import SignUpWindow


class FloatingLabelInput(QFrame):
    textChanged = pyqtSignal(str)
    editingFinished = pyqtSignal()

    def __init__(self, label_text: str, password: bool = False, parent=None) -> None:
        super().__init__(parent)
        self._label_text = label_text
        self._password = password
        self.setObjectName("floatingLabelInput")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setFixedHeight(58)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(200)

        self.label = QLabel(label_text, self)
        self.label.setObjectName("floatingLabel")
        self.label.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        self.label.raise_()

        self.line_edit = QLineEdit(self)
        self.line_edit.setObjectName("floatingLineEdit")
        self.line_edit.setFrame(False)
        self.line_edit.setTextMargins(0, 0, 0, 0)
        self.line_edit.textChanged.connect(self._handle_text_changed)
        self.line_edit.textChanged.connect(self.textChanged)
        self.line_edit.editingFinished.connect(self.editingFinished)
        self.line_edit.installEventFilter(self)

        if password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button = QToolButton(self)
            self.toggle_button.setObjectName("togglePassword")
            self.toggle_button.setCursor(Qt.CursorShape.PointingHandCursor)
            self.toggle_button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            self.toggle_button.setAutoRaise(True)
            self.toggle_button.setIcon(qta.icon("fa5.eye", color="#294c16"))
            self.toggle_button.setIconSize(QSize(18, 18))
            self.toggle_button.clicked.connect(self._toggle_visibility)
            self.toggle_button.raise_()
        else:
            self.toggle_button = None

        self.apply_styles()
        self.update_label_state()

    def apply_styles(self):
        self.setStyleSheet(
            """
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
                background: rgba(15, 23, 42, 0.06);
                border-radius: 6px;
            }
            """
        )
        self.setProperty("focused", self.line_edit.hasFocus())
        self.style().polish(self)

    def resizeEvent(self, event):
        super().resizeEvent(event)
        self.update_label_state()

    def eventFilter(self, obj, event):
        if obj is self.line_edit and event.type() in (event.Type.FocusIn, event.Type.FocusOut):
            self.update_label_state()
        return super().eventFilter(obj, event)

    def update_label_state(self):
        floating = self.line_edit.hasFocus() or bool(self.line_edit.text())

        self.setProperty("focused", self.line_edit.hasFocus())
        self.style().polish(self)

        if floating:
            self.label.setGeometry(14, 5, self.width() - 28, 16)
            self.label.setStyleSheet(
                """
                QLabel#floatingLabel {
                    color: #486b2a;
                    background: transparent;
                    font-size: 8px;
                    font-weight: 500;
                    letter-spacing: 0.3px;
                    padding: 0;
                    margin: 0;
                }
                """
            )
            self.line_edit.setGeometry(
                10,
                20,
                self.width() - 22 - (42 if self._password else 0),
                30,
            )
        else:
            self.label.setGeometry(14, 0, self.width() - 28, self.height())
            self.label.setStyleSheet(
                """
                QLabel#floatingLabel {
                    color: #999999;
                    background: transparent;
                    font-size: 10px;
                    font-weight: 500;
                    letter-spacing: 0.3px;
                    padding: 0;
                    margin: 0;
                }
                """
            )
            self.line_edit.setGeometry(
                10,
                0,
                self.width() - 22 - (42 if self._password else 0),
                self.height(),
            )

        if self._password:
            button_width = 32
            button_x = self.width() - 38
            self.toggle_button.setGeometry(button_x, 11, button_width, button_width)
            self.toggle_button.raise_()

        self.label.raise_()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            self.line_edit.setFocus()
            self.line_edit.setCursorPosition(len(self.line_edit.text()))
        super().mousePressEvent(event)

    def _handle_text_changed(self, text):
        self.update_label_state()

    def _toggle_visibility(self):
        if self.line_edit.echoMode() == QLineEdit.EchoMode.Password:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            self.toggle_button.setIcon(qta.icon("fa5.eye-slash", color="#294c16"))
        else:
            self.line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            self.toggle_button.setIcon(qta.icon("fa5.eye", color="#294c16"))
        self.line_edit.setFocus()

    def text(self):
        return self.line_edit.text()

    def setText(self, text):
        self.line_edit.setText(text)

    def clear(self):
        self.line_edit.clear()

    def setFocus(self):
        self.line_edit.setFocus()

    def setEnabled(self, enabled):
        super().setEnabled(enabled)
        self.line_edit.setEnabled(enabled)
        if self.toggle_button is not None:
            self.toggle_button.setEnabled(enabled)

    def setEchoMode(self, mode):
        self.line_edit.setEchoMode(mode)

    def echoMode(self):
        return self.line_edit.echoMode()

    def setPlaceholderText(self, text):
        self.line_edit.setPlaceholderText(text)

    def focusInEvent(self, event):
        super().focusInEvent(event)
        self.update_label_state()

    def focusOutEvent(self, event):
        super().focusOutEvent(event)
        self.update_label_state()


class ResponsiveLoginButton(QPushButton):
    def __init__(self, text: str = "Login", parent=None) -> None:
        super().__init__(text, parent)
        self.setObjectName("loginButton")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(52)
        self.setStyleSheet(
            """
            QPushButton#loginButton {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #486b2a, stop:1 #294c16);
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px 18px;
                font-size: 16px;
                font-weight: 700;
            }
            QPushButton#loginButton:hover {
                background: #294c16;
            }
            QPushButton#loginButton:pressed {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 #294c16, stop:1 #203b12);
            }
            QPushButton#loginButton:disabled {
                background: #b4b4b4;
                color: #c8c8c8;
            }
            """
        )

        self.shadow = QGraphicsDropShadowEffect(self)
        self.shadow.setBlurRadius(0)
        self.shadow.setXOffset(0)
        self.shadow.setYOffset(6)
        self.shadow.setColor(QColor(72, 107, 42, 100))
        self.setGraphicsEffect(self.shadow)

    def enterEvent(self, event):
        self.shadow.setBlurRadius(18)
        self.shadow.setYOffset(8)
        super().enterEvent(event)

    def leaveEvent(self, event):
        self.shadow.setBlurRadius(0)
        self.shadow.setYOffset(6)
        super().leaveEvent(event)


class RealEstateHeroImage(QLabel):
    """Responsive real-estate image panel using a project-relative asset."""

    def __init__(self, image_path: Path, parent=None) -> None:
        super().__init__(parent)
        self._image_path = Path(image_path)
        self._pixmap = QPixmap(str(self._image_path))
        self.setObjectName("realEstateHero")
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet(
            """
            QLabel#realEstateHero {
                background: #17310a;
                border: none;
            }
            """
        )

        if self._pixmap.isNull():
            self.setText("")

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._update_pixmap()

    def _update_pixmap(self) -> None:
        if self._pixmap.isNull() or self.width() <= 0 or self.height() <= 0:
            return

        target_w = self.width()
        target_h = self.height()

        scaled = self._pixmap.scaled(
            target_w,
            target_h,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation,
        )

        x = max(0, (scaled.width() - target_w) // 2)
        y = max(0, (scaled.height() - target_h) // 2)

        cropped = scaled.copy(x, y, target_w, target_h)
        self.setPixmap(cropped)



class LoginWindow(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.signup_window = None
        self.loading_step = 0
        self.loading_timer = QTimer(self)
        self.loading_timer.timeout.connect(self._tick_loading)
        self.build_ui()

    def build_ui(self) -> None:
        self.setObjectName("loginWindow")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._drag_position = None
        self.setStyleSheet(
            """
            QWidget#loginWindow {
                background: transparent;
            }

            QWidget#cardShell {
                background: transparent;
            }

            QWidget#loginCard {
                background: rgba(18, 38, 8, 0.96);
                border: 1px solid rgba(180, 180, 180, 0.22);
                border-radius: 20px;
            }

            QWidget#brandPanel {
                background: #d8ecb6;
            }

            QWidget#formPanel {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
                    stop:0 rgba(16, 34, 7, 0.98), stop:1 rgba(23, 49, 10, 0.98));
            }

            QLabel {
                color: #d8d8d8;
                background: transparent;
            }

            QLabel#brandTitle {
                color: #e8e8e8;
                font-size: 35px;
                font-weight: 700;
                letter-spacing: 1.5px;
            }

            QLabel#brandSubtitle {
                color: #c8c8c8;
                font-size: 11px;
                letter-spacing: 2px;
                background: transparent;
            }

            QLabel#brandMessage {
                color: #d8d8d8;
                font-size: 16px;
                line-height: 1.5;
                background: transparent;
            }

            QLabel#pageTitle {
                color: #e8e8e8;
                font-size: 30px;
                font-weight: 700;
                background: transparent;
            }

            QLabel#pageSubtitle {
                color: #a9a9a9;
                font-size: 13px;
                background: transparent;
            }

            QLabel#fieldLabel {
                color: #c8c8c8;
                font-size: 12px;
                font-weight: 600;
                padding-bottom: 6px;
                background: transparent;
            }

            QLabel#helperText {
                color: #a9a9a9;
                font-size: 11px;
                background: transparent;
            }

            QLabel#errorLabel {
                color: #fca5a5;
                font-size: 12px;
                min-height: 18px;
                background: transparent;
            }

            QCheckBox {
                color: #c8c8c8;
                font-size: 12px;
            }

            QCheckBox::indicator {
                width: 15px;
                height: 15px;
                border-radius: 4px;
                border: 1px solid #b4b4b4;
                background: rgba(15, 23, 42, 0.85);
                
            }

            QCheckBox::indicator:checked {
                background: #486b2a;
                border: 1px solid #486b2a;
                color: #c8c8c8;
            }

            QPushButton {
                background: #486b2a;
                color: white;
                border: none;
                border-radius: 12px;
                padding: 14px 18px;
                font-size: 16px;
                font-weight: 700;
            }

            QPushButton:hover {
                background: #5d8138;
            }

            QPushButton:pressed {
                background: #294c16;
            }

            QPushButton:disabled {
                background: #b4b4b4;
                color: #c8c8c8;
            }

            QPushButton#togglePassword {
                background: transparent;
                color: #b4b4b4;
                border: 1px solid #536b43;
                border-radius: 10px;
                padding: 8px 10px;
                font-size: 11px;
                font-weight: 600;
                min-width: 58px;
            }

            QPushButton#togglePassword:hover {
                background: rgba(180, 180, 180, 0.10);
            }

            QLabel#forgotPassword {
                color: #b4b4b4;
                font-size: 12px;
                font-weight: 600;
            }

            QLabel#versionLabel {
                color: #999999;
                font-size: 11px;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(18, 18, 18, 18)
        root_layout.setSpacing(0)

        card_container = QWidget(self)
        card_container.setObjectName("cardShell")
        card_layout = QHBoxLayout(card_container)
        card_layout.setContentsMargins(0, 0, 0, 0)
        card_layout.setSpacing(0)

        card = QWidget(card_container)
        card.setObjectName("loginCard")
        card.setFixedSize(900, 500)
        card_layout.addWidget(card, 0, Qt.AlignmentFlag.AlignCenter)
        card_inner_layout = QHBoxLayout(card)
        card_inner_layout.setContentsMargins(0, 0, 0, 0)
        card_inner_layout.setSpacing(0)

        left_panel = QWidget(card)
        left_panel.setObjectName("brandPanel")
        left_panel.setFixedWidth(430)
        left_layout = QVBoxLayout(left_panel)
        left_layout.setContentsMargins(32, 28, 32, 26)
        left_layout.setSpacing(14)

        logo_row = QHBoxLayout()
        logo_row.setContentsMargins(0, 0, 0, 0)
       
        logo_text = QLabel("ALTY")
        logo_text.setStyleSheet(
            "color: #294c16; font-size: 22px; font-weight: 1000; letter-spacing: 2px; line-height: 1.1; background: transparent;"
        )
       
        logo_row.addWidget(logo_text)
        logo_row.addStretch()
        left_layout.addLayout(logo_row)

        self.username_input = FloatingLabelInput("USERNAME")
        self.username_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.username_input.line_edit.setFocus()
        left_layout.addWidget(self.username_input)

        self.password_input = FloatingLabelInput("PASSWORD", password=True)
        self.password_input.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        left_layout.addWidget(self.password_input)

        remember_row = QHBoxLayout()
        remember_row.setContentsMargins(0, 0, 0, 0)
        self.remember_check = QCheckBox("Stay signed in")
        self.remember_check.setChecked(True)
        self.remember_check.setStyleSheet(
            """
            QCheckBox {
                color: #294c16;
                font-size: 12px;
                font-weight: 600;
                spacing: 8px;
                background: transparent;
            }
            
            QCheckBox::indicator {
                width: 17px;
                height: 17px;
                border-radius: 4px;
                border: 1px solid #6b8058;
                background: #294c16;
            }
           
            QCheckBox::indicator:checked {
                background: #6f9348;
                border: 1px solid #b4b4b4;
            }
            """
        )
        remember_row.addWidget(self.remember_check)
        remember_row.addStretch()
        left_layout.addLayout(remember_row)

        self.login_button = ResponsiveLoginButton("Sign In")
        self.login_button.setFixedHeight(48)
        self.login_button.clicked.connect(self.handle_login)
        left_layout.addWidget(self.login_button)

        self.loading_label = QLabel("")
        self.loading_label.setStyleSheet(
            "color: #999999; font-size: 11px; background: transparent; min-height: 14px; qproperty-alignment: AlignCenter;"
        )
        left_layout.addWidget(self.loading_label)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setStyleSheet(
            "color: #e0a0a0; font-size: 11px; background: transparent; min-height: 14px;"
        )
        left_layout.addWidget(self.error_label)

        self.signup_link = QPushButton("CAN'T SIGN IN?  v13.0.8")
        self.signup_link.setObjectName("signupLink")
        self.signup_link.setCursor(Qt.CursorShape.PointingHandCursor)
        self.signup_link.setStyleSheet(
            """
            QPushButton#signupLink {
                color: #294c16;
                background: transparent;
                border: none;
                padding: 0;
                text-align: left;
                font-size: 10px;
                font-weight: 600;
                letter-spacing: 1px;
            }
            QPushButton#signupLink:hover {
                color: #486b2a;
            }
            """
        )
        self.signup_link.clicked.connect(self.open_signup_window)
        left_layout.addWidget(self.signup_link)
        left_layout.addStretch()

        right_panel = QWidget(card)
        right_panel.setObjectName("formPanel")
        right_panel.setFixedWidth(470)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # Window controls live inside the dark panel so there is
        # no separate application title/header bar.
        window_controls = QHBoxLayout()
        window_controls.setContentsMargins(0, 8, 14, 0)
        window_controls.setSpacing(6)

        self.minimize_button = QPushButton()
        self.minimize_button.setFixedSize(30, 26)
        self.minimize_button.setToolTip("Minimize")
        self.minimize_button.setIcon(qta.icon("fa5.window-minimize", color="white"))
        self.minimize_button.setIconSize(QSize(14, 14))
        self.minimize_button.setStyleSheet(
            "QPushButton { background: transparent; color: white; border: none; "
            "padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); "
            "border-radius: 5px; }"
        )
        self.minimize_button.clicked.connect(self.minimize_window)

        self.maximize_button = QPushButton()
        self.maximize_button.setFixedSize(30, 26)
        self.maximize_button.setToolTip("Maximize")
        self.maximize_button.setIcon(qta.icon("fa5.window-maximize", color="white"))
        self.maximize_button.setIconSize(QSize(14, 14))
        self.maximize_button.setStyleSheet(
            "QPushButton { background: transparent; color: white; border: none; "
            "padding: 0; }"
            "QPushButton:hover { background: rgba(255,255,255,0.08); "
            "border-radius: 5px; }"
        )
        self.maximize_button.clicked.connect(self.maximize_window)

        self.close_button = QPushButton()
        self.close_button.setFixedSize(30, 26)
        self.close_button.setToolTip("Close")
        self.close_button.setIcon(qta.icon("fa5.window-close", color="white"))
        self.close_button.setIconSize(QSize(15, 15))
        self.close_button.setStyleSheet(
            "QPushButton { background: transparent; color: white; border: none; "
            "padding: 0; }"
            "QPushButton:hover { background: rgba(239,68,68,0.22); "
            "border-radius: 5px; }"
        )
        self.close_button.clicked.connect(self.close_window)

        window_controls.addStretch()
        window_controls.addWidget(self.minimize_button)
        window_controls.addWidget(self.maximize_button)
        window_controls.addWidget(self.close_button)

        right_layout.addLayout(window_controls)
        right_layout.addSpacing(2)

        # Real-estate image panel.
        image_path = Path(__file__).resolve().parent / "assets" / "real_estate_login.png"
        hero = RealEstateHeroImage(image_path, right_panel)
        right_layout.addWidget(hero, 1)

        card_inner_layout.addWidget(left_panel, 40)
        card_inner_layout.addWidget(right_panel, 60)

        root_layout.addStretch(1)
        root_layout.addWidget(card_container)
        root_layout.addStretch(1)

        self.setWindowTitle("Abellar Realty - Login")
        self.setMinimumSize(980, 620)

    def minimize_window(self) -> None:
        self.window().showMinimized()

    def maximize_window(self) -> None:
        if self.window().isMaximized():
            self.window().showNormal()
            self.maximize_button.setText("□")
        else:
            self.window().showMaximized()
            self.maximize_button.setText("▢")

    def close_window(self) -> None:
        self.window().close()

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            child = self.childAt(event.position().toPoint())

            if child in (
                self.minimize_button,
                self.maximize_button,
                self.close_button,
            ):
                self._drag_position = None
            else:
                self._drag_position = (
                    event.globalPosition().toPoint()
                    - self.window().frameGeometry().topLeft()
                )
        else:
            self._drag_position = None

    def mouseMoveEvent(self, event):
        if self._drag_position is not None:
            self.window().move(event.globalPosition().toPoint() - self._drag_position)
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event):
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def open_signup_window(self) -> None:
        """Open the basic account registration window."""
        if self.signup_window is None:
            self.signup_window = SignUpWindow(
                api=self.api,
                login_window=self,
            )

        self.hide()
        self.signup_window.show()
        self.signup_window.raise_()
        self.signup_window.activateWindow()

    def toggle_password_visibility(self) -> None:
        self.password_input._toggle_visibility()

    def _tick_loading(self) -> None:
        self.loading_step += 1
        dots = "." * (self.loading_step % 4)
        self.loading_label.setText(f"Signing in{dots or ' '}")

    def _start_loading(self) -> None:
        self.loading_step = 0
        self.loading_timer.start(350)
        self.login_button.setEnabled(False)
        self.login_button.setText("Signing in")
        self.loading_label.setText("Signing in")

    def _stop_loading(self) -> None:
        self.loading_timer.stop()
        self.loading_label.setText("")
        self.login_button.setEnabled(True)
        self.login_button.setText("Sign In")

    def handle_login(self) -> None:
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not username or not password:
            self.error_label.setText("Please enter both username and password.")
            return

        self.error_label.setText("")
        self._start_loading()

        try:
            token_response = self.api.login(username, password)
            self.controller.session.set_session(
                token=token_response.get("access_token", ""),
                user={"username": username, "full_name": username.title()},
                role="General Manager",
                permissions=[
                    "dashboard",
                    "properties",
                    "partners",
                    "clients",
                    "transactions",
                    "documents",
                    "agents",
                    "workforce",
                    "media",
                    "analytics",
                    "forecasting",
                    "dss",
                    "users",
                    "audit",
                    "settings",
                ],
            )
            self._stop_loading()
            self.controller.show_main()
        except Exception as exc:  # pragma: no cover - UI error handling
            self.error_label.setText(str(exc))
            self._stop_loading()
