"""Notification panel opened from the bell in the main window header.

Shows what the API computes from the records (``GET /notifications``):
failed documents, recorded transactions, client reviews, new client
accounts, listings missing a map location and, for the Administrator,
synchronization and sign-in alerts. Clicking one marks it read and opens
the page it concerns.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

import qtawesome as qta
from PyQt6.QtCore import QPoint, QSize, Qt, pyqtSignal
from PyQt6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.i18n import tr
from app.theme import TOKENS as T, raw_set_stylesheet

PANEL_SIZE = QSize(420, 540)

CATEGORY_ICONS = {
    "documents": "fa5s.file-alt",
    "transactions": "fa5s.exchange-alt",
    "reviews": "fa5s.star",
    "clients": "fa5s.user-plus",
    "listings": "fa5s.map-marker-alt",
    "sync": "fa5s.cloud",
    "security": "fa5s.shield-alt",
}
SEVERITY_TOKENS = {
    "danger": ("danger", "danger_soft"),
    "warning": ("warning", "warning_soft"),
    "success": ("success", "success_soft"),
    "info": ("info", "info_soft"),
}


def time_ago(value: str | None) -> str:
    if not value:
        return ""
    try:
        moment = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return ""
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    seconds = max(0, int((datetime.now(timezone.utc) - moment).total_seconds()))
    if seconds < 60:
        return tr("just now")
    for size, unit in ((86400 * 7, "w"), (86400, "d"), (3600, "h"), (60, "m")):
        if seconds >= size:
            return f"{seconds // size}{unit} ago" if unit != "w" or seconds < 86400 * 35 \
                else moment.astimezone().strftime("%b %d, %Y")
    return ""


def panel_style() -> str:
    return f"""/*alty-raw*/
QFrame#notificationPanel {{ background: {T['card']}; border: 1px solid {T['border_strong']}; border-radius: 14px; }}
QLabel {{ background: transparent; border: none; }}
QLabel#panelTitle {{ color: {T['text']}; font-size: 15px; font-weight: 700; }}
QLabel#unreadPill {{ background: {T['accent']}; color: {T['accent_ink']}; border-radius: 9px;
    padding: 1px 8px; font-size: 11px; font-weight: 700; }}
QPushButton#linkButton {{ background: transparent; border: none; color: {T['accent']}; font-size: 12px;
    font-weight: 600; padding: 4px 2px; }}
QPushButton#linkButton:hover {{ color: {T['accent_hover']}; text-decoration: underline; }}
QPushButton#linkButton:disabled {{ color: {T['text_faint']}; text-decoration: none; }}
QPushButton#segment {{ background: transparent; color: {T['text_muted']}; border: none; border-radius: 8px;
    padding: 5px 12px; font-size: 12px; font-weight: 600; }}
