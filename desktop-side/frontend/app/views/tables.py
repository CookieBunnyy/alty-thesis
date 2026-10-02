"""Modern look for every table in the desktop app.

``modernize_table`` is applied by ``ui_polish`` to each table when it is
first shown, so pages keep building tables as before. It gives:

* one stylesheet (``theme.table_stylesheet``): white/charcoal rows with thin
  separators, no grid or zebra stripes, small uppercase header labels;
* comfortable row height (46 px) and left-aligned headers;
* ``ModernTableDelegate``: status-like columns (Status, Type, Role, …)
  become soft pills with a dot, and person columns (Name, Client, Agent, …)
  get an initials avatar. Other cells paint normally, so item colours set
  by pages still apply.
"""

from __future__ import annotations

import hashlib

from PyQt6.QtCore import QRectF, QSize, Qt
from PyQt6.QtGui import QColor, QFont, QFontMetrics, QPainter
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QStyle,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QTableWidget,
)

from app.theme import BADGES, TOKENS as T, raw_set_stylesheet, table_stylesheet

ROW_HEIGHT = 46
HEADER_HEIGHT = 42
PILL_COLUMNS = {
    "status", "sync", "sync status", "type", "transaction type", "role", "stage", "result",
    "severity", "priority", "source", "document type", "category", "availability", "state",
}
PERSON_COLUMNS = {
    "name", "full name", "client", "client name", "agent", "agent name", "buyer", "seller",
    "owner", "partner", "developer", "uploaded by", "actor", "user", "employee",
}
_AVATAR_TONES = (("accent", "accent_soft_2"), ("info", "info_soft"), ("success", "success_soft"),
                 ("warning", "warning_soft"), ("danger", "danger_soft"))


def _pretty(text: str) -> str:
    """RESERVED -> Reserved, ON_HOLD -> On hold; mixed-case text is kept."""
    if text.isupper() or "_" in text:
        words = text.replace("_", " ").strip()
        return words[:1].upper() + words[1:].lower()
    return text


def _initials(text: str) -> str:
    words = [w for w in text.replace(",", " ").split() if w[:1].isalpha()]
    return "".join(w[0] for w in words[:2]).upper()


