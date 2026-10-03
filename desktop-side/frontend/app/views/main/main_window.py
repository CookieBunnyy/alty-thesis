from __future__ import annotations

from datetime import datetime

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
from app.views.main.pages.partners import PARTNERS, PartnersPage
from app.views.main.pages.properties import PropertiesPage
from app.views.main.pages.settings import SettingsPage
from app.views.main.pages.transactions import TransactionsPage
from app.views.main.pages.users import UsersPage
from app.views.main.pages.workforce import WorkforcePage
from app.busy import busy_tracker
from app.i18n import tr
from app.views.notifications import NotificationPanel
from app.views.loading import BusyBar, BusyIndicators, LoadingOverlay
from app.views.theme_toggle import ThemeToggleButton
from app.views.window_frame import is_drag_area, start_move, toggle_maximized
from app.views.main.global_search import GlobalSearchDialog
from app.theme import TOKENS


def shell_stylesheet() -> str:
    t = TOKENS
    return f"""/*alty-raw*/
QWidget {{ background: transparent; color: {t['text']}; }}
QWidget#appShell {{ background: {t['bg']}; border: 1px solid {t['border']}; border-radius: 14px; }}
QWidget#sidebar {{ background: {t['sidebar']}; border: 1px solid {t['border']}; border-radius: 14px; }}
QWidget#contentArea {{ background: {t['bg']}; border: none; }}
QWidget#topBar {{ background: {t['sidebar']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QLabel {{ background: transparent; border: none; color: {t['text']}; }}
QLabel#navBrand {{ color: {t['text']}; font-size: 18px; font-weight: 800; letter-spacing: 1px; }}
QLabel#navSubtitle {{ color: {t['text_faint']}; font-size: 10px; font-weight: 700; letter-spacing: 1.4px; }}
QLabel#brandMark {{ background: {t['accent']}; color: {t['accent_ink']}; border-radius: 9px;
    font-size: 18px; font-weight: 900; }}
QToolButton#sectionButton {{ background: transparent; color: {t['text_faint']}; border: none;
    text-align: left; padding: 12px 6px 4px 10px; font-size: 10px; font-weight: 700; letter-spacing: 1.6px; }}
QToolButton#sectionButton:hover {{ color: {t['text_muted']}; }}
QLabel#sectionArrow {{ color: transparent; }}
QPushButton#navButton {{ background: transparent; color: {t['text_muted']}; text-align: left;
    padding: 9px 12px; border: none; border-radius: 9px; font-size: 13px; font-weight: 600; }}
QPushButton#navButton:hover {{ background: {t['hover']}; color: {t['text']}; }}
QPushButton#navButton[active="true"] {{ background: {t['accent']}; color: {t['accent_ink']}; }}
QToolButton#headerAction, QToolButton#windowAction {{ background: {t['card']}; color: {t['text']};
    border: 1px solid {t['border']}; border-radius: 9px; min-width: 38px; min-height: 38px; }}
QToolButton#windowAction {{ min-width: 30px; min-height: 30px; }}
QToolButton#headerAction:hover, QToolButton#windowAction:hover {{ background: {t['hover']};
    border-color: {t['border_strong']}; }}
QToolButton#headerAction::menu-indicator {{ image: none; }}
QMenu {{ background: {t['card_2']}; color: {t['text']}; border: 1px solid {t['border_strong']};
    border-radius: 8px; padding: 6px; }}
QMenu::item {{ padding: 7px 18px 7px 12px; border-radius: 6px; }}
QMenu::item:selected {{ background: {t['accent_soft_2']}; color: {t['accent']}; }}
QMenu::separator {{ height: 1px; background: {t['border']}; margin: 5px 8px; }}
QToolButton#statusChip {{ background: {t['card']}; color: {t['text_muted']}; border: 1px solid {t['border']};
    border-radius: 9px; padding: 0 10px; min-height: 38px; font-size: 12px; font-weight: 600; }}
QToolButton#statusChip:hover {{ background: {t['hover']}; color: {t['text']}; }}
QToolButton#statusChip[alert="true"] {{ color: {t['danger']}; border-color: {t['danger']}; }}
QToolButton#statusChip[ok="true"] {{ color: {t['success']}; }}
QWidget#userChip {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 10px; }}
QLabel#avatar {{ background: {t['accent_soft_2']}; color: {t['accent']}; border-radius: 16px;
    font-weight: 800; font-size: 12px; }}
QLabel#userName {{ color: {t['text']}; font-weight: 700; font-size: 12px; }}
QLabel#userRole {{ color: {t['text_faint']}; font-size: 11px; }}
QWidget#sidebarUser {{ background: {t['card']}; border: 1px solid {t['border']}; border-radius: 12px; }}
QScrollArea#pageScroll {{ background: transparent; border: none; }}
QLineEdit#searchField {{ background: {t['card']}; color: {t['text']}; border: 1px solid {t['border']};
    border-radius: 10px; padding: 9px 14px; font-size: 13px; }}
QLineEdit#searchField:focus {{ border: 1px solid {t['accent']}; }}
QLabel#pageTitle {{ color: {t['text']}; font-size: 20px; font-weight: 800; }}
QLabel#pageGreeting {{ color: {t['text_muted']}; font-size: 13px; }}
"""


