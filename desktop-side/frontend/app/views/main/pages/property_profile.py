"""Property profile: a modern read-only view of one listing.

Opened from the Properties table (double-click) and the card grid. Shows
only what the listing record holds — photos, price terms, facts, features,
amenities, nearby places, location and record information — with "Not
provided" for empty values.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable

import qtawesome as qta
from PyQt6.QtCore import QPoint, QRect, QSize, Qt, QUrl
from PyQt6.QtGui import QDesktopServices, QPainter, QPainterPath, QPixmap
from PyQt6.QtWidgets import (
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLayout,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.theme import TOKENS as T, badge_colors, raw_set_stylesheet
from app.views.main.pages.property_cards import _image_loader

PHOTO_HEIGHT = 300
THUMB_SIZE = QSize(84, 60)
NOT_PROVIDED = "Not provided"

PLACE_LABELS = {
    "mall": "Malls", "malls": "Malls", "school": "Schools", "schools": "Schools",
    "hospital": "Hospitals", "hospitals": "Hospitals", "market": "Markets", "markets": "Markets",
    "church": "Churches", "churches": "Churches", "bank": "Banks", "banks": "Banks",
    "government_office": "Government offices", "government_offices": "Government offices",
    "transport_hub": "Transport hubs", "transport_hubs": "Transport hubs",
    "park": "Parks", "parks": "Parks", "restaurant": "Restaurants", "restaurants": "Restaurants",
    "other": "Other", "others": "Other",
}


def _style() -> str:
    return f"""/*alty-raw*/
QDialog {{ background: {T['bg']}; }}
QScrollArea, QWidget#profileBody {{ background: transparent; border: none; }}
QLabel {{ background: transparent; border: none; color: {T['text']}; }}
QFrame#card {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: 14px; }}
QLabel#photo {{ background: {T['card_2']}; border-radius: 12px; color: {T['text_faint']}; }}
QLabel#thumb {{ background: {T['card_2']}; border: 2px solid transparent; border-radius: 8px; }}
QLabel#thumb[active="true"] {{ border: 2px solid {T['accent']}; }}
QLabel#title {{ font-size: 22px; font-weight: 800; }}
QLabel#subtle {{ color: {T['text_muted']}; font-size: 12px; }}
QLabel#price {{ color: {T['accent']}; font-size: 26px; font-weight: 800; }}
QLabel#sectionTitle {{ color: {T['text_muted']}; font-size: 11px; font-weight: 700; letter-spacing: 1px; }}
QLabel#statValue {{ font-size: 15px; font-weight: 700; }}
QLabel#statLabel {{ color: {T['text_faint']}; font-size: 11px; }}
QLabel#fieldLabel {{ color: {T['text_faint']}; font-size: 12px; }}
QLabel#fieldValue {{ font-size: 13px; font-weight: 600; }}
QLabel#emptyValue {{ color: {T['text_faint']}; font-size: 13px; font-style: italic; }}
QLabel#body {{ color: {T['text_muted']}; font-size: 13px; }}
QLabel#chip {{ background: {T['card_2']}; border: 1px solid {T['border']}; border-radius: 12px;
    padding: 4px 10px; font-size: 12px; color: {T['text']}; }}
QLabel#featureOn {{ background: {T['accent_soft']}; border: 1px solid {T['accent_soft_2']}; border-radius: 12px;
    padding: 4px 10px; font-size: 12px; color: {T['accent']}; font-weight: 600; }}
QLabel#featureOff {{ background: transparent; border: 1px dashed {T['border']}; border-radius: 12px;
    padding: 4px 10px; font-size: 12px; color: {T['text_faint']}; }}
QPushButton {{ background: {T['hover']}; color: {T['text']}; border: 1px solid {T['border']};
    border-radius: 9px; padding: 8px 16px; font-weight: 600; }}