class ModernTableDelegate(QStyledItemDelegate):
    def __init__(self, table: QTableView) -> None:
        super().__init__(table)
        self.table = table

    def _kind(self, column: int) -> str | None:
        model = self.table.model()
        header = model.headerData(column, Qt.Orientation.Horizontal, Qt.ItemDataRole.DisplayRole) if model else None
        name = " ".join(str(header or "").casefold().split())
        if name in PILL_COLUMNS:
            return "pill"
        if name in PERSON_COLUMNS:
            return "person"
        return None

    def sizeHint(self, option, index) -> QSize:
        size = super().sizeHint(option, index)
        extra = {"person": 38, "pill": 34}.get(self._kind(index.column()) or "", 0)
        return QSize(size.width() + extra, max(size.height(), ROW_HEIGHT))

    def paint(self, painter: QPainter, option, index) -> None:
        text = str(index.data(Qt.ItemDataRole.DisplayRole) or "").strip()
        kind = self._kind(index.column()) if text and text not in {"—", "-"} else None
        if kind == "person" and not _initials(text):
            kind = None
        if kind is None:
            super().paint(painter, option, index)
            return

        opt = QStyleOptionViewItem(option)
        self.initStyleOption(opt, index)
        opt.text = ""
        widget = opt.widget
        style = widget.style() if widget is not None else None
        if style is not None:  # row background, hover and selection from the stylesheet
            style.drawControl(QStyle.ControlElement.CE_ItemViewItem, opt, painter, widget)

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = option.rect.adjusted(12, 0, -8, 0)
        if kind == "pill":
            self._paint_pill(painter, rect, text, opt.font)
        else:
            self._paint_person(painter, rect, text, opt.font, index)
        painter.restore()

    @staticmethod
    def _paint_pill(painter: QPainter, rect, text: str, base: QFont) -> None:
        foreground, background = BADGES.get(text.upper().replace(" ", "_"), (T["text_muted"], T["hover"]))
        font = QFont(base)
        font.setPixelSize(12)
        font.setWeight(QFont.Weight.Medium)
        metrics = QFontMetrics(font)
        label = _pretty(text)
        max_text = max(20, rect.width() - 30)
        label = metrics.elidedText(label, Qt.TextElideMode.ElideRight, max_text)
        width = metrics.horizontalAdvance(label) + 30
        height = 24
        pill = QRectF(rect.left(), rect.center().y() - height / 2 + 0.5, width, height)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(background))
        painter.drawRoundedRect(pill, height / 2, height / 2)
        painter.setBrush(QColor(foreground))
        painter.drawEllipse(QRectF(pill.left() + 10, pill.center().y() - 3, 6, 6))
        painter.setFont(font)
        painter.setPen(QColor(foreground))
        painter.drawText(pill.adjusted(21, 0, -8, 0), Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, label)

    @staticmethod
    def _paint_person(painter: QPainter, rect, text: str, base: QFont, index) -> None:
        size = 28
        tone = _AVATAR_TONES[int(hashlib.md5(text.encode()).hexdigest(), 16) % len(_AVATAR_TONES)]
        circle = QRectF(rect.left(), rect.center().y() - size / 2 + 0.5, size, size)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor(T[tone[1]]))
        painter.drawEllipse(circle)
        initials_font = QFont(base)
        initials_font.setPixelSize(11)
        initials_font.setWeight(QFont.Weight.Bold)
        painter.setFont(initials_font)
        painter.setPen(QColor(T[tone[0]]))
        painter.drawText(circle, Qt.AlignmentFlag.AlignCenter, _initials(text))

        font = QFont(base)
        font.setWeight(QFont.Weight.Medium)
        painter.setFont(font)
        brush = index.data(Qt.ItemDataRole.ForegroundRole)
        painter.setPen(brush.color() if brush is not None and hasattr(brush, "color") else QColor(T["text"]))
        text_rect = rect.adjusted(size + 10, 0, 0, 0)
        shown = QFontMetrics(font).elidedText(text, Qt.TextElideMode.ElideRight, int(text_rect.width()))
        painter.drawText(text_rect, Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft, shown)


def _uppercase_headers(table: QTableView) -> None:
    """Small uppercase column labels (QSS cannot transform text)."""
    if not isinstance(table, QTableWidget) or table.property("_altyRelabelling"):
        return
    table.setProperty("_altyRelabelling", True)
    try:
        for column in range(table.columnCount()):
            item = table.horizontalHeaderItem(column)
            if item is not None and item.text() != item.text().upper():
                item.setText(item.text().upper())
    finally:
        table.setProperty("_altyRelabelling", False)


def modernize_table(table: QTableView) -> None:
    """Apply the modern table look once (idempotent)."""
    if table.property("_altyModern"):
        return
    table.setProperty("_altyModern", True)
    raw_set_stylesheet(table, table_stylesheet())
    table.setShowGrid(False)
    table.setAlternatingRowColors(False)
    table.setMouseTracking(True)  # row hover
    if table.selectionBehavior() == QAbstractItemView.SelectionBehavior.SelectItems:
        table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)

    vertical = table.verticalHeader()
    vertical.setVisible(False)
    # Rows sized to their contents (wrapped text) keep that; others get the roomier default.
    vertical.setDefaultSectionSize(max(vertical.defaultSectionSize(), ROW_HEIGHT))
    vertical.setMinimumSectionSize(ROW_HEIGHT - 6)

    header = table.horizontalHeader()
    header.setDefaultAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
    header.setFixedHeight(HEADER_HEIGHT)
    header.setHighlightSections(False)
    font = QFont(header.font())
    font.setPixelSize(11)
    font.setWeight(QFont.Weight.DemiBold)
    font.setLetterSpacing(QFont.SpacingType.AbsoluteSpacing, 0.6)
    header.setFont(font)
    _uppercase_headers(table)
    model = table.model()
    if model is not None:  # pages that relabel columns later keep the style
        model.headerDataChanged.connect(lambda *_: _uppercase_headers(table))

    if type(table.itemDelegate()) is QStyledItemDelegate:  # keep pages' own delegates
        table.setItemDelegate(ModernTableDelegate(table))