NAV_ICONS = {
    "dashboard": "fa5s.tachometer-alt",
    "properties": "fa5s.home",
    "partners": "fa5s.handshake",
    "clients": "fa5s.users",
    "transactions": "fa5s.exchange-alt",
    "documents": "fa5s.folder-open",
    "media": "fa5s.images",
    "agents": "fa5s.user-tie",
    "workforce": "fa5s.sitemap",
    "analytics": "fa5s.chart-bar",
    "forecasting": "fa5s.chart-line",
    "dss": "fa5s.lightbulb",
    "users": "fa5s.user-shield",
    "audit": "fa5s.clipboard-list",
    "settings": "fa5s.cog",
}


class CurrentPageStack(QStackedWidget):
    """A stack that sizes itself by the visible page only.

    QStackedWidget normally reports the largest size (and height-for-width)
    of *all* pages, so every page became as tall/wide as the biggest one and
    its tables stopped scrolling.
    """

    def __init__(self) -> None:
        super().__init__()
        self.currentChanged.connect(lambda _index: self.updateGeometry())

    def sizeHint(self) -> QSize:
        page = self.currentWidget()
        return page.sizeHint() if page is not None else super().sizeHint()

    def minimumSizeHint(self) -> QSize:
        page = self.currentWidget()
        return page.minimumSizeHint() if page is not None else super().minimumSizeHint()

    def hasHeightForWidth(self) -> bool:
        return False

    def heightForWidth(self, _width: int) -> int:
        # QScrollArea asks this (via the internal layout, which would answer
        # with the tallest page). -1 = "use the minimum size we set".
        return -1


