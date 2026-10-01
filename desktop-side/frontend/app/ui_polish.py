"""Application-wide dialog and icon polish.

Installed once in ``main.py``. An event filter handles every top-level
window when it is first shown, so individual dialogs need no changes:

* QMessageBox: the active theme (light or dark), a type-specific icon,
  icons on buttons.
* QDialog: never larger than the screen — content taller than the screen is
  wrapped in a scroll area, and the window is kept inside the visible area.
* Any button without an icon gets one chosen from its text.

Icons come from qtawesome (Font Awesome 5, plus Material Design fallbacks).
"""

from __future__ import annotations

import re

import qtawesome as qta
from PyQt6.QtCore import QEvent, QObject, QSize, Qt, QTimer
from PyQt6.QtGui import QGuiApplication
from PyQt6.QtWidgets import (
    QAbstractButton,
    QAbstractItemView,
    QHeaderView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QTableView,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

SCREEN_FRACTION = 0.9
MAX_MESSAGE_LINES = 22

DIALOG_SCROLL_STYLE = (
    "QScrollArea#dialogScroll { background: transparent; border: none; }"
    "QWidget#dialogContent { background: transparent; }"
)

# (icon name, colour token) per message box type.
MESSAGE_ICONS = {
    QMessageBox.Icon.Information: ("fa5s.info-circle", "info"),
    QMessageBox.Icon.Warning: ("fa5s.exclamation-triangle", "warning"),
    QMessageBox.Icon.Critical: ("fa5s.times-circle", "danger"),
    QMessageBox.Icon.Question: ("fa5s.question-circle", "accent"),
    QMessageBox.Icon.NoIcon: ("fa5s.comment-alt", "accent"),
}

STANDARD_BUTTON_ICONS = {
    QMessageBox.StandardButton.Ok: "fa5s.check",
    QMessageBox.StandardButton.Yes: "fa5s.check",
    QMessageBox.StandardButton.YesToAll: "fa5s.check-double",
    QMessageBox.StandardButton.No: "fa5s.times",
    QMessageBox.StandardButton.NoToAll: "fa5s.times",
    QMessageBox.StandardButton.Cancel: "fa5s.ban",
    QMessageBox.StandardButton.Close: "fa5s.times-circle",
    QMessageBox.StandardButton.Save: "fa5s.save",
    QMessageBox.StandardButton.Discard: "fa5s.trash-alt",
    QMessageBox.StandardButton.Apply: "fa5s.check",
    QMessageBox.StandardButton.Retry: "fa5s.redo",
    QMessageBox.StandardButton.Ignore: "fa5s.forward",
    QMessageBox.StandardButton.Abort: "fa5s.stop-circle",
    QMessageBox.StandardButton.Help: "fa5s.question",
    QMessageBox.StandardButton.Reset: "fa5s.undo",
    QMessageBox.StandardButton.Open: "fa5s.folder-open",
}

# First matching keyword (checked against the button text) wins.
TEXT_ICONS = [
    (r"sign ?in|log ?in", "fa5s.sign-in-alt"),
    (r"sign ?up|register|create account", "fa5s.user-plus"),
    (r"log ?out|sign ?out", "fa5s.sign-out-alt"),
    (r"new user|add user", "fa5s.user-plus"),
    (r"reset password|password", "fa5s.key"),
    (r"reprocess", "fa5s.redo"),
    (r"refresh|reload", "fa5s.sync-alt"),
    (r"push|upload", "fa5s.cloud-upload-alt"),
    (r"sync", "fa5s.cloud-download-alt"),
    (r"download|save as", "fa5s.download"),
    (r"save", "fa5s.save"),
    (r"delete|remove", "fa5s.trash-alt"),
    (r"edit|rename|update", "fa5s.edit"),
    (r"preview|view|profile|details|open", "fa5s.eye"),
    (r"print", "fa5s.print"),
    (r"archive", "fa5s.archive"),
    (r"restore|undo", "fa5s.undo"),
    (r"history|version", "fa5s.history"),
    (r"report|audit|log", "fa5s.clipboard-list"),
    (r"move|folder", "fa5s.folder-open"),
    (r"browse|choose", "fa5s.folder-open"),
    (r"search|find", "fa5s.search"),
    (r"filter", "fa5s.filter"),
    (r"export", "fa5s.file-export"),
    (r"import", "fa5s.file-import"),
    (r"image|photo|media", "fa5s.images"),
    (r"map", "fa5s.map-marked-alt"),
    (r"add|new|create", "fa5s.plus"),
    (r"submit|confirm|ok|yes|apply|done", "fa5s.check"),
    (r"cancel|no\b", "fa5s.ban"),
    (r"close", "fa5s.times-circle"),
    (r"back|previous", "fa5s.arrow-left"),
    (r"next|continue", "fa5s.arrow-right"),
    (r"settings", "fa5s.cog"),
    (r"help|about", "fa5s.question-circle"),
]


def icon_for_text(text: str) -> str | None:
    label = re.sub(r"[^a-z ]", " ", text.casefold()).strip()
    if not label:
        return None
    for pattern, icon in TEXT_ICONS:
        if re.search(rf"\b(?:{pattern})", label):
            return icon
    return None


def _button_icon_color(button: QAbstractButton) -> str:
    """Ink on accent (primary) buttons, the text colour elsewhere."""
    from app.theme import TOKENS

    style = (button.styleSheet() or "").replace(" ", "").casefold()
    accent = TOKENS["accent"].casefold()
    if button.objectName() == "primaryAction" or f"background:{accent}" in style \
            or f"background-color:{accent}" in style:
        return TOKENS["accent_ink"]
    return TOKENS["text"]


def _text_color() -> str:
    from app.theme import TOKENS

    return TOKENS["text"]


def add_button_icons(root: QWidget) -> None:
    for button in root.findChildren(QAbstractButton):
        if isinstance(button, QToolButton) and button.icon().isNull() and not button.text():
            continue  # icon-only tool buttons set their own
        if not button.icon().isNull() or not isinstance(button, (QPushButton, QToolButton)):
            continue
        name = icon_for_text(button.text())
        if name:
            button.setIcon(qta.icon(name, color=_button_icon_color(button)))
            if button.iconSize().width() < 14:
                button.setIconSize(QSize(14, 14))


MAX_COLUMN_WIDTH = 360
MIN_COLUMN_WIDTH = 70


def make_table_scrollable(table: QTableView) -> None:
    """Scroll up/down and side to side: columns size to their contents
    (capped), so a table wider than its area gets a horizontal scrollbar
    instead of squeezing or cutting off columns."""
    if table.property("_altyScrollable"):
        return
    table.setProperty("_altyScrollable", True)
    table.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
    table.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setHorizontalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
    table.setSizeAdjustPolicy(QAbstractItemView.SizeAdjustPolicy.AdjustIgnored)
    header = table.horizontalHeader()
    header.setMinimumSectionSize(MIN_COLUMN_WIDTH)
    header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)  # user can drag widths
    header.setStretchLastSection(True)  # fill spare room when the table is narrower
    header.setTextElideMode(Qt.TextElideMode.ElideRight)

    timer = QTimer(table)
    timer.setSingleShot(True)
    timer.setInterval(0)

    def fit_columns() -> None:
        model = table.model()
        if model is None:
            return
        table.resizeColumnsToContents()
        for column in range(model.columnCount()):
            width = table.columnWidth(column)
            table.setColumnWidth(column, max(MIN_COLUMN_WIDTH, min(width + 16, MAX_COLUMN_WIDTH)))

    timer.timeout.connect(fit_columns)
    model = table.model()
    if model is not None:
        for signal in (model.rowsInserted, model.modelReset, model.dataChanged, model.layoutChanged):
            signal.connect(lambda *_: timer.start())
    timer.start()