QPushButton:hover {{ background: {T['hover_2']}; }}
QPushButton#primary {{ background: {T['accent']}; color: {T['accent_ink']}; border-color: {T['accent']}; }}
QPushButton#primary:hover {{ background: {T['accent_hover']}; }}
QPushButton#link {{ background: transparent; border: none; color: {T['accent']}; padding: 2px 0; }}
QPushButton#link:hover {{ text-decoration: underline; }}
"""


def _money(value: Any) -> str | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return f"₱{number:,.2f}" if number else None


def _date(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%b %d, %Y %I:%M %p")
    except ValueError:
        return str(value)


def _rounded(pixmap: QPixmap, radius: int) -> QPixmap:
    """The pixmap with rounded corners (labels don't clip to border-radius)."""
    result = QPixmap(pixmap.size())
    result.fill(Qt.GlobalColor.transparent)
    painter = QPainter(result)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(0, 0, pixmap.width(), pixmap.height(), radius, radius)
    painter.setClipPath(path)
    painter.drawPixmap(0, 0, pixmap)
    painter.end()
    return result


def _label(text: str, name: str) -> QLabel:
    label = QLabel(text)
    label.setObjectName(name)
    return label


def _card(title: str | None = None, icon: str | None = None) -> tuple[QFrame, QVBoxLayout]:
    card = QFrame()
    card.setObjectName("card")
    layout = QVBoxLayout(card)
    layout.setContentsMargins(18, 16, 18, 16)
    layout.setSpacing(10)
    if title:
        row = QHBoxLayout()
        row.setSpacing(8)
        if icon:
            mark = QLabel()
            mark.setPixmap(qta.icon(icon, color=T["accent"]).pixmap(QSize(14, 14)))
            row.addWidget(mark)
        row.addWidget(_label(title.upper(), "sectionTitle"))
        row.addStretch()
        layout.addLayout(row)
    return card, layout


class _FlowLayout(QLayout):
    """Left-to-right layout that wraps its items onto new lines."""

    def __init__(self, parent: QWidget | None = None, spacing: int = 8) -> None:
        super().__init__(parent)
        self._items: list = []
        self._spacing = spacing
        self.setContentsMargins(0, 0, 0, 0)

    def addItem(self, item) -> None:  # noqa: N802 - Qt API
        self._items.append(item)

    def count(self) -> int:
        return len(self._items)

    def itemAt(self, index: int):  # noqa: N802
        return self._items[index] if 0 <= index < len(self._items) else None

    def takeAt(self, index: int):  # noqa: N802
        return self._items.pop(index) if 0 <= index < len(self._items) else None

    def expandingDirections(self):  # noqa: N802
        return Qt.Orientation(0)

    def hasHeightForWidth(self) -> bool:  # noqa: N802
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802
        return self._arrange(QRect(0, 0, width, 0), apply=False)

    def setGeometry(self, rect: QRect) -> None:  # noqa: N802
        super().setGeometry(rect)
        self._arrange(rect, apply=True)

    def sizeHint(self) -> QSize:  # noqa: N802
        return self.minimumSize()

    def minimumSize(self) -> QSize:  # noqa: N802
        size = QSize()
        for item in self._items:
            size = size.expandedTo(item.minimumSize())
        return size

    def _arrange(self, rect: QRect, apply: bool) -> int:
        x, y, line = rect.x(), rect.y(), 0
        for item in self._items:
            hint = item.sizeHint()
            if x + hint.width() > rect.right() + 1 and line:
                x, y, line = rect.x(), y + line + self._spacing, 0
            if apply:
                item.setGeometry(QRect(QPoint(x, y), hint))
            x += hint.width() + self._spacing
            line = max(line, hint.height())
        return y + line - rect.y()


class _FlowRow(QWidget):
    """Chips that wrap onto new lines."""

    def __init__(self, labels: list[QLabel]) -> None:
        super().__init__()
        flow = _FlowLayout(self)
        for label in labels:
            flow.addWidget(label)


class PropertyProfileDialog(QDialog):
    def __init__(self, listing: dict[str, Any], parent: QWidget | None = None,
                 category: str | None = None, status_label: str | None = None,
                 on_edit: Callable[[], None] | None = None) -> None:
        super().__init__(parent)
        self.listing = listing
        self.on_edit = on_edit
        self.photos = [str(p) for p in (listing.get("photos") or []) if p]
        self.current_photo = 0
        self.thumbs: list[QLabel] = []
        self.setWindowTitle(f"Property #{listing.get('listing_id')}")
        self.setMinimumSize(760, 600)
        self.resize(1000, 820)
        raw_set_stylesheet(self, _style())

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body = QWidget()
        body.setObjectName("profileBody")
        self.body = QVBoxLayout(body)
        self.body.setContentsMargins(22, 22, 22, 12)
        self.body.setSpacing(16)
        scroll.setWidget(body)
        outer.addWidget(scroll, 1)

        self._hero(category, status_label)
        self._terms_and_facts()
        self._description_and_features()
        self._nearby()
        self._location_and_record()
        self.body.addStretch()

        # Closed with the window's own ✕ (or Esc); no separate Close button.
        if on_edit is not None:
            footer = QHBoxLayout()
            footer.setContentsMargins(22, 10, 22, 16)
            footer.addStretch()
            edit = QPushButton(qta.icon("fa5s.pen", color=T["accent_ink"]), "Edit property")
            edit.setObjectName("primary")
            edit.clicked.connect(self._edit)
            footer.addWidget(edit)
            outer.addLayout(footer)

    # ---- sections ------------------------------------------------------
    def _hero(self, category: str | None, status_label: str | None) -> None:
        card, layout = _card()
        layout.setSpacing(14)

        self.photo = QLabel()
        self.photo.setObjectName("photo")
        self.photo.setFixedHeight(PHOTO_HEIGHT)
        self.photo.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Fixed)
        self.photo.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.photo.setPixmap(qta.icon("fa5s.home", color=T["text_faint"]).pixmap(QSize(56, 56)))
        if not self.photos:
            self.photo.setFixedHeight(150)
            self.photo.setText("")
        layout.addWidget(self.photo)
        self._pixmaps: dict[int, QPixmap] = {}
        if len(self.photos) > 1:
            strip = QHBoxLayout()
            strip.setSpacing(8)
            for index in range(len(self.photos)):
                thumb = QLabel()
                thumb.setObjectName("thumb")
                thumb.setFixedSize(THUMB_SIZE)
                thumb.setAlignment(Qt.AlignmentFlag.AlignCenter)
                thumb.setCursor(Qt.CursorShape.PointingHandCursor)
                thumb.mousePressEvent = lambda _e, i=index: self._show_photo(i)
                self.thumbs.append(thumb)
                strip.addWidget(thumb)
            strip.addStretch()
            layout.addLayout(strip)
        for index, url in enumerate(self.photos):
            _image_loader().load(url, lambda pixmap, i=index: self._photo_loaded(i, pixmap))

        top = QHBoxLayout()
        top.setSpacing(12)
        left = QVBoxLayout()
        left.setSpacing(6)
        badges = QHBoxLayout()
        badges.setSpacing(8)
        status = str(self.listing.get("status") or "").upper()
        if status:
            text, background = badge_colors(status)
            badge = QLabel(status_label or status.replace("_", " ").title())
            raw_set_stylesheet(badge, f"background: {background.name()}; color: {text.name()}; border-radius: 10px;"
                                      " padding: 3px 10px; font-size: 11px; font-weight: 700;")
            badges.addWidget(badge)
        badges.addWidget(_label(category or self.listing.get("category") or "Uncategorized", "chip"))
        if self.listing.get("layout_type"):
            badges.addWidget(_label(str(self.listing["layout_type"]), "chip"))
        badges.addStretch()
        left.addLayout(badges)
        title = _label(self.listing.get("title") or "Untitled property", "title")
        title.setWordWrap(True)
        left.addWidget(title)
        where = QHBoxLayout()
        where.setSpacing(6)
        pin = QLabel()
        pin.setPixmap(qta.icon("fa5s.map-marker-alt", color=T["text_muted"]).pixmap(QSize(12, 12)))
        where.addWidget(pin)
        where.addWidget(_label(self.listing.get("village_name") or "Location not provided", "subtle"))
        where.addStretch()
        left.addLayout(where)
        top.addLayout(left, 1)

        price_box = QVBoxLayout()
        price_box.setSpacing(0)
        price_box.addWidget(_label("TOTAL PRICE", "sectionTitle"), 0, Qt.AlignmentFlag.AlignRight)
        price_box.addWidget(_label(_money(self.listing.get("price_total")) or "Price not set", "price"),
                            0, Qt.AlignmentFlag.AlignRight)
        top.addLayout(price_box)
        layout.addLayout(top)
        self.body.addWidget(card)

    def _terms_and_facts(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        garage = self.listing.get("garage_spaces")
        tiles = [
            ("fa5s.hand-holding-usd", "Initial down payment", _money(self.listing.get("initial_dp"))),
            ("fa5s.calendar-alt", "Monthly rate", _money(self.listing.get("monthly_rate"))),
            ("fa5s.bed", "Bedrooms", self._count(self.listing.get("num_bedrooms"))),
            ("fa5s.bath", "Bathrooms", self._count(self.listing.get("num_bathrooms"))),
            ("fa5s.car", "Garage", f"{garage} space(s)" if self.listing.get("has_garage") and garage
             else "Yes" if self.listing.get("has_garage") else None),
        ]
        for icon, caption, value in tiles:
            card, layout = _card()
            layout.setContentsMargins(14, 12, 14, 12)
            layout.setSpacing(4)
            mark = QLabel()
            mark.setPixmap(qta.icon(icon, color=T["accent"]).pixmap(QSize(16, 16)))
            layout.addWidget(mark)
            layout.addWidget(_label(value or NOT_PROVIDED, "statValue" if value else "emptyValue"))
            layout.addWidget(_label(caption, "statLabel"))
            row.addWidget(card, 1)
        self.body.addLayout(row)

    def _description_and_features(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        about, about_layout = _card("About this property", "fa5s.align-left")
        details = str(self.listing.get("details") or "").strip()
        text = _label(details or "No description provided.", "body" if details else "emptyValue")
        text.setWordWrap(True)
        text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        about_layout.addWidget(text)
        about_layout.addStretch()
        row.addWidget(about, 3)

        features, features_layout = _card("Features & amenities", "fa5s.check-circle")
        flags = [("Balcony", "has_balcony"), ("Kitchen", "has_kitchen"), ("Backyard", "has_backyard"),
                 ("Garage", "has_garage")]
        features_layout.addWidget(_FlowRow(
            [_label(("✓ " if self.listing.get(key) else "") + name,
                    "featureOn" if self.listing.get(key) else "featureOff") for name, key in flags]))
        amenities = self.listing.get("amenity_list") or []
        if isinstance(amenities, dict):
            amenities = list(amenities.keys())
        if isinstance(amenities, str):
            amenities = [amenities]
        features_layout.addWidget(_label("Amenities", "fieldLabel"))
        if amenities:
            features_layout.addWidget(_FlowRow([_label(str(a), "chip") for a in amenities]))
        else:
            features_layout.addWidget(_label("No amenities listed", "emptyValue"))
        features_layout.addStretch()
        row.addWidget(features, 2)
        self.body.addLayout(row)

    def _nearby(self) -> None:
        groups: dict[str, list[str]] = {}
        establishments = self.listing.get("nearby_establishments") or {}
        if isinstance(establishments, dict):
            for key, entries in establishments.items():
                for entry in entries if isinstance(entries, list) else [entries]:
                    if isinstance(entry, dict) and entry.get("name"):
                        distance = entry.get("distance_km")
                        suffix = f" · {float(distance):g} km" if isinstance(distance, (int, float)) else ""
                        groups.setdefault(PLACE_LABELS.get(key, key.replace("_", " ").title()), []).append(
                            f"{entry['name']}{suffix}")
        if not groups:
            places = self.listing.get("nearby_places") or {}
            if isinstance(places, dict):
                for key, names in places.items():
                    for name in names if isinstance(names, list) else [names]:
                        if name:
                            groups.setdefault(PLACE_LABELS.get(key, key.replace("_", " ").title()), []).append(str(name))
            elif isinstance(places, list):
                groups["Nearby"] = [str(name) for name in places if name]
        card, layout = _card("Nearby places", "fa5s.map-signs")
        if not groups:
            layout.addWidget(_label("No nearby places recorded", "emptyValue"))
        else:
            grid = QGridLayout()
            grid.setHorizontalSpacing(24)
            grid.setVerticalSpacing(12)
            for index, (group, names) in enumerate(groups.items()):
                cell = QVBoxLayout()
                cell.setSpacing(4)
                cell.addWidget(_label(group, "fieldLabel"))
                for name in names:
                    value = _label(name, "fieldValue")
                    value.setWordWrap(True)
                    cell.addWidget(value)
                cell.addStretch()
                grid.addLayout(cell, index // 3, index % 3)
            for column in range(3):
                grid.setColumnStretch(column, 1)
            layout.addLayout(grid)
        self.body.addWidget(card)

    def _location_and_record(self) -> None:
        row = QHBoxLayout()
        row.setSpacing(12)
        location, location_layout = _card("Location", "fa5s.map-marker-alt")
        lat, lng = self.listing.get("lat"), self.listing.get("lng")
        self._fields(location_layout, [
            ("Village / project", self.listing.get("village_name")),
            ("Coordinates", f"{float(lat):.5f}, {float(lng):.5f}" if lat is not None and lng is not None else None),
        ])
        if lat is not None and lng is not None:
            link = QPushButton(qta.icon("fa5s.external-link-alt", color=T["accent"]), "Open in map")
            link.setObjectName("link")
            link.setCursor(Qt.CursorShape.PointingHandCursor)
            link.clicked.connect(lambda: QDesktopServices.openUrl(QUrl(
                f"https://www.openstreetmap.org/?mlat={lat}&mlon={lng}#map=17/{lat}/{lng}")))
            location_layout.addWidget(link, 0, Qt.AlignmentFlag.AlignLeft)
        else:
            location_layout.addWidget(_label("Without coordinates this listing does not appear on the website map.",
                                             "subtle"))
        location_layout.addStretch()
        row.addWidget(location, 1)

        record, record_layout = _card("Record", "fa5s.database")
        self._fields(record_layout, [
            ("Listing ID", self.listing.get("listing_id")),
            ("External ID", self.listing.get("external_listing_id")),
            ("Sync status", self.listing.get("sync_status")),
            ("Last synced", _date(self.listing.get("last_synced_at"))),
            ("Created", _date(self.listing.get("created_at"))),
            ("Updated", _date(self.listing.get("updated_at"))),
        ])
        record_layout.addStretch()
        row.addWidget(record, 1)
        self.body.addLayout(row)

    # ---- helpers -------------------------------------------------------
    @staticmethod
    def _count(value: Any) -> str | None:
        try:
            return str(int(value)) if value not in (None, "") else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _fields(layout: QVBoxLayout, rows: list[tuple[str, Any]]) -> None:
        grid = QGridLayout()
        grid.setHorizontalSpacing(16)
        grid.setVerticalSpacing(8)
        for index, (caption, value) in enumerate(rows):
            grid.addWidget(_label(caption, "fieldLabel"), index, 0, Qt.AlignmentFlag.AlignTop)
            shown = _label(str(value) if value not in (None, "") else NOT_PROVIDED,
                           "fieldValue" if value not in (None, "") else "emptyValue")
            shown.setWordWrap(True)
            shown.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(shown, index, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)

    def _photo_loaded(self, index: int, pixmap: QPixmap) -> None:
        self._pixmaps[index] = pixmap
        if index < len(self.thumbs):
            self.thumbs[index].setPixmap(_rounded(pixmap.scaled(
                THUMB_SIZE, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation).copy(0, 0, THUMB_SIZE.width(), THUMB_SIZE.height()), 6))
        if index == self.current_photo:
            self._show_photo(index)

    def _show_photo(self, index: int) -> None:
        self.current_photo = index
        for i, thumb in enumerate(self.thumbs):
            thumb.setProperty("active", "true" if i == index else "false")
            thumb.style().unpolish(thumb)
            thumb.style().polish(thumb)
        pixmap = self._pixmaps.get(index)
        if pixmap is None:
            return
        width = max(self.photo.width(), 400)
        scaled = pixmap.scaled(QSize(width, PHOTO_HEIGHT), Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                               Qt.TransformationMode.SmoothTransformation)
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - PHOTO_HEIGHT) // 2)
        self.photo.setPixmap(_rounded(scaled.copy(x, y, width, PHOTO_HEIGHT), 12))

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._pixmaps:
            self._show_photo(self.current_photo)

    def _edit(self) -> None:
        self.accept()
        if self.on_edit is not None:
            self.on_edit()