class MainWindow(QWidget):
    def __init__(self, controller) -> None:
        super().__init__()
        self.controller = controller
        self.all_pages = []
        from app.api.client import ApiClient

        self.search_api = ApiClient()
        self.nav_map = {}
        self.group_buttons = {}
        self.group_contents = {}
        self.group_arrows = {}
        self._drag_position = None
        self.build_ui()

    def build_ui(self) -> None:
        self.setStyleSheet(shell_stylesheet())

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
        self.brand_icon.setObjectName("brandMark")
        self.brand_icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.brand_icon.setFixedSize(36, 36)

        brand_col = QVBoxLayout()
        brand_col.setSpacing(1)

        self.brand = QLabel("ALTY")
        self.brand.setObjectName("navBrand")

        self.brand_subtitle = QLabel("ABELLAR REALTY")
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
                ("Properties", "properties"),
                ("Buyers & Sellers", "clients"),
                ("Transactions", "transactions"),
                ("Agents", "agents"),
                ("Partners / Developers", "partners"),
            ]),
            ("INTELLIGENCE", [
                ("Analytics", "analytics"),
                ("Forecasting", "forecasting"),
                ("Decision Support", "dss"),
                ("Digital Preview", "media"),
            ]),
            ("OPERATIONS", [
                ("Document Repository", "documents"),
                ("Workforce", "workforce"),
                ("Users & Access", "users"),
                ("Audit Logs", "audit"),
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
            f"QScrollBar::handle:vertical {{ background: {TOKENS['border_strong']}; border-radius: 3px; min-height: 24px; }}"
        )

        nav_container = QWidget()
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
            group_button.setChecked(True)
            group_button.setCursor(Qt.CursorShape.PointingHandCursor)
            group_button.setToolButtonStyle(
                Qt.ToolButtonStyle.ToolButtonTextOnly
            )

            group_button.setText(tr(group_name))

            arrow_label = QLabel("", group_button)
            arrow_label.setObjectName("sectionArrow")
            arrow_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
            arrow_label.setAttribute(
                Qt.WidgetAttribute.WA_TransparentForMouseEvents, True
            )
            self.group_arrows[group_name] = arrow_label

            group_content = QWidget()
            group_layout = QVBoxLayout(group_content)
            group_layout.setContentsMargins(0, 0, 0, 3)
            group_layout.setSpacing(2)

            for label, key in items:
                label = tr(label)
                btn = QPushButton(label.replace("&", "&&"))  # "&" is Qt's mnemonic marker
                btn.setObjectName("navButton")
                btn.setIcon(qta.icon(NAV_ICONS.get(key, "fa5s.circle"), color=TOKENS["text_muted"]))
                btn.setIconSize(QSize(16, 16))
                btn.setToolTip(label)
                btn.setProperty("fullText", label.replace("&", "&&"))
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
                True,
                update_button=False,
            )

        nav_layout.addStretch()
        self.sidebar_scroll.setWidget(nav_container)
        self.sidebar_layout.addWidget(self.sidebar_scroll, 1)

        # The signed-in user is shown in the header chip (no duplicate here).

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
        self.search_input.setPlaceholderText(
            tr("Search properties, clients, transactions, agents, documents… (press Enter)")
        )
        self.search_input.setClearButtonEnabled(True)
        self.search_input.returnPressed.connect(self.run_global_search)
        self.search_input.setFixedHeight(40)

        search_button = QToolButton()
        search_button.setObjectName("headerAction")
        search_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        search_button.setIcon(qta.icon("fa5s.search", color=TOKENS["accent"]))
        search_button.setIconSize(QSize(16, 16))
        search_button.setCursor(Qt.CursorShape.PointingHandCursor)
        search_button.setFixedSize(40, 40)
        search_button.setToolTip(tr("Search all records"))
        search_button.clicked.connect(self.run_global_search)

        self.sidebar_toggle = QToolButton()
        self.sidebar_toggle.setObjectName("headerAction")
        self.sidebar_toggle.setIcon(qta.icon("fa5s.bars", color=TOKENS["text"]))
        self.sidebar_toggle.setIconSize(QSize(16, 16))
        self.sidebar_toggle.setFixedSize(40, 40)
        self.sidebar_toggle.setToolTip(tr("Collapse / expand the sidebar"))
        self.sidebar_toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sidebar_toggle.clicked.connect(self.toggle_sidebar)
        self.sidebar_collapsed = False

        self.sync_chip = QToolButton()
        self.sync_chip.setObjectName("statusChip")
        self.sync_chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.sync_chip.setIcon(qta.icon("fa5s.cloud", color=TOKENS["text_muted"]))
        self.sync_chip.setText("Sync")
        self.sync_chip.setToolTip("Central database synchronization status")
        self.sync_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_chip.clicked.connect(lambda: self.show_page("settings"))

        self.alert_chip = QToolButton()
        self.alert_chip.setObjectName("statusChip")
        self.alert_chip.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.alert_chip.setIcon(qta.icon("fa5s.bell", color=TOKENS["text_muted"]))
        self.alert_chip.setText("0")
        self.alert_chip.setToolTip(tr("Notifications"))
        self.alert_chip.setAccessibleName(tr("Notifications"))
        self.alert_chip.setCursor(Qt.CursorShape.PointingHandCursor)
        self.alert_chip.clicked.connect(self.toggle_notifications)
        self.notification_panel = NotificationPanel(
            self.search_api, lambda: self.controller.session.state.token, self.open_notification, self)
        self.notification_panel.changed.connect(self._show_notification_count)

        self.user_chip = QWidget()
        self.user_chip.setObjectName("userChip")
        chip_layout = QHBoxLayout(self.user_chip)
        chip_layout.setContentsMargins(6, 3, 12, 3)
        chip_layout.setSpacing(8)
        self.header_avatar = QLabel("—")
        self.header_avatar.setObjectName("avatar")
        self.header_avatar.setFixedSize(32, 32)
        self.header_avatar.setAlignment(Qt.AlignmentFlag.AlignCenter)
        chip_text = QVBoxLayout()
        chip_text.setSpacing(0)
        self.header_user = QLabel("User")
        self.header_user.setObjectName("userName")
        self.header_role = QLabel("Role")
        self.header_role.setObjectName("userRole")
        chip_text.addWidget(self.header_user)
        chip_text.addWidget(self.header_role)
        chip_layout.addWidget(self.header_avatar)
        chip_layout.addLayout(chip_text)

        header_layout.addWidget(self.sidebar_toggle)
        header_layout.addWidget(self.search_input, 1)
        header_layout.addWidget(search_button)
        header_layout.addWidget(self.sync_chip)
        header_layout.addWidget(self.alert_chip)
        header_layout.addWidget(self.user_chip)

        self.minimize_button = QToolButton()
        self.minimize_button.setObjectName("windowAction")
        self.minimize_button.setToolButtonStyle(
            Qt.ToolButtonStyle.ToolButtonIconOnly
        )
        self.minimize_button.setIcon(
            qta.icon("fa5.window-minimize", color=TOKENS["text_muted"])
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
            qta.icon("fa5.window-maximize", color=TOKENS["text_muted"])
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
            qta.icon("fa5.window-close", color=TOKENS["text_muted"])
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
            qta.icon("fa5s.cog", color=TOKENS["accent"])
        )
        self.settings_button.setIconSize(QSize(17, 17))
        self.settings_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_button.setFixedSize(40, 40)
        self.settings_button.setPopupMode(
            QToolButton.ToolButtonPopupMode.InstantPopup
        )

        self.settings_menu = QMenu(self)
        # Styled by the global theme (QMenu).

        logout_action = QAction(
            qta.icon("fa5s.sign-out-alt", color=TOKENS["text_muted"]),
            tr("Logout"),
            self,
        )
        logout_action.triggered.connect(self.controller.logout)
        self.settings_menu.addAction(logout_action)

        settings_action = QAction(
            qta.icon("fa5s.cog", color=TOKENS["text_muted"]),
            tr("Settings"),
            self,
        )
        settings_action.triggered.connect(
            lambda: self.show_page("settings")
        )
        self.settings_menu.addAction(settings_action)

        about_action = QAction(
            qta.icon("fa5s.info-circle", color=TOKENS["text_muted"]),
            tr("About"),
            self,
        )
        about_action.triggered.connect(self.show_about)
        self.settings_menu.addAction(about_action)

        self.settings_button.setMenu(self.settings_menu)

        # Light/dark switch sits with the window controls: [theme] [—] [□] [×]
        self.theme_button = ThemeToggleButton(self.controller, "windowAction", 30)
        header_layout.addWidget(self.theme_button)
        header_layout.addWidget(self.minimize_button)
        header_layout.addWidget(self.maximize_button)
        header_layout.addWidget(self.close_button)
        header_layout.addWidget(self.settings_button)

        self.page_title = QLabel("Dashboard")
        self.page_title.setObjectName("pageTitle")  # styled by shell_stylesheet()
        self.page_title.setContentsMargins(0, 2, 0, 0)

        # Dashboard only: "Good afternoon, <full name>" under the title.
        self.greeting = QLabel()
        self.greeting.setObjectName("pageGreeting")
        self.greeting.setContentsMargins(0, 0, 0, 2)
        self.greeting.hide()
        title_text = QVBoxLayout()
        title_text.setSpacing(2)
        title_text.addWidget(self.page_title)
        title_text.addWidget(self.greeting)

        title_row = QHBoxLayout()
        title_row.addLayout(title_text)
        title_row.addStretch()

        content_layout.addWidget(self.header)
        # Slim progress bar: visible whenever the app is waiting for the server.
        self.busy_bar = BusyBar()
        content_layout.addWidget(self.busy_bar)
        content_layout.addLayout(title_row)

        # Put the stacked pages inside a vertical scroll area.
        # This prevents large pages such as Dashboard, Analytics,
        # Forecasting, and DSS from being compressed into the viewport.
        self.page_scroll = QScrollArea()
        self.page_scroll.setObjectName("pageScroll")
        self.page_scroll.setWidgetResizable(True)
        # Safety net: a page wider than the window scrolls instead of clipping.
        self.page_scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.page_scroll.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )

        self.stack = CurrentPageStack()
        self.stack.setContentsMargins(0, 0, 0, 0)
        # Height comes only from _resize_current_page (viewport height, or the
        # current page's content height if taller). With a "Minimum" policy the
        # stack grew to its tallest page and table pages stopped scrolling.
        self.stack.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Ignored,
        )

        self.pages = {
            "dashboard": DashboardPage(self.controller),
            "properties": PropertiesPage(self.controller),
            "partners": PartnersPage(),
            "clients": ClientsPage(self.controller),
            "transactions": TransactionsPage(self.controller),
            "documents": DocumentsPage(self.controller),
            "media": MediaPage(self.controller),
            "agents": AgentsPage(self.controller),
            "workforce": WorkforcePage(self.controller),
            "analytics": AnalyticsPage(self.controller),
            "forecasting": ForecastingPage(self.controller),
            "dss": DssPage(self.controller),
            "users": UsersPage(self.controller),
            "audit": AuditPage(self.controller),
            "settings": SettingsPage(self.controller),
        }

        for key, page in self.pages.items():
            self.stack.addWidget(page)
            self.all_pages.append(page)
            # Long captions must wrap, otherwise their single-line width
            # becomes the page's minimum width and the page overflows.
            for label in page.findChildren(QLabel):
                if not label.wordWrap() and len(label.text()) > 24:
                    label.setWordWrap(True)

        self.page_scroll.setWidget(self.stack)
        content_layout.addWidget(self.page_scroll, 1)
        # "Loading Agents…" over the page when a load takes a moment.
        self.loading_overlay = LoadingOverlay(self.page_scroll, blur=self.stack)
        self.busy_indicators = BusyIndicators(self.busy_bar, self.loading_overlay, self)

        shell_layout.addWidget(self.sidebar)
        shell_layout.addWidget(content, 1)

        root_layout.addWidget(self.app_shell, 1)


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

        button.setText(tr(group_name))

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

        sidebar_width = 76 if getattr(self, "sidebar_collapsed", False) else max(
            220, min(260, int(width * 0.16))
        )
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
        toggle_maximized(self)
        self._update_maximize_icon()

    def _update_maximize_icon(self) -> None:
        maximized = self.controller.root.isMaximized()
        self.maximize_button.setIcon(qta.icon(
            "fa5.window-restore" if maximized else "fa5.window-maximize", color=TOKENS["text_muted"]
        ))

    def changeEvent(self, event) -> None:
        super().changeEvent(event)
        if hasattr(self, "maximize_button"):
            self._update_maximize_icon()

    def close_window(self) -> None:
        self.controller.root.close()

    def show_about(self) -> None:
        QMessageBox.about(
            self,
            "About",
            "Abellar Realty Management System\n"
            "Internal desktop management application.",
        )

    def _on_title_bar(self, event) -> bool:
        pos = self.header.mapFrom(self, event.position().toPoint())
        return self.header.rect().contains(pos) and is_drag_area(self.header, pos)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_title_bar(event):
            start_move(self)  # OS move: supports snap and dragging out of maximized
            return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self._on_title_bar(event):
            self.maximize_window()
            return
        super().mouseDoubleClickEvent(event)

    def refresh_status_chips(self) -> None:
        """Sync + alert indicators from real API data (no fabricated values)."""
        token = self.controller.session.state.token
        if not token:
            return
        with busy_tracker().labelled("Checking sync status…", quiet=True):
            self._refresh_status_chips(token)

    def _refresh_status_chips(self, token: str) -> None:
        try:
            sync = self.search_api.get_sync_status(token=token)
            pending = sum(counts.get("PENDING", 0) for counts in sync.get("counts", {}).values())
            if not sync.get("enabled"):
                text, ok, alert = "Local only", False, False
            elif pending:
                text, ok, alert = f"{pending} pending", False, False
            else:
                text, ok, alert = "Synced", True, False
        except Exception:
            text, ok, alert = "Offline", False, True
        self.sync_chip.setText(text)
        self.sync_chip.setIcon(qta.icon("fa5s.cloud" if not alert else "fa5s.exclamation-circle",
                                        color=TOKENS["success"] if ok else
                                        TOKENS["danger"] if alert else TOKENS["text_muted"]))
        self._set_chip_state(self.sync_chip, ok=ok, alert=alert)
        if not self.notification_panel.isVisible():
            self.notification_panel.load()  # updates the bell through ``changed``

    def _show_notification_count(self, data: dict) -> None:
        unread = [item for item in data.get("items", []) if not item.get("read")]
        urgent = any(item.get("severity") == "danger" for item in unread)
        self.alert_chip.setText(str(len(unread)))
        self.alert_chip.setToolTip(f"{tr('Notifications')}: {len(unread)} {tr('Unread').lower()}")
        self.alert_chip.setIcon(qta.icon("fa5s.bell", color=TOKENS["danger"] if urgent else
                                         TOKENS["accent"] if unread else TOKENS["text_muted"]))
        self._set_chip_state(self.alert_chip, ok=False, alert=urgent)

    def toggle_notifications(self) -> None:
        if self.notification_panel.isVisible():
            self.notification_panel.hide()
        else:
            self.notification_panel.show_under(self.alert_chip)

    def open_notification(self, item: dict) -> None:
        """Go to the page a notification is about (if this role can open it)."""
        page = item.get("page")
        permissions = self.controller.session.state.permissions
        if not page or (permissions and page not in permissions and page != "settings"):
            return
        if str(item.get("key", "")).startswith("document-failed:"):
            self.open_failed_documents()
        else:
            self.show_page(page)

    @staticmethod
    def _set_chip_state(chip, ok: bool, alert: bool) -> None:
        chip.setProperty("ok", "true" if ok else "false")
        chip.setProperty("alert", "true" if alert else "false")
        chip.style().unpolish(chip)
        chip.style().polish(chip)

    def open_failed_documents(self) -> None:
        self.show_page("documents")
        page = self.pages.get("documents")
        combo = getattr(page, "status_filter", None)
        if combo is not None:
            index = combo.findText("Failed")
            if index >= 0:
                combo.setCurrentIndex(index)

    def toggle_sidebar(self) -> None:
        """Collapse the sidebar to icons only (and back)."""
        self.sidebar_collapsed = not self.sidebar_collapsed
        collapsed = self.sidebar_collapsed
        for btn in self.nav_map.values():
            btn.setText("" if collapsed else btn.property("fullText"))
        for button in self.group_buttons.values():
            button.setVisible(not collapsed)
        for widget in (self.brand, self.brand_subtitle):
            widget.setVisible(not collapsed)
        self._apply_responsive_sidebar()

    def run_global_search(self) -> None:
        query = self.search_input.text().strip()
        if len(query) < 2:
            self.search_input.setFocus()
            self.search_input.setPlaceholderText(tr("Type at least 2 characters, then press Enter"))
            return
        token = self.controller.session.state.token
        permissions = set(self.controller.session.state.permissions)
        try:
            with busy_tracker().labelled(f"Searching for “{query}”…"):
                data = self.search_api.search(query, token=token)
            results = {
                group: [item for item in items if not permissions or item["page"] in permissions]
                for group, items in data.get("results", {}).items()
            }
        except Exception as exc:
            from app.api.client import error_message

            QMessageBox.warning(self, "Search failed", error_message(exc))
            return
        partners_page = self.pages.get("partners")
        partner_names = PARTNERS
        if partners_page is not None and (not permissions or "partners" in permissions):
            results["partners"] = [
                {"title": name, "subtitle": "Developer / partner", "page": "partners", "filter": name}
                for name in partner_names if query.casefold() in name.casefold()
            ]
        GlobalSearchDialog(query, results, self.open_search_result, self).exec()

    def open_search_result(self, page_key: str, filter_text: str) -> None:
        """Open the page and apply the result to that page's own filter."""
        self.show_page(page_key)
        page = self.pages.get(page_key)
        field = getattr(page, "search_input", None) or getattr(page, "search", None)
        if field is not None and hasattr(field, "setText"):
            field.setText(filter_text)
            if page_key == "audit":
                page.refresh()  # the audit page searches on the server

    def apply_session(self) -> None:
        """Show the signed-in user's real name/role and only permitted pages."""
        state = self.controller.session.state
        name = self.controller.session.user_name
        initials = "".join(part[0] for part in name.split()[:2]).upper() or "?"
        for label in (self.header_user,):
            label.setText(name)
        for label in (self.header_role,):
            label.setText(state.role)
        for avatar in (self.header_avatar,):
            avatar.setText(initials)
        self._update_greeting()
        self.refresh_status_chips()
        if not hasattr(self, "status_timer"):
            from PyQt6.QtCore import QTimer

            self.status_timer = QTimer(self)
            self.status_timer.setInterval(60_000)  # light: two small requests per minute
            self.status_timer.timeout.connect(self.refresh_status_chips)
        self.status_timer.start()
        allowed = set(state.permissions)
        for key, btn in self.nav_map.items():
            btn.setVisible(key in allowed)
        for group_name, content in self.group_contents.items():
            layout = content.layout()
            visible = any(
                layout.itemAt(index).widget() is not None
                and not layout.itemAt(index).widget().isHidden()
                for index in range(layout.count())
            ) if layout is not None else True
            if group_name in self.group_buttons:
                self.group_buttons[group_name].setVisible(visible)

    def _update_greeting(self) -> None:
        on_dashboard = getattr(self, "current_page", "dashboard") == "dashboard"
        self.greeting.setVisible(on_dashboard)
        if on_dashboard:
            hour = datetime.now().hour
            hello = tr("Good morning") if hour < 12 else tr("Good afternoon") if hour < 18 else tr("Good evening")
            today = datetime.now().strftime("%A, %B %d, %Y").replace(" 0", " ")
            self.greeting.setText(f"{hello}, {self.controller.session.user_name} · {today}")

    def refresh_account(self) -> None:
        """Re-read the signed-in account (name, role, permissions) from the
        server and update the header card, greeting and navigation — used
        after the account is edited in Users & Access."""
        state = self.controller.session.state
        if not state.token:
            return
        try:
            me = self.search_api.me(state.token)
        except Exception:
            return
        self.controller.session.set_session(
            token=state.token, user=me, role=me.get("role", state.role),
            permissions=me.get("permissions", state.permissions), branch_id=me.get("branch_id"),
        )
        self.apply_session()
        current = getattr(self, "current_page", "dashboard")
        if state.permissions and current not in state.permissions:
            self.show_page("dashboard")  # the new role can no longer open this page

    def show_page(self, key: str) -> None:
        if key not in self.pages:
            return
        # A page chosen while another is still loading opens right after it
        # (never a second load nested inside the first).
        if getattr(self, "_page_loading", False):
            self._pending_page = key
            return
        permissions = self.controller.session.state.permissions
        if permissions and key not in permissions:
            QMessageBox.information(self, "Access restricted", "Your role does not have access to this page.")
            return

        self.current_page = key
        self.stack.setCurrentWidget(self.pages[key])
        # Size the stack by the visible page only; otherwise every page is
        # stretched to the tallest page and its table stops scrolling.
        for other in self.pages.values():
            other.setSizePolicy(
                QSizePolicy.Policy.Preferred,
                QSizePolicy.Policy.Preferred if other is self.pages[key] else QSizePolicy.Policy.Ignored,
            )
        self.page_title.setText(self.page_title_for_key(key))
        self._update_greeting()
        page = self.pages[key]
        self._page_loading = True
        try:
            with busy_tracker().labelled(f"Loading {self.page_title_for_key(key)}…"):
                for loader in ("refresh", "load_agents", "load_clients", "load_transactions"):
                    if hasattr(page, loader):
                        getattr(page, loader)()
                        break
        finally:
            self._page_loading = False
        pending, self._pending_page = getattr(self, "_pending_page", None), None
        if pending and pending != key:
            from PyQt6.QtCore import QTimer

            QTimer.singleShot(0, lambda: self.show_page(pending))

        for nav_key, btn in self.nav_map.items():
            is_active = nav_key == key
            btn.setProperty("active", "true" if is_active else "false")
            btn.setIcon(qta.icon(
                NAV_ICONS.get(nav_key, "fa5s.circle"),
                color=TOKENS["accent_ink"] if is_active else TOKENS["text_muted"],
            ))
            btn.style().unpolish(btn)
            btn.style().polish(btn)
            btn.update()

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
        # Minimum (not preferred) height: a page only outgrows the window
        # when its essential content does not fit; otherwise its tables take
        # the remaining space and scroll inside themselves.
        content_height = max(page.minimumSizeHint().height(), page.minimumHeight())
        layout = page.layout()
        if layout is not None and layout.hasHeightForWidth():
            # Wrapped text: the real minimum depends on the available width.
            width = max(self.page_scroll.viewport().width(), page.minimumSizeHint().width())
            # Qt's height-for-width distribution squeezes rows below their
            # minimum unless the page gets its preferred height at this width.
            content_height = max(content_height, layout.heightForWidth(width))

        # Table pages fit the viewport (their tables scroll); pages whose
        # content is taller than the viewport scroll as a whole.
        target_height = max(viewport_height, content_height + 12)
        target_width = max(self.page_scroll.viewport().width(), page.minimumSizeHint().width())
        self.stack.setMinimumHeight(target_height)
        self.stack.resize(target_width, target_height)

    def page_title_for_key(self, key: str) -> str:
        mapping = {
            "dashboard": "Dashboard",
            "properties": "Property Operations",
            "partners": "Partners / Developers",
            "clients": "Buyers & Sellers",
            "transactions": "Transactions",
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

        return tr(mapping.get(key, "Dashboard"))