QPushButton#segment:hover {{ color: {T['text']}; }}
QPushButton#segment:checked {{ background: {T['hover_2']}; color: {T['text']}; }}
QWidget#segments {{ background: {T['card_2']}; border: 1px solid {T['border']}; border-radius: 10px; }}
QScrollArea, QWidget#listBody {{ background: transparent; border: none; }}
QFrame#notificationRow {{ background: transparent; border: none; border-radius: 10px; }}
QFrame#notificationRow:hover {{ background: {T['hover']}; }}
QFrame#notificationRow[unread="true"] {{ background: {T['card_2']}; }}
QFrame#notificationRow[unread="true"]:hover {{ background: {T['hover']}; }}
QLabel#rowTitle {{ color: {T['text']}; font-size: 13px; font-weight: 600; }}
QLabel#rowMessage {{ color: {T['text_muted']}; font-size: 12px; }}
QLabel#rowTime {{ color: {T['text_faint']}; font-size: 11px; }}
QLabel#emptyTitle {{ color: {T['text']}; font-size: 14px; font-weight: 700; }}
QLabel#emptyText, QLabel#footerText {{ color: {T['text_faint']}; font-size: 11px; }}
QFrame#divider {{ background: {T['border']}; border: none; max-height: 1px; min-height: 1px; }}
QToolButton#refreshButton {{ background: transparent; border: none; border-radius: 7px; padding: 4px; }}
QToolButton#refreshButton:hover {{ background: {T['hover']}; }}
"""


class NotificationRow(QFrame):
    activated = pyqtSignal(dict)

    def __init__(self, item: dict[str, Any]) -> None:
        super().__init__()
        self.item = item
        self.setObjectName("notificationRow")
        self.setProperty("unread", "false" if item.get("read") else "true")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(12)

        color, background = SEVERITY_TOKENS.get(item.get("severity"), ("info", "info_soft"))
        icon = QLabel()
        icon.setFixedSize(36, 36)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        raw_set_stylesheet(icon, f"background: {T[background]}; border-radius: 10px;")
        icon.setPixmap(qta.icon(CATEGORY_ICONS.get(item.get("category"), "fa5s.bell"),
                                color=T[color]).pixmap(QSize(16, 16)))
        layout.addWidget(icon, 0, Qt.AlignmentFlag.AlignTop)

        text = QVBoxLayout()
        text.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(8)
        title = QLabel(item.get("title") or "")
        title.setObjectName("rowTitle")
        title.setWordWrap(True)
        top.addWidget(title, 1)
        when = QLabel(time_ago(item.get("created_at")))
        when.setObjectName("rowTime")
        top.addWidget(when, 0, Qt.AlignmentFlag.AlignTop)
        text.addLayout(top)
        message = QLabel(item.get("message") or "")
        message.setObjectName("rowMessage")
        message.setWordWrap(True)
        text.addWidget(message)
        layout.addLayout(text, 1)

        dot = QLabel()
        dot.setFixedSize(8, 8)
        raw_set_stylesheet(dot, f"background: {T['accent'] if not item.get('read') else 'transparent'};"
                                " border-radius: 4px;")
        layout.addWidget(dot, 0, Qt.AlignmentFlag.AlignTop)

    def mouseReleaseEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.activated.emit(self.item)
        super().mouseReleaseEvent(event)


class NotificationPanel(QFrame):
    """Popup list. ``load`` fetches; ``on_open_page`` navigates the main window."""

    changed = pyqtSignal(dict)  # latest {"items", "unread"} after any change

    def __init__(self, api, token_getter: Callable[[], str | None],
                 on_open_page: Callable[[dict], None], parent: QWidget | None = None) -> None:
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.api = api
        self.token_getter = token_getter
        self.on_open_page = on_open_page
        self.data: dict[str, Any] = {"items": [], "unread": 0}
        self.error = ""
        self.unread_only = False
        self.setObjectName("notificationPanel")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedSize(PANEL_SIZE)
        raw_set_stylesheet(self, panel_style())

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 10)
        layout.setSpacing(10)

        header = QHBoxLayout()
        title = QLabel(tr("Notifications"))
        title.setObjectName("panelTitle")
        header.addWidget(title)
        self.unread_pill = QLabel("0")
        self.unread_pill.setObjectName("unreadPill")
        header.addWidget(self.unread_pill)
        header.addStretch()
        self.mark_all = QPushButton(tr("Mark all as read"))
        self.mark_all.setObjectName("linkButton")
        self.mark_all.setCursor(Qt.CursorShape.PointingHandCursor)
        self.mark_all.clicked.connect(self.mark_all_read)
        header.addWidget(self.mark_all)
        layout.addLayout(header)

        segments = QWidget()
        segments.setObjectName("segments")
        segments.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        segment_layout = QHBoxLayout(segments)
        segment_layout.setContentsMargins(3, 3, 3, 3)
        segment_layout.setSpacing(2)
        self.segment_buttons = {}
        for key, label in (("all", tr("All")), ("unread", tr("Unread"))):
            button = QPushButton(label)
            button.setObjectName("segment")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda _checked, k=key: self.set_filter(k == "unread"))
            segment_layout.addWidget(button)
            self.segment_buttons[key] = button
        self.segment_buttons["all"].setChecked(True)
        segment_row = QHBoxLayout()
        segment_row.addWidget(segments)
        segment_row.addStretch()
        layout.addLayout(segment_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.body = QWidget()
        self.body.setObjectName("listBody")
        self.list_layout = QVBoxLayout(self.body)
        self.list_layout.setContentsMargins(0, 0, 4, 0)
        self.list_layout.setSpacing(4)
        self.scroll.setWidget(self.body)
        layout.addWidget(self.scroll, 1)

        divider = QFrame()
        divider.setObjectName("divider")
        layout.addWidget(divider)
        footer = QHBoxLayout()
        footer_text = QLabel(tr("Generated from system records"))
        footer_text.setObjectName("footerText")
        footer.addWidget(footer_text)
        footer.addStretch()
        refresh = QToolButton()
        refresh.setObjectName("refreshButton")
        refresh.setIcon(qta.icon("fa5s.sync-alt", color=T["text_muted"]))
        refresh.setToolTip(tr("Refresh"))
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.load)
        footer.addWidget(refresh)
        layout.addLayout(footer)

    # ---- data ----------------------------------------------------------
    def load(self) -> dict[str, Any]:
        token = self.token_getter()
        if not token:
            return self.data
        try:
            self.set_data(self.api.get_notifications(token=token))
            self.error = ""
        except Exception:
            self.error = tr("Could not load notifications")
            self.render()
        return self.data

    def set_data(self, data: dict[str, Any]) -> None:
        self.data = {"items": list(data.get("items", [])), "unread": int(data.get("unread", 0))}
        self.render()
        self.changed.emit(self.data)

    def mark_all_read(self) -> None:
        token = self.token_getter()
        if token and self.data["unread"]:
            try:
                self.set_data(self.api.mark_all_notifications_read(token=token))
            except Exception:
                pass

    def _activate(self, item: dict[str, Any]) -> None:
        token = self.token_getter()
        if token and not item.get("read"):
            try:
                self.set_data(self.api.mark_notifications_read([item["key"]], token=token))
            except Exception:
                pass
        self.hide()
        self.on_open_page(item)

    # ---- view ----------------------------------------------------------
    def set_filter(self, unread_only: bool) -> None:
        self.unread_only = unread_only
        self.segment_buttons["all"].setChecked(not unread_only)
        self.segment_buttons["unread"].setChecked(unread_only)
        self.render()

    def render(self) -> None:
        while self.list_layout.count():
            child = self.list_layout.takeAt(0).widget()
            if child is not None:
                child.deleteLater()
        unread = self.data["unread"]
        self.unread_pill.setText(str(unread))
        self.unread_pill.setVisible(unread > 0)
        self.mark_all.setEnabled(unread > 0)
        self.segment_buttons["unread"].setText(f"{tr('Unread')} ({unread})" if unread else tr("Unread"))
        items = [i for i in self.data["items"] if not (self.unread_only and i.get("read"))]
        if self.error or not items:
            self.list_layout.addWidget(self._empty_state())
        for item in items:
            row = NotificationRow(item)
            row.activated.connect(self._activate)
            self.list_layout.addWidget(row)
        self.list_layout.addStretch()

    def _empty_state(self) -> QWidget:
        box = QWidget()
        layout = QVBoxLayout(box)
        layout.setContentsMargins(20, 50, 20, 20)
        layout.setSpacing(8)
        icon = QLabel()
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setPixmap(qta.icon("fa5s.exclamation-circle" if self.error else "fa5s.check-circle",
                                color=T["danger"] if self.error else T["accent"]).pixmap(QSize(34, 34)))
        title = QLabel(self.error or tr("You're all caught up"))
        title.setObjectName("emptyTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        text = QLabel(tr("New alerts about documents, transactions, reviews and the system appear here."))
        text.setObjectName("emptyText")
        text.setWordWrap(True)
        text.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for widget in (icon, title, text):
            layout.addWidget(widget)
        box.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        return box

    def show_under(self, anchor: QWidget) -> None:
        """Open below ``anchor``, right-aligned with it, kept on screen."""
        point = anchor.mapToGlobal(QPoint(anchor.width() - self.width(), anchor.height() + 8))
        screen = anchor.screen().availableGeometry() if anchor.screen() else None
        if screen is not None:
            point.setX(max(screen.left() + 8, min(point.x(), screen.right() - self.width() - 8)))
        self.move(point)
        self.render()
        self.show()
        self.load()
