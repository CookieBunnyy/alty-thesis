from __future__ import annotations

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QAction, QFont
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QScrollArea,
    QSizePolicy,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.views.main.pages.agents import AgentsPage
from app.views.main.pages.analytics import AnalyticsPage
from app.views.main.pages.audit import AuditPage
from app.views.main.pages.clients import ClientsPage
from app.views.main.pages.dashboard import DashboardPage
from app.views.main.pages.documents import DocumentsPage
from app.views.main.pages.dss import DssPage
from app.views.main.pages.forecasting import ForecastingPage
from app.views.main.pages.media import MediaPage
from app.views.main.pages.partners import PartnersPage
from app.views.main.pages.properties import PropertiesPage
from app.views.main.pages.settings import SettingsPage
from app.views.main.pages.transactions import TransactionsPage
from app.views.main.pages.users import UsersPage
from app.views.main.pages.workforce import WorkforcePage


class MainWindow(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.all_pages = []
        self.nav_map = {}
        self.group_buttons = {}
        self.group_contents = {}
        self.group_arrows = {}
        self._drag_position = None
        self.build_ui()

    def build_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget {
                background: transparent;
                color: #17310a;
            }

            QWidget#appShell {
                background: #eef3e5;
                border: none;
                border-radius: 14px;
            }

            QWidget#sidebar {
                background: #17310a;
                border: 1px solid rgba(72, 107, 42, 0.10);
                border-radius: 14px;
            }

            QWidget#contentArea {
                background: #eef3e5;
                border: none;
                border-radius: 14px;
            }

            QWidget#topBar {
                background: #f7f9f3;
                border: none;
                border-radius: 12px;
            }

            QLabel {
                color: #17310a;
                border: none;
                background: transparent;
            }

            QLabel#navBrand {
                color: #f1f5eb;
                font-size: 18px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }

            QLabel#navSubtitle {
                color: #a9b39f;
                font-size: 11px;
                font-weight: 600;
                letter-spacing: 0.8px;
            }


            QToolButton#sectionButton {
                background: transparent;
                color: #f7f9f3;
                border: none;
                text-align: left;
                padding: 7px 5px 7px 28px;
                min-height: 26px;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.7px;
            }

            QToolButton#sectionButton:hover {
                background: rgba(180, 180, 180, 0.07);
                color: #f7f9f3;
                border-radius: 7px;
            }

            QToolButton#sectionButton:checked {
                color: #f7f9f3;
            }

            QLabel#sectionArrow {
                color: #f7f9f3;
                background: transparent;
                font-size: 16px;
                font-weight: 700;
                min-width: 18px;
            }

            QLabel#sectionLabel {
                color: #f7f9f3;
                background: transparent;
                font-size: 10px;
                font-weight: 700;
                letter-spacing: 1.7px;
            }

            QPushButton {
                background: transparent;
                border: none;
                padding: 8px 12px;
            }

            QLabel, QToolButton {
                border: none;
            }

            QPushButton#navButton {
                background: transparent;
                color: #b8c4ad;
                text-align: left;
                padding: 9px 12px;
                border-radius: 9px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton#navButton:hover {
                background: rgba(180, 180, 180, 0.07);
            }

            QPushButton#navButton[active="true"] {
                background: rgba(72, 107, 42, 0.16);
                color: #edf5df;
                border: 1px solid rgba(72, 107, 42, 0.34);
            }

            QToolButton#headerAction,
            QToolButton#windowAction {
                background: #edf2e7;
                color: #17310a;
                border: none;
                border-radius: 9px;
                min-width: 42px;
                min-height: 42px;
            }

            QToolButton#windowAction {
                min-width: 30px;
                min-height: 30px;
            }

            QScrollArea#pageScroll { background: transparent; border: none; }
            QScrollBar#pageScrollBar:vertical { width: 10px; background: transparent; }
            QScrollBar#pageScrollBar::handle:vertical { background: #b8c4ad; border-radius: 5px; min-height: 32px; }
            QScrollBar#pageScrollBar::handle:vertical:hover { background: #a9b39f; }

            QLineEdit#searchField {
                background: #f1f5eb;
                color: #17310a;
                border: 1px solid #c9d5bb;
                border-radius: 10px;
                padding: 10px 14px;
            }
            """
        )

        root_layout = QVBoxLayout(self)
        root_layout.setContentsMargins(6, 6, 6, 6)
        root_layout.setSpacing(0)

        self.app_shell = QWidget(self)
        self.app_shell.setObjectName("appShell")

        shell_layout = QHBoxLayout(self.app_shell)
        shell_layout.setContentsMargins(8, 8, 8, 8)
        shell_layout.setSpacing(10)

        self.sidebar = QWidget(self.app_shell)
        self.sidebar.setObjectName("sidebar")

        self.sidebar_layout = QVBoxLayout(self.sidebar)
        self.sidebar_layout.setContentsMargins(16, 16, 16, 12)
        self.sidebar_layout.setSpacing(7)

        brand_row = QHBoxLayout()

        self.brand_icon = QLabel("A")
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_icon.setFixedSize(34, 34)
        self.brand_icon.setStyleSheet(
            """
            background: rgba(72,107,42,0.18);
            color: #d7e8b7;
            border: none;
            border-radius: 9px;
            font-size: 19px;
            font-weight: 800;
            """
        )

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)

        self.brand = QLabel("ALTY")
        self.brand.setObjectName("navBrand")

        self.brand_subtitle = QLabel("INTERNAL MANAGEMENT")
        self.brand_subtitle.setObjectName("navSubtitle")

        brand_col.addWidget(self.brand)
        brand_col.addWidget(self.brand_subtitle)

        brand_row.addWidget(self.brand_icon)
        brand_row.addSpacing(9)
        brand_row.addLayout(brand_col)
        brand_row.addStretch()

        self.sidebar_layout.addLayout(brand_row)

        nav_groups = [
            ("MAIN", [
                ("Dashboard", "dashboard"),
            ]),
            ("PROPERTY OPERATIONS", [
                ("Properties", "properties"),
                ("Partners / Developers", "partners"),
            ]),
            ("CLIENT & TRANSACTIONS", [
                ("Buyers & Sellers", "clients"),
                ("Transactions", "transactions"),
                ("Commissions", "commissions"),
            ]),
            ("RECORDS", [
                ("Document Repository", "documents"),
                ("Digital Preview", "media"),
            ]),
            ("WORKFORCE", [
                ("Agents", "agents"),
                ("Workforce", "workforce"),
            ]),
            ("INTELLIGENCE", [
                ("Analytics", "analytics"),
                ("Forecasting", "forecasting"),
                ("Decision Support", "dss"),
            ]),
            ("SYSTEM", [
                ("Users & Access", "users"),
                ("Audit Logs", "audit"),
                ("Settings", "settings"),
            ]),
        ]

        # Navigation is placed inside a vertical scroll area so it
        # remains usable even on smaller screens.
        self.sidebar_scroll = QScrollArea()
        self.sidebar_scroll.setObjectName("sidebarScroll")
        self.sidebar_scroll.setWidgetResizable(True)
        self.sidebar_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.sidebar_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.sidebar_scroll.setStyleSheet(
            "QScrollArea { background: transparent; border: none; }"
            "QScrollBar:vertical { width: 7px; background: transparent; }"
            "QScrollBar::handle:vertical { background: rgba(180,180,180,0.30); border-radius: 3px; min-height: 24px; }"
        )

        nav_container = QWidget()
        nav_container.setStyleSheet("background: transparent;")
        nav_layout = QVBoxLayout(nav_container)
        nav_layout.setContentsMargins(0, 4, 4, 4)
        nav_layout.setSpacing(2)

        self.nav_map = {}

        for index, (group_name, items) in enumerate(nav_groups):
            # Section header: separate arrow and label so their font sizes
            # can be controlled independently.
            group_button = QToolButton()
            group_button.setObjectName("sectionButton")
            group_button.setCheckable(True)
            group_button.setChecked(index == 0)
            group_button.setCursor(Qt.CursorShape.PointingHandCursor)
            group_button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextOnly
            )

            group_button.setText(group_name)

            arrow_label = QLabel("▼" if index == 0 else "▶", group_button)
            arrow_label.setObjectName("sectionArrow")
            arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            self.group_arrows[group_name] = arrow_label

            group_content = QWidget()
            group_content.setStyleSheet("background: transparent;")
            group_layout = QVBoxLayout(group_content)
            group_layout.setContentsMargins(0, 0, 0, 3)
            group_layout.setSpacing(2)

            for label, key in items:
                btn = QPushButton(label)
                btn.setObjectName("navButton")
                btn.setCursor(Qt.CursorShape.PointingHandCursor)
                btn.clicked.connect(
                    lambda _, k=key: self.show_page(k)
                )
                btn.setProperty("pageKey", key)
                group_layout.addWidget(btn)
                self.nav_map[key] = btn

            self.group_buttons[group_name] = group_button
            self.group_contents[group_name] = group_content

            group_button.toggled.connect(
                lambda checked, name=group_name:
                self._toggle_nav_group(name, checked)
            )

            nav_layout.addWidget(group_button)
            nav_layout.addWidget(group_content)

            self._toggle_nav_group(
                group_name,
                index == 0,
                update_button=False,
            )

        nav_layout.addStretch()
        self.sidebar_scroll.setWidget(nav_container)
        self.sidebar_layout.addWidget(self.sidebar_scroll, 1)

        user_widget = QWidget(self.sidebar)
        user_widget.setStyleSheet(
            """
            QWidget {
                background: rgba(32, 59, 18, 0.96);
                border: none;
                border-radius: 12px;
            }
            """
        )

        user_layout = QVBoxLayout(user_widget)
        user_layout.setContentsMargins(10, 8, 10, 8)
        user_layout.setSpacing(2)

        self.user_label = QLabel("User")
        self.user_label.setStyleSheet("color: white; font-weight: 600;")

        self.role_label = QLabel("Role")
        self.role_label.setStyleSheet(
            "color: #b8c4ad; font-size: 12px; border: none;"
        )

        user_layout.addWidget(self.user_label)
        user_layout.addWidget(self.role_label)
        self.sidebar_layout.addWidget(user_widget)

        content = QWidget(self.app_shell)
        content.setObjectName("contentArea")

        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)

        self.header = QWidget(content)
        self.header.setObjectName("topBar")

        header_layout = QHBoxLayout(self.header)
        header_layout.setContentsMargins(12, 9, 12, 9)
        header_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setObjectName("searchField")
        self.search_input.setPlaceholderText("Search something...")
        self.search_input.setFixedHeight(40)

        search_button = QToolButton()
        search_button.setObjectName("headerAction")
        search_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        search_button.setIcon(qta.icon("fa5s.search", color="#486b2a"))
        search_button.setIconSize(QSize(16, 16))
        search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        search_button.setFixedSize(40, 40)
        search_button.clicked.connect(self.search_input.setFocus)

        header_layout.addWidget(self.search_input, 1)
        header_layout.addWidget(search_button)

        self.minimize_button = QToolButton()
        self.minimize_button.setObjectName("windowAction")
        self.minimize_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.minimize_button.setIcon(
            qta.icon("fa5.window-minimize", color="#486b2a")
        )
        self.minimize_button.setIconSize(QSize(15, 15))
        self.minimize_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.minimize_button.setFixedSize(30, 30)
        self.minimize_button.clicked.connect(self.minimize_window)

        self.maximize_button = QToolButton()
        self.maximize_button.setObjectName("windowAction")
        self.maximize_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.maximize_button.setIcon(
            qta.icon("fa5.window-maximize", color="#486b2a")
        )
        self.maximize_button.setIconSize(QSize(15, 15))
        self.maximize_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.maximize_button.setFixedSize(30, 30)
        self.maximize_button.clicked.connect(self.maximize_window)

        self.close_button = QToolButton()
        self.close_button.setObjectName("windowAction")
        self.close_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.close_button.setIcon(
            qta.icon("fa5.window-close", color="#486b2a")
        )
        self.close_button.setIconSize(QSize(15, 15))
        self.close_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_button.setFixedSize(30, 30)
        self.close_button.clicked.connect(self.close_window)

        self.settings_button = QToolButton()
        self.settings_button.setObjectName("headerAction")
        self.settings_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.settings_button.setIcon(
            qta.icon("fa5s.cog", color="#486b2a")
        )
        self.settings_button.setIconSize(QSize(17, 17))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        self.settings_menu = QMenu(self)
        self.settings_menu.setStyleSheet(
            """
            QMenu {
                background: #17310a;
                color: #c9d5bb;
                border: none;
                border-radius: 10px;
                padding: 8px;
            }

            QMenu::item {
                padding: 8px 14px;
                border-radius: 8px;
            }

            QMenu::item:selected {
                background: rgba(72,107,42,0.32);
            }
            """
        )

        logout_action = QAction(
            qta.icon("fa5s.sign-out-alt"),
            "Logout",
            self,
        )
        logout_action.triggered.connect(self.controller.logout)
        self.settings_menu.addAction(logout_action)

        settings_action = QAction(
            qta.icon("fa5s.cog"),
            "Settings",
            self,
        )
        settings_action.triggered.connect(
            lambda: self.show_page("settings")
        )
        self.settings_menu.addAction(settings_action)

        about_action = QAction(
            qta.icon("fa5s.info-circle"),
            "About",
            self,
        )
        about_action.triggered.connect(self.show_about)
        self.settings_menu.addAction(about_action)

        self.settings_button.setMenu(self.settings_menu)

        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.maximize_button)
        header_layout.addWidget(self.close_button)
        header_layout.addWidget(self.settings_button)

        self.page_title = QLabel("Dashboard")
        self.page_title.setStyleSheet(
            """
            font-size: 20px;
            font-weight: 700;
            color: #17310a;
            """
        )
        self.page_title.setContentsMargins(0, 2, 0, 0)

        title_row = QHBoxLayout()
        title_row.addWidget(self.page_title)
        title_row.addStretch()

        content_layout.addWidget(self.header)
        content_layout.addLayout(title_row)

        # Put the stacked pages inside a vertical scroll area.
        # This prevents large pages such as Dashboard, Analytics,
        # Forecasting, and DSS from being compressed into the viewport.
        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("pageScroll")
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self.page_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.stack = QStackedWidget()
        self.stack.setContentsMargins(0, 0, 0, 0)
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Minimum,
        )

        self.pages = {
            "dashboard": DashboardPage(),
            "properties": PropertiesPage(),
            "partners": PartnersPage(),
            "clients": ClientsPage(),
            "transactions": TransactionsPage(),
            # Temporary: Commissions currently reuses the transaction page
            # until a dedicated CommissionsPage is implemented.
            "commissions": TransactionsPage(),
            "documents": DocumentsPage(),
            "media": MediaPage(),
            "agents": AgentsPage(),
            "workforce": WorkforcePage(),
            "analytics": AnalyticsPage(),
            "forecasting": ForecastingPage(),
            "dss": DssPage(),
            "users": UsersPage(),
            "audit": AuditPage(),
            "settings": SettingsPage(),
        }

        for key, page in self.pages.items():
            self.stack.addWidget(page)
            self.all_pages.append(page)

        self.page_scroll.setWidget(self.stack)
        content_layout.addWidget(self.page_scroll, 1)

        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(content, 1)

        root_layout.addWidget(self.app_shell, 1)

        self.user_label.setText(self.controller.session.user_name)
        self.role_label.setText(self.controller.session.state.role)

        self._apply_responsive_sidebar()
        self.show_page("dashboard")

    def _toggle_nav_group(
        self,
        group_name: str,
        expanded: bool,
        update_button: bool = True,
    ) -> None:
        content = self.group_contents.get(group_name)
        button = self.group_buttons.get(group_name)

        if content is None or button is None:
            return

        content.setVisible(expanded)

        # Arrow has its own QLabel/style, independent from the section label.
        arrow_label = self.group_arrows.get(group_name)
        if arrow_label is not None:
            arrow_label.setText("▼" if expanded else "▶")
            arrow_label.setGeometry(5, 4, 18, max(24, button.height() - 8))
            arrow_label.raise_()

        button.setText(group_name)

        if update_button and button.isChecked() != expanded:
            button.blockSignals(True)
            button.setChecked(expanded)
            button.blockSignals(False)

    def _apply_responsive_sidebar(self) -> None:
        screen = self.screen() or self.window().screen() or QApplication.primaryScreen()

        if screen is None:
            width = 1366
        else:
            width = screen.availableGeometry().width()

        sidebar_width = max(220, min(280, int(width * 0.17)))
        self.sidebar.setFixedWidth(sidebar_width)

        brand_size = max(12, min(19, int(width * 0.013)))
        subtitle_size = max(9, min(11, int(width * 0.008)))
        nav_font = max(11, min(14, int(width * 0.009)))

        self.brand.setFont(
            QFont("Segoe UI", brand_size, QFont.Weight.Bold)
        )
        self.brand_subtitle.setFont(
            QFont("Segoe UI", subtitle_size, QFont.Weight.Bold)
        )

        for btn in self.nav_map.values():
            btn.setFont(
                QFont("Segoe UI", nav_font, QFont.Weight.DemiBold)
            )
            btn.setMinimumHeight(32)
            btn.setMaximumHeight(38)

        for group_name, arrow_label in self.group_arrows.items():
            button = self.group_buttons.get(group_name)
            if button is not None:
                arrow_label.setGeometry(
                    5, 4, 18, max(24, button.height() - 8)
                )
                arrow_label.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)

        if hasattr(self, "nav_map"):
            self._apply_responsive_sidebar()
        if hasattr(self, "stack"):
            self._resize_current_page()

    def minimize_window(self) -> None:
        self.controller.root.showMinimized()

    def maximize_window(self) -> None:
        if self.controller.root.isMaximized():
            self.controller.root.showNormal()
            self.maximize_button.setIcon(
                qta.icon("fa5.window-maximize", color="#486b2a")
            )
        else:
            self.controller.root.showMaximized()
            self.maximize_button.setIcon(
                qta.icon("fa5.window-restore", color="#486b2a")
            )

    def close_window(self) -> None:
        self.controller.root.close()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "Abellar Realty Management System\n"
            "Internal desktop management application.",
        )

    def mousePressEvent(self, event) -> None:
        if (
            event.button() == Qt.MouseButton.LeftButton
            and self.header.geometry().contains(event.pos())
        ):
            self._drag_position = (
                event.globalPosition().toPoint()
                - self.controller.root.frameGeometry().topLeft()
            )
        else:
            self._drag_position = None

        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:
        if self._drag_position is not None:
            self.controller.root.move(
                event.globalPosition().toPoint() - self._drag_position
            )
            return

        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:
        self._drag_position = None
        super().mouseReleaseEvent(event)

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return

        self.stack.setCurrentWidget(self.pages[key])
        self.page_title.setText(self.page_title_for_key(key))

        for nav_key, btn in self.nav_map.items():
            is_active = nav_key == key
            btn.setProperty("active", "true" if is_active else "false")
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

        self.stack.adjustSize()
        self._resize_current_page()

    def _resize_current_page(self) -> None:
        """Allow pages to become taller than the viewport so the page
        scroll area can actually scroll vertically."""
        if not hasattr(self, "page_scroll") or not hasattr(self, "stack"):
            return

        page = self.stack.currentWidget()
        if page is None:
            return

        viewport_height = self.page_scroll.viewport().height()
        content_height = max(
            page.sizeHint().height(),
            page.minimumSizeHint().height(),
            page.minimumHeight(),
        )

        self.stack.setMinimumHeight(
            max(viewport_height, content_height + 12)
        )

    def page_title_for_key(self, key: str) -> str:
        mapping = {
            "dashboard": "Dashboard",
            "properties": "Property Operations",
            "partners": "Partners / Developers",
            "clients": "Buyers & Sellers",
            "transactions": "Transactions",
            "commissions": "Commissions",
            "documents": "Document Repository",
            "agents": "Agents",
            "workforce": "Workforce",
            "media": "Digital Preview",
            "analytics": "Analytics",
            "forecasting": "Forecasting",
            "dss": "Decision Support",
            "users": "Users & Access",
            "audit": "Audit Logs",
            "settings": "Settings",
        }

        return mapping.get(key, "Dashboard")