def make_tables_scrollable(root: QWidget) -> None:
    for table in root.findChildren(QTableView):
        make_table_scrollable(table)


def polish_message_box(box: QMessageBox) -> None:
    # The box's own stylesheet overrides the transparent rules that the main
    # window and pages set on their QWidget descendants.
    from app.theme import TOKENS, message_box_stylesheet, raw_set_stylesheet

    raw_set_stylesheet(box, message_box_stylesheet())
    # Very long messages would push the box past the screen: show the start
    # and move the full text into the scrollable "Show Details" area.
    lines = box.text().splitlines()
    if len(lines) > MAX_MESSAGE_LINES and not box.detailedText():
        box.setDetailedText(box.text())
        shown = "\n".join(lines[:MAX_MESSAGE_LINES])
        box.setText(shown + "\n… (see Show Details for the full text)")
    name, token = MESSAGE_ICONS.get(box.icon(), MESSAGE_ICONS[QMessageBox.Icon.NoIcon])
    color = TOKENS[token]
    box.setIconPixmap(qta.icon(name, color=color).pixmap(QSize(40, 40)))
    box.setWindowIcon(qta.icon(name, color=color))
    for button in box.buttons():
        icon = STANDARD_BUTTON_ICONS.get(box.standardButton(button))
        if icon:
            default = button is box.defaultButton()
            button.setIcon(qta.icon(icon, color=TOKENS["accent_ink"] if default else TOKENS["text"]))


