"""Property card grid (visual alternative to the Properties table).

Cards show the same listing dictionaries the table uses; selecting a card
selects the listing, double-clicking opens the existing details dialog.
Photos are loaded asynchronously from the listing's own photo URLs.
"""

from __future__ import annotations

from typing import Any, Callable

import qtawesome as qta
from PyQt6.QtCore import QSize, Qt, QUrl, pyqtSignal
from PyQt6.QtGui import QPixmap
from PyQt6.QtNetwork import QNetworkAccessManager, QNetworkReply, QNetworkRequest
from PyQt6.QtWidgets import (
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.theme import BADGES, TOKENS as T, raw_set_stylesheet

CARD_MIN_WIDTH = 270
IMAGE_HEIGHT = 158

def card_style() -> str:
    return f"""/*alty-raw*/
QFrame#propertyCard {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: 14px; }}
QFrame#propertyCard:hover {{ border: 1px solid {T['border_strong']}; background: {T['card_2']}; }}
QFrame#propertyCard[selected="true"] {{ border: 1px solid {T['accent']}; }}
QLabel {{ background: transparent; border: none; }}
QLabel#cardImage {{ background: {T['card_2']}; border-radius: 10px; color: {T['text_faint']}; }}
QLabel#cardPrice {{ color: {T['accent']}; font-size: 16px; font-weight: 800; }}
QLabel#cardTitle {{ color: {T['text']}; font-size: 13px; font-weight: 700; }}
QLabel#cardMeta {{ color: {T['text_muted']}; font-size: 11px; }}
QLabel#cardFact {{ color: {T['text_muted']}; font-size: 11px; }}
"""


class _ImageLoader:
    """One shared network manager + in-memory cache for card photos."""

    def __init__(self) -> None:
        self.manager = QNetworkAccessManager()
        self.cache: dict[str, QPixmap] = {}

    def load(self, url: str, callback: Callable[[QPixmap], None]) -> None:
        if url in self.cache:
            callback(self.cache[url])
            return
        reply = self.manager.get(QNetworkRequest(QUrl(url)))

        def finished() -> None:
            if reply.error() == QNetworkReply.NetworkError.NoError:
                pixmap = QPixmap()
                if pixmap.loadFromData(bytes(reply.readAll())):
                    self.cache[url] = pixmap
                    callback(pixmap)
            reply.deleteLater()

        reply.finished.connect(finished)


_loader: _ImageLoader | None = None


def _image_loader() -> _ImageLoader:
    global _loader
    if _loader is None:
        _loader = _ImageLoader()
    return _loader


def _money(value: Any) -> str:
    try:
        return f"₱{float(value):,.0f}"
    except (TypeError, ValueError):
        return "Price not set"


class PropertyCard(QFrame):
    clicked = pyqtSignal(dict)
    double_clicked = pyqtSignal(dict)

    def __init__(self, listing: dict[str, Any]) -> None:
        super().__init__()
        self.listing = listing
        self.setObjectName("propertyCard")
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        raw_set_stylesheet(self, card_style())
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 12)
        layout.setSpacing(6)

        self.image = QLabel()
        self.image.setObjectName("cardImage")
        self.image.setFixedHeight(IMAGE_HEIGHT)
        self.image.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image.setPixmap(qta.icon("fa5s.home", color=T["text_faint"]).pixmap(QSize(38, 38)))
        layout.addWidget(self.image)

        status = str(listing.get("status") or "AVAILABLE").upper()
        text_color, background = BADGES.get(status, (T["text"], T["card_2"]))
        self.badge = QLabel(status.replace("_", " ").title(), self.image)
        raw_set_stylesheet(
            self.badge,
            f"background: {background}; color: {text_color}; border-radius: 8px; padding: 3px 9px; "
            "font-size: 10px; font-weight: 800;",
        )
        self.badge.adjustSize()
        self.badge.move(10, 10)

        price = QLabel(_money(listing.get("price_total")))
        price.setObjectName("cardPrice")
        title = QLabel(listing.get("title") or "Untitled property")
        title.setObjectName("cardTitle")
        title.setWordWrap(True)
        location_bits = [listing.get("village_name"), listing.get("category")]
        meta = QLabel(" · ".join(str(bit) for bit in location_bits if bit) or "Location not set")
        meta.setObjectName("cardMeta")
        meta.setWordWrap(True)
        layout.addWidget(price)
        layout.addWidget(title)
        layout.addWidget(meta)

        facts = QHBoxLayout()
        facts.setSpacing(12)
        for icon, value in (
            ("fa5s.bed", f"{listing.get('num_bedrooms') or 0} Beds"),
            ("fa5s.bath", f"{listing.get('num_bathrooms') or 0} Baths"),
            ("fa5s.car", f"{listing.get('garage_spaces') or 0} Garage"),
        ):
            fact = QHBoxLayout()
            fact.setSpacing(4)
            icon_label = QLabel()
            icon_label.setPixmap(qta.icon(icon, color=T["text_faint"]).pixmap(QSize(12, 12)))
            text = QLabel(value)
            text.setObjectName("cardFact")
            fact.addWidget(icon_label)
            fact.addWidget(text)
            facts.addLayout(fact)
        facts.addStretch()
        code = QLabel(str(listing.get("external_listing_id") or f"#{listing.get('listing_id')}"))
        code.setObjectName("cardFact")
        facts.addWidget(code)
        layout.addLayout(facts)

        photos = [url for url in (listing.get("photos") or []) if isinstance(url, str) and url.startswith("http")]
        if photos:
            _image_loader().load(photos[0], self._set_photo)

    def _set_photo(self, pixmap: QPixmap) -> None:
        if self.image is None:
            return
        target = QSize(max(self.image.width(), 240), IMAGE_HEIGHT)
        scaled = pixmap.scaled(target, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - target.width()) // 2)
        y = max(0, (scaled.height() - target.height()) // 2)
        self.image.setPixmap(scaled.copy(x, y, target.width(), target.height()))

    def set_selected(self, selected: bool) -> None:
        self.setProperty("selected", "true" if selected else "false")
        self.style().unpolish(self)
        self.style().polish(self)

    def mousePressEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit(self.listing)
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.double_clicked.emit(self.listing)
        super().mouseDoubleClickEvent(event)


class PropertyCardGrid(QScrollArea):
    """Responsive grid of PropertyCards (columns follow the width)."""

    listing_selected = pyqtSignal(dict)
    listing_opened = pyqtSignal(dict)

    def __init__(self) -> None:
        super().__init__()
        self.setWidgetResizable(True)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.container = QWidget()
        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(0, 0, 4, 0)
        self.grid.setHorizontalSpacing(14)
        self.grid.setVerticalSpacing(14)
        self.setWidget(self.container)
        self.cards: list[PropertyCard] = []
        self.empty = QLabel("No properties match the current filters.")
        raw_set_stylesheet(self.empty, f"color: {T['text_faint']}; padding: 30px; background: transparent;")
        self._columns = 0

    def set_listings(self, listings: list[dict[str, Any]]) -> None:
        for card in self.cards:
            card.deleteLater()
        self.cards = []
        for listing in listings:
            card = PropertyCard(listing)
            card.clicked.connect(self._select)
            card.double_clicked.connect(self.listing_opened.emit)
            self.cards.append(card)
        self._columns = 0
        self._reflow()

    def _select(self, listing: dict) -> None:
        for card in self.cards:
            card.set_selected(card.listing is listing)
        self.listing_selected.emit(listing)

    def _reflow(self) -> None:
        columns = max(1, self.viewport().width() // CARD_MIN_WIDTH)
        if columns == self._columns and self.grid.count():
            return
        self._columns = columns
        while self.grid.count():
            item = self.grid.takeAt(0)
            if item.widget() is not None and item.widget() is not self.empty:
                item.widget().setParent(self.container)
        for column in range(8):
            self.grid.setColumnStretch(column, 1 if column < columns else 0)
        self.empty.setVisible(not self.cards)
        if not self.cards:
            self.grid.addWidget(self.empty, 0, 0, 1, columns)
        for index, card in enumerate(self.cards):
            self.grid.addWidget(card, index // columns, index % columns)
        rows = (len(self.cards) + columns - 1) // columns
        for row in range(rows + 2):
            self.grid.setRowStretch(row, 0)
        self.grid.setRowStretch(rows, 1)  # cards keep their natural height

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        self._reflow()