def _available_geometry(widget: QWidget):
    screen = widget.screen() or QGuiApplication.primaryScreen()
    return screen.availableGeometry() if screen else None


def fit_to_screen(dialog: QDialog) -> None:
    """Keep the dialog inside the screen; scroll its content if too tall."""
    area = _available_geometry(dialog)
    if area is None:
        return
    max_w = int(area.width() * SCREEN_FRACTION)
    max_h = int(area.height() * SCREEN_FRACTION)
    hint = dialog.sizeHint().expandedTo(dialog.minimumSizeHint())

    if (hint.height() > max_h or hint.width() > max_w) and not dialog.property("_altyScroll"):
        layout = dialog.layout()
        if layout is not None:
            content = QWidget()
            content.setObjectName("dialogContent")
            content.setLayout(layout)  # moves the layout and its widgets
            scroll = QScrollArea()
            scroll.setObjectName("dialogScroll")
            scroll.setWidgetResizable(True)
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
            scroll.setStyleSheet(DIALOG_SCROLL_STYLE)
            scroll.setWidget(content)
            wrapper = QVBoxLayout(dialog)
            wrapper.setContentsMargins(0, 0, 0, 0)
            wrapper.addWidget(scroll)
            dialog.setProperty("_altyScroll", True)
            bar = scroll.verticalScrollBar().sizeHint().width()
            width = min(max_w, max(dialog.minimumWidth(), content.sizeHint().width() + bar + 4))
            dialog.setMinimumSize(min(dialog.minimumWidth(), max_w), 0)
            dialog.resize(width, min(max_h, content.sizeHint().height() + 4))

    # Clamp size and position into the visible screen area.
    width = min(dialog.width(), max_w)
    height = min(dialog.height(), max_h)
    if dialog.minimumHeight() > max_h:
        dialog.setMinimumHeight(max_h)
    if dialog.minimumWidth() > max_w:
        dialog.setMinimumWidth(max_w)
    dialog.resize(width, height)
    frame = dialog.frameGeometry()
    x = min(max(frame.x(), area.left()), area.right() - frame.width())
    y = min(max(frame.y(), area.top()), area.bottom() - frame.height())
    if (x, y) != (frame.x(), frame.y()):
        dialog.move(max(area.left(), x), max(area.top(), y))


class UiPolisher(QObject):
    def eventFilter(self, obj: QObject, event: QEvent) -> bool:
        if event.type() == QEvent.Type.Show and isinstance(obj, QWidget) and obj.isWindow():
            try:
                if isinstance(obj, QMessageBox):
                    polish_message_box(obj)
                elif isinstance(obj, QFileDialog):
                    pass  # native dialog
                elif isinstance(obj, QDialog):
                    add_button_icons(obj)
                    make_tables_scrollable(obj)
                    for box in obj.findChildren(QDialogButtonBox):
                        for button in box.buttons():
                            icon = STANDARD_BUTTON_ICONS.get(box.standardButton(button))
                            if icon and button.icon().isNull():
                                button.setIcon(qta.icon(icon, color=_text_color()))
                    fit_to_screen(obj)
                else:
                    add_button_icons(obj)
                    make_tables_scrollable(obj)
            except Exception:  # polish must never break a dialog
                pass
        return False


def install(app: QApplication) -> UiPolisher:
    app.setWindowIcon(qta.icon("fa5s.building", color="#486b2a"))
    polisher = UiPolisher(app)
    app.installEventFilter(polisher)
    return polisher
