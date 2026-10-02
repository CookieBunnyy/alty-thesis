from __future__ import annotations

from typing import Any

import httpx

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor, QDoubleValidator, QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QStackedWidget,
    QScrollArea,
    QSizePolicy,
    QSpinBox,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

import qtawesome as qta

from app.theme import badge_colors
from app.api.client import ApiClient
from app.theme import TOKENS
from app.views.main.pages.property_cards import PropertyCardGrid

# Standard property categories (same list as the website:
# website-side/frontend/src/lib/categories.ts). Older free-text values are
# mapped onto them when a listing is edited.
PROPERTY_CATEGORIES = [
    "Condominium", "House and Lot", "Townhouse", "Duplex",
    "Apartment", "Lot Only", "Commercial", "Warehouse / Industrial",
]
_CATEGORY_ALIASES = {
    "Condominium": ("condo", "condominium", "condo unit", "studio", "loft"),
    "House and Lot": ("house", "house and lot", "house & lot", "single detached", "single-detached",
                      "villa", "bungalow"),
    "Townhouse": ("townhouse", "town house", "rowhouse", "row house"),
    "Duplex": ("duplex", "semi-detached", "semi detached"),
    "Apartment": ("apartment", "apartment unit", "flat"),
    "Lot Only": ("lot", "lot only", "vacant lot", "residential lot", "land"),
    "Commercial": ("commercial", "commercial space", "office", "office space", "retail", "shop"),
    "Warehouse / Industrial": ("warehouse", "industrial", "storage", "warehouse / industrial"),
}


def standard_category(value: str | None) -> str:
    """The standard category for a stored value, or the value itself."""
    text = " ".join(str(value or "").split())
    lowered = text.casefold()
    for label, aliases in _CATEGORY_ALIASES.items():
        if lowered == label.casefold() or lowered in aliases:
            return label
    return text


PROPERTY_STATUSES = [
    ("Available", "AVAILABLE", "#e5efdc"),
    ("Reserved", "RESERVED", "#e4eff7"),
    ("Sold", "SOLD", "#eef0ed"),
    ("On Hold", "ON_HOLD", "#fff3cd"),
    ("Unavailable", "UNAVAILABLE", "#f8dedc"),
]



def _chip_style() -> str:
    t = TOKENS
    return (
        "/*alty-raw*/"
        f"QPushButton {{ background: {t['card']}; color: {t['text_muted']}; border: 1px solid {t['border']};"
        " border-radius: 15px; padding: 6px 14px; font-weight: 600; }"
        f"QPushButton:hover {{ color: {t['text']}; border-color: {t['border_strong']}; }}"
        f"QPushButton:checked {{ background: {t['accent']}; color: {t['accent_ink']}; border-color: {t['accent']}; }}"
    )


class DynamicStringList(QWidget):
    def __init__(self, title: str, placeholder: str) -> None:
        super().__init__()
        self.items: list[str] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)

        title_label = QLabel(title)
        title_label.setStyleSheet("font-weight: 600; color: #17310a;")
        layout.addWidget(title_label)

        input_row = QHBoxLayout()
        self.input = QLineEdit()
        self.input.setPlaceholderText(placeholder)
        self.input.returnPressed.connect(self.add_item)
        add_button = QPushButton("Add")
        add_button.setIcon(qta.icon("fa5s.plus", color="#486b2a"))
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.add_item)
        input_row.addWidget(self.input, 1)
        input_row.addWidget(add_button)
        layout.addLayout(input_row)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #9b3030; font-size: 11px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.items_layout = QVBoxLayout()
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(3)
        layout.addLayout(self.items_layout)

    def add_item(self) -> None:
        value = self.input.text().strip()
        if not value:
            return
        if any(item.casefold() == value.casefold() for item in self.items):
            self.error_label.setText("This item has already been added.")
            return

        self.error_label.clear()
        self.items.append(value)
        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 0, 0)
        row_layout.setSpacing(8)
        item_label = QLabel(value)
        item_label.setWordWrap(True)
        remove_button = QPushButton("Remove")
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.setIcon(qta.icon("fa5s.trash-alt", color="#65745b"))
        remove_button.clicked.connect(lambda: self.remove_item(value, row))
        row_layout.addWidget(item_label, 1)
        row_layout.addWidget(remove_button)
        self.items_layout.addWidget(row)
        self.input.clear()

    def remove_item(self, value: str, row: QWidget) -> None:
        self.items = [item for item in self.items if item != value]
        self.items_layout.removeWidget(row)
        row.deleteLater()
        self.error_label.clear()

    def values(self) -> list[str]:
        return list(self.items)


class NearbyPlacesList(QWidget):
    PLACE_TYPES = {
        "Mall": "mall",
        "School": "school",
        "Hospital": "hospital",
        "Market": "market",
        "Church": "church",
        "Bank": "bank",
        "Government Office": "government_office",
        "Transport Hub": "transport_hub",
        "Park": "park",
        "Restaurant": "restaurant",
        "Other": "other",
    }

    changed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self.entries: list[tuple[str, str]] = []
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("Nearby Places")
        title.setStyleSheet("font-weight: 600; color: #17310a;")
        layout.addWidget(title)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.type_input = QComboBox()
        self.type_input.addItems(self.PLACE_TYPES.keys())
        self.type_input.setMinimumWidth(105)
        self.type_input.setCursor(Qt.CursorShape.PointingHandCursor)

        self.name_input = QLineEdit()
        self.name_input.setPlaceholderText("Place name")
        self.name_input.returnPressed.connect(self.add_item)

        add_button = QPushButton("Add")
        add_button.setIcon(qta.icon("fa5s.plus", color="#486b2a"))
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.add_item)

        input_row.addWidget(self.type_input)
        input_row.addWidget(self.name_input, 1)
        input_row.addWidget(add_button)
        layout.addLayout(input_row)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #9b3030; font-size: 11px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.items_layout = QVBoxLayout()
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(2)
        layout.addLayout(self.items_layout)

    def add_item(self) -> None:
        name = self.name_input.text().strip()
        if not name:
            self.error_label.setText("Enter a place name.")
            return

        place_type = self.type_input.currentText()
        if any(
            kind == place_type and value.casefold() == name.casefold()
            for kind, value in self.entries
        ):
            self.error_label.setText(
                "This place has already been added for this type."
            )
            return

        self.error_label.clear()
        self.entries.append((place_type, name))

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 0, 0)
        row_layout.setSpacing(6)

        type_label = QLabel(place_type)
        type_label.setMinimumWidth(105)
        type_label.setStyleSheet("color: #65745b;")

        name_label = QLabel(name)
        name_label.setWordWrap(True)

        remove_button = QPushButton("Remove")
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.setIcon(qta.icon("fa5s.trash-alt", color="#65745b"))
        remove_button.clicked.connect(
            lambda: self.remove_item(place_type, name, row)
        )

        row_layout.addWidget(type_label)
        row_layout.addWidget(name_label, 1)
        row_layout.addWidget(remove_button)
        self.items_layout.addWidget(row)

        self.name_input.clear()
        self.changed.emit()

    def remove_item(self, place_type: str, name: str, row: QWidget) -> None:
        self.entries = [
            entry for entry in self.entries
            if entry != (place_type, name)
        ]
        self.items_layout.removeWidget(row)
        row.deleteLater()
        self.error_label.clear()
        self.changed.emit()

    def values(self) -> dict[str, str | list[str]]:
        grouped: dict[str, list[str]] = {}
        for place_type, name in self.entries:
            key = self.PLACE_TYPES[place_type]
            grouped.setdefault(key, []).append(name)
        return {
            key: names[0] if len(names) == 1 else names
            for key, names in grouped.items()
        }

    def place_options(self) -> list[tuple[str, str, str]]:
        return [
            (name, place_type, self.PLACE_TYPES[place_type])
            for place_type, name in self.entries
        ]


class NearbyEstablishmentsList(QWidget):
    def __init__(self, places_source: NearbyPlacesList | None = None) -> None:
        super().__init__()
        self.places_source = places_source
        self.entries: list[tuple[str, str, float]] = []

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        title = QLabel("Nearby Establishments")
        title.setStyleSheet("font-weight: 600; color: #17310a;")
        layout.addWidget(title)

        input_row = QHBoxLayout()
        input_row.setSpacing(6)

        self.place_input = QComboBox()
        self.place_input.setMinimumWidth(160)
        self.place_input.setCursor(Qt.CursorShape.PointingHandCursor)

        self.distance_input = QDoubleSpinBox()
        self.distance_input.setRange(0, 9999)
        self.distance_input.setDecimals(1)
        self.distance_input.setSuffix(" km")
        self.distance_input.setCursor(Qt.CursorShape.ArrowCursor)
        self.distance_input.setMinimumWidth(85)

        add_button = QPushButton("Add")
        add_button.setIcon(qta.icon("fa5s.plus", color="#486b2a"))
        add_button.setCursor(Qt.CursorShape.PointingHandCursor)
        add_button.clicked.connect(self.add_item)
        self.add_button = add_button

        input_row.addWidget(self.place_input, 1)
        input_row.addWidget(self.distance_input)
        input_row.addWidget(add_button)
        layout.addLayout(input_row)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #9b3030; font-size: 11px;")
        self.error_label.setWordWrap(True)
        layout.addWidget(self.error_label)

        self.items_layout = QVBoxLayout()
        self.items_layout.setContentsMargins(0, 0, 0, 0)
        self.items_layout.setSpacing(2)
        layout.addLayout(self.items_layout)

        self.refresh_places()

    def refresh_places(self) -> None:
        current_name = self.place_input.currentText()
        self.place_input.blockSignals(True)
        self.place_input.clear()

        options = self.places_source.place_options() if self.places_source else []

        if not options:
            self.place_input.addItem("Add Nearby Places first")
            self.place_input.setEnabled(False)
            self.add_button.setEnabled(False)
        else:
            self.place_input.setEnabled(True)
            self.add_button.setEnabled(True)
            for name, type_label, type_key in options:
                self.place_input.addItem(
                    name,
                    (type_label, type_key, name),
                )
            if current_name:
                index = self.place_input.findText(current_name)
                if index >= 0:
                    self.place_input.setCurrentIndex(index)

        self.place_input.blockSignals(False)

    def add_item(self) -> None:
        data = self.place_input.currentData()
        if not data:
            self.error_label.setText("Add a Nearby Place first.")
            return

        _type_label, type_key, name = data
        distance = float(self.distance_input.value())

        if any(
            entry_name.casefold() == name.casefold()
            for _key, entry_name, _distance in self.entries
        ):
            self.error_label.setText("This place has already been added.")
            return

        self.entries.append((type_key, name, distance))
        self.error_label.clear()

        row = QWidget()
        row_layout = QHBoxLayout(row)
        row_layout.setContentsMargins(4, 0, 0, 0)
        row_layout.setSpacing(6)

        name_label = QLabel(name)
        name_label.setWordWrap(True)

        distance_label = QLabel(f"{distance:.1f} km")
        distance_label.setMinimumWidth(58)
        distance_label.setAlignment(
            Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )

        remove_button = QPushButton("Remove")
        remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        remove_button.setIcon(qta.icon("fa5s.trash-alt", color="#65745b"))
        remove_button.clicked.connect(
            lambda: self.remove_item(type_key, name, row)
        )

        row_layout.addWidget(name_label, 1)
        row_layout.addWidget(distance_label)
        row_layout.addWidget(remove_button)
        self.items_layout.addWidget(row)

        self.distance_input.setValue(0.0)

    def remove_item(self, type_key: str, name: str, row: QWidget) -> None:
        self.entries = [
            entry for entry in self.entries
            if not (entry[0] == type_key and entry[1] == name)
        ]
        self.items_layout.removeWidget(row)
        row.deleteLater()
        self.error_label.clear()

    def values(self) -> dict[str, list[dict[str, str | float]]]:
        grouped: dict[str, list[dict[str, str | float]]] = {}
        for type_key, name, distance in self.entries:
            key = {
                "mall": "malls",
                "school": "schools",
                "hospital": "hospitals",
                "market": "markets",
                "church": "churches",
                "bank": "banks",
                "government_office": "government_offices",
                "transport_hub": "transport_hubs",
                "park": "parks",
                "restaurant": "restaurants",
                "other": "others",
            }.get(type_key, f"{type_key}s")

            grouped.setdefault(key, []).append(
                {"name": name, "distance_km": distance}
            )
        return grouped


class PropertyEditDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None = None,
        listing: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(parent)
        self.existing_listing = listing
        self.setWindowTitle("Edit Property")
        available = self.screen().availableGeometry()
        # Keep the dialog inside the actual available screen area.
        # The form below is intentionally compact so the normal layout
        # fits without forcing the window beyond the screen.
        width = min(1100, max(760, available.width() - 40))
        height = min(820, max(600, available.height() - 40))
        self.setMinimumSize(min(760, width), min(600, height))
        self.resize(width, height)
        self.setStyleSheet(
            """
            QDialog { background: #eef3e5; color: #dee0dc; }
            QGroupBox {
                background: #f7f9f3;
                border: 1px solid #d5dfcc;
                border-radius: 8px;
                margin-top: 10px;
                padding: 12px;
                font-weight: 700;
                color: #17310a;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 12px;
                padding: 0 5px;
            }
            QLineEdit, QSpinBox, QDoubleSpinBox, QTextEdit, QListWidget {
                background: #ffffff;
                color: #17240f;
                border: 1px solid #cbd6c1;
                border-radius: 5px;
                padding: 6px;
            }
            QCheckBox {
                color: #17240f;
                spacing: 7px;
                min-height: 24px;
            }

            QCheckBox::indicator {
                width: 18px;
                height: 18px;
                border: 1px solid #aebca4;
                border-radius: 3px;
                background: #ffffff;
            }

            QCheckBox::indicator:hover {
                border: 1px solid #486b2a;
            }

            QCheckBox::indicator:checked {
                background: #486b2a;
                border: 1px solid #486b2a;
            }

            QAbstractSpinBox {
                padding-right: 28px;
            }

            QSpinBox::up-button,
            QDoubleSpinBox::up-button,
            QSpinBox::down-button,
            QDoubleSpinBox::down-button {
                width: 24px;
                border-left: 1px solid #cbd6c1;
                background: #f7f9f3;
            }

            QSpinBox::up-button,
            QDoubleSpinBox::up-button {
                subcontrol-origin: border;
                subcontrol-position: top right;
                border-top-right-radius: 5px;
                border-bottom: 1px solid #cbd6c1;
            }

            QSpinBox::down-button,
            QDoubleSpinBox::down-button {
                subcontrol-origin: border;
                subcontrol-position: bottom right;
                border-bottom-right-radius: 5px;
            }

            QSpinBox::up-button:hover,
            QDoubleSpinBox::up-button:hover,
            QSpinBox::down-button:hover,
            QDoubleSpinBox::down-button:hover {
                background: #e7eedc;
            }

            QSpinBox::up-button:pressed,
            QDoubleSpinBox::up-button:pressed,
            QSpinBox::down-button:pressed,
            QDoubleSpinBox::down-button:pressed {
                background: #d5e2ca;
            }

            QSpinBox::up-arrow,
            QDoubleSpinBox::up-arrow {
                width: 10px;
                height: 10px;
            }

            QSpinBox::down-arrow,
            QDoubleSpinBox::down-arrow {
                width: 10px;
                height: 10px;
            }
            QPushButton {
                background: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 5px;
                padding: 8px 12px;
            }
            QPushButton#saveProperty {
                background: #17310a;
                color: #ffffff;
                border-color: #17310a;
                font-weight: 700;
            }
            QLabel#formError { color: #9b3030; }
            """
        )

        content = QWidget()
        content_layout = QGridLayout(content)
        content_layout.setContentsMargins(14, 14, 14, 14)
        content_layout.setHorizontalSpacing(12)
        content_layout.setVerticalSpacing(10)
        content_layout.setColumnStretch(0, 1)
        content_layout.setColumnStretch(1, 1)

        information = QGroupBox("Property Information")
        info_form = QFormLayout(information)
        self.title_input = QLineEdit()
        # Standard categories; still editable for a special case.
        self.category_input = QComboBox()
        self.category_input.setEditable(True)
        self.category_input.addItems(PROPERTY_CATEGORIES)
        self.category_input.setCurrentIndex(-1)
        self.category_input.lineEdit().setPlaceholderText("Choose a category")
        self.layout_input = QLineEdit()
        self.location_input = QLineEdit()
        info_form.addRow("Title *", self.title_input)
        info_form.addRow("Category *", self.category_input)
        info_form.addRow("Layout Type", self.layout_input)
        info_form.addRow("Village / Location", self.location_input)
        content_layout.addWidget(information, 0, 0)

        pricing = QGroupBox("Pricing")
        pricing_grid = QGridLayout(pricing)
        pricing_grid.setContentsMargins(8, 8, 8, 8)
        pricing_grid.setHorizontalSpacing(10)
        pricing_grid.setVerticalSpacing(4)

        self.total_price = self._currency_input()
        self.initial_dp = self._currency_input()
        self.monthly_rate = self._currency_input()

        price_labels = [
            QLabel("Total Price"),
            QLabel("Initial Down Payment"),
            QLabel("Monthly Rate"),
        ]
        for label in price_labels:
            label.setWordWrap(True)
            label.setMinimumHeight(28)
            label.setStyleSheet("font-size: 11px; color: #17310a;")

        for column in range(3):
            pricing_grid.setColumnStretch(column, 1)

        pricing_grid.addWidget(price_labels[0], 0, 0)
        pricing_grid.addWidget(price_labels[1], 0, 1)
        pricing_grid.addWidget(price_labels[2], 0, 2)
        pricing_grid.addWidget(self.total_price, 1, 0)
        pricing_grid.addWidget(self.initial_dp, 1, 1)
        pricing_grid.addWidget(self.monthly_rate, 1, 2)
        content_layout.addWidget(pricing, 0, 1)

        details = QGroupBox("Property Details")
        details_form = QFormLayout(details)
        self.bedrooms = self._integer_input()
        self.bathrooms = self._integer_input()
        self.details_input = QTextEdit()
        self.details_input.setMinimumHeight(60)
        self.details_input.setMaximumHeight(72)
        details_form.addRow("Bedrooms", self.bedrooms)
        details_form.addRow("Bathrooms", self.bathrooms)
        details_form.addRow("Details / Description", self.details_input)
        content_layout.addWidget(details, 1, 1)

        location = QGroupBox("Location Coordinates")
        location_form = QFormLayout(location)
        location_form.setVerticalSpacing(6)

        self.latitude_input = QLineEdit()
        self.latitude_input.setPlaceholderText("-90 to 90")
        self.latitude_input.setValidator(
            QDoubleValidator(-90.0, 90.0, 6, self.latitude_input)
        )

        self.longitude_input = QLineEdit()
        self.longitude_input.setPlaceholderText("-180 to 180")
        self.longitude_input.setValidator(
            QDoubleValidator(-180.0, 180.0, 6, self.longitude_input)
        )

        location_form.addRow("Latitude", self.latitude_input)
        location_form.addRow("Longitude", self.longitude_input)
        content_layout.addWidget(location, 1, 0)

        # ---------------------------------------------------------
        # Property Features + Photos
        # These two cards intentionally sit side-by-side.
        # ---------------------------------------------------------

        amenities = QGroupBox("Property Features")
        amenities_grid = QGridLayout(amenities)
        amenities_grid.setContentsMargins(12, 12, 12, 12)
        amenities_grid.setHorizontalSpacing(18)
        amenities_grid.setVerticalSpacing(4)

        self.balcony = QCheckBox("Balcony")
        self.kitchen = QCheckBox("Kitchen")
        self.backyard = QCheckBox("Backyard")
        self.garage = QCheckBox("Garage")

        for checkbox in (
            self.balcony,
            self.kitchen,
            self.backyard,
            self.garage,
        ):
            checkbox.setCursor(Qt.CursorShape.PointingHandCursor)

        self.garage_spaces = self._integer_input()
        self.garage_spaces.setEnabled(False)
        self.garage.toggled.connect(self.garage_spaces.setEnabled)

        amenities_grid.addWidget(self.balcony, 0, 0)
        amenities_grid.addWidget(self.kitchen, 0, 1)
        amenities_grid.addWidget(self.backyard, 1, 0)
        amenities_grid.addWidget(self.garage, 1, 1)
        amenities_grid.addWidget(QLabel("Garage Spaces"), 2, 0)
        amenities_grid.addWidget(self.garage_spaces, 2, 1)
        amenities_grid.setColumnStretch(0, 1)
        amenities_grid.setColumnStretch(1, 1)

        # Keep the feature card compact and aligned with the photo card.
        amenities.setMinimumHeight(135)
        amenities.setMaximumHeight(150)

        photos = QGroupBox("Photos")
        photos_layout = QVBoxLayout(photos)
        photos_layout.setContentsMargins(12, 12, 12, 12)
        photos_layout.setSpacing(7)

        self.photo_list = QListWidget()
        self.photo_list.setMinimumHeight(58)
        self.photo_list.setMaximumHeight(62)

        photo_buttons = QHBoxLayout()
        photo_buttons.setSpacing(7)

        add_photo = QPushButton("Add Images")
        add_photo.setIcon(qta.icon("fa5s.images", color="#486b2a"))

        remove_photo = QPushButton("Remove")
        remove_photo.setIcon(qta.icon("fa5s.trash-alt", color="#486b2a"))

        add_photo.clicked.connect(self._add_photos)
        remove_photo.clicked.connect(self._remove_photo)

        photo_buttons.addWidget(add_photo)
        photo_buttons.addWidget(remove_photo)
        photo_buttons.addStretch()

        photo_note = QLabel(
            "Image paths are saved as references; files are not uploaded."
        )
        photo_note.setStyleSheet("color: #65745b; font-size: 11px;")
        photo_note.setWordWrap(True)

        photos_layout.addWidget(self.photo_list)
        photos_layout.addLayout(photo_buttons)
        photos_layout.addWidget(photo_note)

        photos.setMinimumHeight(135)
        photos.setMaximumHeight(150)

        # Row 2: Property Features | Photos
        content_layout.addWidget(
            amenities,
            2,
            0,
            alignment=Qt.AlignmentFlag.AlignTop,
        )
        content_layout.addWidget(
            photos,
            2,
            1,
            alignment=Qt.AlignmentFlag.AlignTop,
        )

        # ---------------------------------------------------------
        # Additional Information
        # Full-width section underneath Property Features + Photos.
        # ---------------------------------------------------------

        additional = QGroupBox("Additional Information")
        additional_layout = QGridLayout(additional)
        additional_layout.setContentsMargins(12, 12, 12, 12)
        additional_layout.setHorizontalSpacing(14)
        additional_layout.setVerticalSpacing(4)

        self.amenity_list_input = DynamicStringList(
            "Amenities", "Enter amenity..."
        )

        self.nearby_places_input = NearbyPlacesList()

        self.nearby_establishments_input = NearbyEstablishmentsList(
            self.nearby_places_input
        )

        self.nearby_places_input.changed.connect(
            self.nearby_establishments_input.refresh_places
        )

        # Keep the three additional-information controls side-by-side.
        # This prevents the Add Property dialog from becoming unnecessarily
        # tall while preserving the requested full-width section.
        additional_layout.addWidget(self.amenity_list_input, 0, 0)
        additional_layout.addWidget(self.nearby_places_input, 0, 1)
        additional_layout.addWidget(self.nearby_establishments_input, 0, 2)

        for column in range(3):
            additional_layout.setColumnStretch(column, 1)

        self.amenity_list_input.setMinimumHeight(112)
        self.nearby_places_input.setMinimumHeight(112)
        self.nearby_establishments_input.setMinimumHeight(112)

        # Row 3: Additional Information spans both columns.
        content_layout.addWidget(
            additional,
            3,
            0,
            1,
            2,
        )

        content.setSizePolicy(
            QSizePolicy.Policy.Preferred,
            QSizePolicy.Policy.Preferred,
        )

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll.setWidget(content)

        self.error_label = QLabel()
        self.error_label.setObjectName("formError")
        self.error_label.setWordWrap(True)
        self.save_button = QPushButton("Save Property")
        self.save_button.setObjectName("saveProperty")
        self.save_button.setIcon(qta.icon("fa5s.save", color="#ffffff"))
        self.cancel_button = QPushButton("Cancel")
        self.cancel_button.setIcon(qta.icon("fa5s.times", color="#486b2a"))
        self.cancel_button.clicked.connect(self.reject)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(self.cancel_button)
        actions.addWidget(self.save_button)

        outer = QVBoxLayout(self)
        outer.addWidget(scroll, 1)
        outer.addWidget(self.error_label)
        outer.addLayout(actions)
        if listing is not None:
            self._populate_from_listing(listing)

    def _populate_from_listing(self, listing: dict[str, Any]) -> None:
        self.setWindowTitle("Edit Property")
        self.save_button.setText("Save Changes")
        self.title_input.setText(str(listing.get("title") or ""))
        self.category_input.setCurrentText(standard_category(listing.get("category")))
        self.layout_input.setText(str(listing.get("layout_type") or ""))
        self.location_input.setText(str(listing.get("village_name") or ""))
        self.total_price.setValue(float(listing.get("price_total") or 0))
        self.initial_dp.setValue(float(listing.get("initial_dp") or 0))
        self.monthly_rate.setValue(float(listing.get("monthly_rate") or 0))
        self.bedrooms.setValue(int(listing.get("num_bedrooms") or 0))
        self.bathrooms.setValue(int(listing.get("num_bathrooms") or 0))
        self.details_input.setPlainText(str(listing.get("details") or ""))
        self.latitude_input.setText(str(listing.get("lat") or ""))
        self.longitude_input.setText(str(listing.get("lng") or ""))
        self.balcony.setChecked(bool(listing.get("has_balcony")))
        self.kitchen.setChecked(bool(listing.get("has_kitchen")))
        self.backyard.setChecked(bool(listing.get("has_backyard")))
        has_garage = bool(listing.get("has_garage"))
        self.garage.setChecked(has_garage)
        self.garage_spaces.setEnabled(has_garage)
        self.garage_spaces.setValue(int(listing.get("garage_spaces") or 0))
        for path in listing.get("photos") or []:
            self.photo_list.addItem(str(path))

        amenities = listing.get("amenity_list") or []
        if isinstance(amenities, dict):
            amenities = list(amenities.keys())
        if isinstance(amenities, str):
            amenities = [amenities]
        for value in amenities:
            self.amenity_list_input.input.setText(str(value))
            self.amenity_list_input.add_item()

        place_type_by_key = {
            key: label
            for label, key in NearbyPlacesList.PLACE_TYPES.items()
        }
        nearby = listing.get("nearby_places") or {}
        if isinstance(nearby, dict):
            place_rows = [
                (place_type_by_key.get(key, "Other"), name)
                for key, values in nearby.items()
                for name in (values if isinstance(values, list) else [values])
            ]
        elif isinstance(nearby, list):
            place_rows = [("Other", name) for name in nearby]
        else:
            place_rows = []
        for place_type, name in place_rows:
            if isinstance(name, dict):
                name = name.get("name", "")
            if name:
                self.nearby_places_input.type_input.setCurrentText(place_type)
                self.nearby_places_input.name_input.setText(str(name))
                self.nearby_places_input.add_item()

        establishment_type_by_key = {
            "malls": "mall",
            "schools": "school",
            "hospitals": "hospital",
            "markets": "market",
            "churches": "church",
            "banks": "bank",
            "government_offices": "government_office",
            "transport_hubs": "transport_hub",
            "parks": "park",
            "restaurants": "restaurant",
            "others": "other",
        }
        label_by_type = {
            key: label for label, key in NearbyPlacesList.PLACE_TYPES.items()
        }
        establishments = listing.get("nearby_establishments") or {}
        if isinstance(establishments, dict):
            for group, records in establishments.items():
                type_key = establishment_type_by_key.get(group)
                if type_key is None:
                    continue
                place_label = label_by_type[type_key]
                if not isinstance(records, list):
                    records = [records]
                for record in records:
                    if isinstance(record, dict):
                        name = str(record.get("name") or "")
                        distance = float(record.get("distance_km") or 0)
                    else:
                        name = str(record or "")
                        distance = 0
                    if not name:
                        continue
                    if not any(
                        existing_type == place_label
                        and existing_name.casefold() == name.casefold()
                        for existing_type, existing_name
                        in self.nearby_places_input.entries
                    ):
                        self.nearby_places_input.type_input.setCurrentText(
                            place_label
                        )
                        self.nearby_places_input.name_input.setText(name)
                        self.nearby_places_input.add_item()
                    target = (place_label, type_key, name)
                    index = self.nearby_establishments_input.place_input.findData(
                        target
                    )
                    if index >= 0:
                        self.nearby_establishments_input.place_input.setCurrentIndex(
                            index
                        )
                        self.nearby_establishments_input.distance_input.setValue(
                            distance
                        )
                        self.nearby_establishments_input.add_item()

    @staticmethod
    def _currency_input() -> QDoubleSpinBox:
        control = QDoubleSpinBox()
        control.setRange(0, 999_999_999_999.99)
        control.setDecimals(2)
        control.setPrefix("₱ ")
        control.setGroupSeparatorShown(True)
        control.setMinimumWidth(0)
        control.setMinimumHeight(32)
        control.setCursor(Qt.CursorShape.ArrowCursor)
        return control

    @staticmethod
    def _integer_input() -> QSpinBox:
        control = QSpinBox()
        control.setRange(0, 100_000)
        control.setCursor(Qt.CursorShape.ArrowCursor)
        return control

    def _add_photos(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select property images",
            "",
            "Images (*.png *.jpg *.jpeg *.webp *.bmp)",
        )
        existing = {
            self.photo_list.item(index).text()
            for index in range(self.photo_list.count())
        }
        for path in paths:
            if path not in existing:
                self.photo_list.addItem(path)

    def _remove_photo(self) -> None:
        row = self.photo_list.currentRow()
        if row >= 0:
            self.photo_list.takeItem(row)

    def payload(self) -> dict[str, Any]:
        title = self.title_input.text().strip()
        category = standard_category(self.category_input.currentText())
        if not title:
            raise ValueError("Title is required.")
        if not category:
            raise ValueError("Category is required.")

        latitude_text = self.latitude_input.text().strip()
        longitude_text = self.longitude_input.text().strip()
        latitude = self._coordinate(latitude_text, "Latitude", -90, 90)
        longitude = self._coordinate(longitude_text, "Longitude", -180, 180)
        if (latitude is None) != (longitude is None):
            raise ValueError(
                "Enter both latitude and longitude, or leave both blank."
            )

        photos = [
            self.photo_list.item(index).text()
            for index in range(self.photo_list.count())
        ]
        payload = {
            "title": title,
            "category": category,
            "layout_type": self.layout_input.text().strip() or None,
            "village_name": self.location_input.text().strip() or None,
            "price_total": self.total_price.value(),
            "initial_dp": self.initial_dp.value(),
            "monthly_rate": self.monthly_rate.value(),
            "num_bedrooms": self.bedrooms.value(),
            "num_bathrooms": self.bathrooms.value(),
            "details": self.details_input.toPlainText().strip() or None,
            "lat": latitude,
            "lng": longitude,
            "photos": photos,
            "amenity_list": self.amenity_list_input.values(),
            "nearby_places": self.nearby_places_input.values(),
            "nearby_establishments": self.nearby_establishments_input.values(),
            "has_balcony": self.balcony.isChecked(),
            "has_kitchen": self.kitchen.isChecked(),
            "has_backyard": self.backyard.isChecked(),
            "has_garage": self.garage.isChecked(),
            "garage_spaces": (
                self.garage_spaces.value() if self.garage.isChecked() else 0
            ),
        }
        return payload

    @staticmethod
    def _coordinate(
        value: str,
        field: str,
        minimum: float,
        maximum: float,
    ) -> float | None:
        if not value:
            return None
        try:
            coordinate = float(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be numeric.") from exc
        if not minimum <= coordinate <= maximum:
            raise ValueError(f"{field} must be between {minimum} and {maximum}.")
        return coordinate

    def show_error(self, message: str) -> None:
        self.error_label.setText(message)


class PropertiesPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()

        self.controller = controller
        self.api = ApiClient()
        self.listings: list[dict[str, Any]] = []

        self._build_ui()
        if self.token:
            self.load_properties()

    def refresh(self) -> None:
        self.load_properties()

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(24, 24, 24, 24)
        main_layout.setSpacing(16)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        header_layout = QHBoxLayout()

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

        title = QLabel("Property Management")
        title.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 26px;
                font-weight: 700;
            }
            """
        )

        subtitle = QLabel(
            "Manage property listings, pricing, location, and synchronization."
        )
        subtitle.setStyleSheet(
            """
            QLabel {
                color: #60705a;
                font-size: 13px;
            }
            """
        )

        title_layout.addWidget(title)
        title_layout.addWidget(subtitle)

        header_layout.addLayout(title_layout)
        header_layout.addStretch()

        self.edit_property_button = QPushButton("Edit")
        self.edit_property_button.setIcon(qta.icon("fa5s.edit", color="#486b2a"))
        self.edit_property_button.clicked.connect(self.edit_selected_property)
        header_layout.addWidget(self.edit_property_button)

        self.delete_property_button = QPushButton("Delete")
        self.delete_property_button.setIcon(
            qta.icon("fa5s.trash-alt", color="#9b3030")
        )
        self.delete_property_button.clicked.connect(self.delete_selected_property)
        header_layout.addWidget(self.delete_property_button)

        self.sync_button = QPushButton("↻  Sync Listings")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.setFixedHeight(38)
        self.sync_button.setStyleSheet(
            """
            QPushButton {
                background-color: #17310a;
                color: white;
                border: none;
                border-radius: 7px;
                padding: 0 16px;
                font-size: 13px;
                font-weight: 600;
            }

            QPushButton:hover {
                background-color: #285214;
            }

            QPushButton:pressed {
                background-color: #102406;
            }

            QPushButton:disabled {
                background-color: #aeb8a7;
            }
            """
        )
        self.sync_button.clicked.connect(self.sync_listings)

        header_layout.addWidget(self.sync_button)

        main_layout.addLayout(header_layout)

        # -----------------------------------------------------
        # Search / Filter Bar
        # -----------------------------------------------------

        filter_layout = QHBoxLayout()
        filter_layout.setSpacing(10)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search property, location, or category..."
        )
        self.search_input.setFixedHeight(38)
        self.search_input.setClearButtonEnabled(True)

        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #ffffff;
                border: 1px solid #cbd5c4;
                border-radius: 7px;
                padding: 0 12px;
                color: #17310a;
                font-size: 13px;
            }

            QLineEdit:focus {
                border: 1px solid #5d7d4e;
            }
            """
        )

        self.search_input.textChanged.connect(self.apply_filters)

        filter_layout.addWidget(self.search_input, 1)

        self.category_filter = QComboBox()
        self.category_filter.setFixedHeight(38)
        self.category_filter.setMinimumWidth(150)
        self.category_filter.addItem("All Categories")

        self.category_filter.setStyleSheet(
            """
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5c4;
                border-radius: 7px;
                padding: 0 10px;
                color: #17310a;
                font-size: 13px;
            }

            QComboBox:focus {
                border: 1px solid #5d7d4e;
            }
            """
        )

        self.category_filter.currentTextChanged.connect(
            self.apply_filters
        )

        filter_layout.addWidget(self.category_filter)

        self.status_filter = QComboBox()
        self.status_filter.setFixedHeight(38)
        self.status_filter.setMinimumWidth(150)
        self.status_filter.addItem("All Property Status", None)
        for label, value, _color in PROPERTY_STATUSES:
            self.status_filter.addItem(label, value)
        self.status_filter.currentIndexChanged.connect(self.apply_filters)
        filter_layout.addWidget(self.status_filter)

        self.sync_filter = QComboBox()
        self.sync_filter.setFixedHeight(38)
        self.sync_filter.setMinimumWidth(140)
        self.sync_filter.addItems(
            [
                "All Sync Status",
                "SYNCED",
                "PENDING",
                "ERROR",
            ]
        )

        self.sync_filter.setStyleSheet(
            """
            QComboBox {
                background-color: #ffffff;
                border: 1px solid #cbd5c4;
                border-radius: 7px;
                padding: 0 10px;
                color: #17310a;
                font-size: 13px;
            }

            QComboBox:focus {
                border: 1px solid #5d7d4e;
            }
            """
        )

        self.sync_filter.currentTextChanged.connect(
            self.apply_filters
        )

        filter_layout.addWidget(self.sync_filter)

        main_layout.addLayout(filter_layout)

        # Status chips (drive the existing status filter) + view toggle.
        chips_row = QHBoxLayout()
        chips_row.setSpacing(8)
        self.status_chips: list[QPushButton] = []
        for label, value in [("All", None)] + [(label, value) for label, value, _c in PROPERTY_STATUSES]:
            chip = QPushButton(label)
            chip.setCheckable(True)
            chip.setChecked(value is None)
            chip.setCursor(Qt.CursorShape.PointingHandCursor)
            chip.setProperty("statusValue", value)
            chip.setStyleSheet(_chip_style())
            chip.clicked.connect(lambda _checked, v=value: self._select_status_chip(v))
            chips_row.addWidget(chip)
            self.status_chips.append(chip)
        chips_row.addStretch()
        self.cards_view_button = QPushButton("Cards")
        self.table_view_button = QPushButton("Table")
        for button, icon, index in ((self.cards_view_button, "fa5s.th-large", 0),
                                    (self.table_view_button, "fa5s.list", 1)):
            button.setCheckable(True)
            button.setIcon(qta.icon(icon, color=TOKENS["text"]))
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setStyleSheet(_chip_style())
            button.clicked.connect(lambda _checked, i=index: self._set_view(i))
            chips_row.addWidget(button)
        self.status_filter.hide()  # the chips replace the dropdown visually
        main_layout.addLayout(chips_row)

        # -----------------------------------------------------
        # Record Count
        # -----------------------------------------------------

        self.record_count = QLabel("0 properties")
        self.record_count.setStyleSheet(
            """
            QLabel {
                color: #60705a;
                font-size: 12px;
                font-weight: 600;
            }
            """
        )

        main_layout.addWidget(self.record_count)

        # -----------------------------------------------------
        # Property Table
        # -----------------------------------------------------

        self.table = QTableWidget()
        self.table.setColumnCount(9)

        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Property",
                "Category",
                "Location",
                "Price",
                "Monthly",
                "Beds / Baths",
                "Status",
                "Sync",
            ]
        )

        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.table.setEditTriggers(
            QAbstractItemView.EditTrigger.NoEditTriggers
        )
        self.table.setSortingEnabled(True)
        self.table.setShowGrid(False)
        self.table.verticalHeader().setVisible(False)

        self.table.setStyleSheet(
            """
            QTableWidget {
                background-color: #ffffff;
                alternate-background-color: #f5f7f2;
                border: 1px solid #d4dccf;
                border-radius: 8px;
                color: #26351f;
                font-size: 13px;
                selection-background-color: #dcebd3;
                selection-color: #17310a;
            }

            QTableWidget::item {
                padding: 8px;
                border-bottom: 1px solid #edf0eb;
            }

            QTableWidget::item:selected {
                background-color: #c8dfb7;
                color: #17310a;
                font-weight: 600;
            }

            QTableWidget::item:selected:!active {
                background-color: #dcebd3;
                color: #17310a;
            }

            QHeaderView::section {
                background-color: #e4ebdf;
                color: #17310a;
                border: none;
                border-bottom: 1px solid #cbd5c4;
                padding: 9px;
                font-size: 12px;
                font-weight: 700;
            }
            """
        )

        header = self.table.horizontalHeader()

        header.setSectionResizeMode(
            0,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            1,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            2,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            3,
            QHeaderView.ResizeMode.Stretch,
        )

        header.setSectionResizeMode(
            4,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            5,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            6,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        header.setSectionResizeMode(
            7,
            QHeaderView.ResizeMode.ResizeToContents,
        )
        header.setSectionResizeMode(
            8,
            QHeaderView.ResizeMode.ResizeToContents,
        )

        self.table.cellDoubleClicked.connect(
            self.show_property_details
        )

        self.card_grid = PropertyCardGrid()
        self.card_grid.listing_selected.connect(self._card_selected)
        self.card_grid.listing_opened.connect(self._card_opened)
        self.views = QStackedWidget()
        self.views.addWidget(self.card_grid)
        self.views.addWidget(self.table)
        main_layout.addWidget(self.views, 1)
        self._set_view(0)

    # ---------------------------------------------------------
    # Message Box Styling
    # ---------------------------------------------------------

    @staticmethod
    def _status_label(status: Any) -> str:
        status = str(status or "AVAILABLE").upper()
        return next(
            (label for label, value, _color in PROPERTY_STATUSES if value == status),
            "Available",
        )

    @staticmethod
    def _api_error_message(exc: httpx.HTTPStatusError) -> str:
        try:
            detail = exc.response.json().get("detail")
        except ValueError:
            detail = None
        if isinstance(detail, list):
            return "\n".join(
                str(item.get("msg", "Invalid value"))
                for item in detail
                if isinstance(item, dict)
            )
        return str(detail or f"The server returned HTTP {exc.response.status_code}.")

    def _show_message(
        self,
        title: str,
        message: str,
        icon: QMessageBox.Icon = QMessageBox.Icon.Information,
    ) -> None:
        """Show a light-themed message box regardless of the app/global theme."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(message)
        box.setIcon(icon)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        box.setStyleSheet(
            """
            QMessageBox {
                background-color: #ffffff;
                color: #17310a;
                border: 1px solid #d5dfcc;
            }
            QMessageBox QLabel {
                background-color: #ffffff;
                color: #17310a;
                font-size: 13px;
            }
            QMessageBox QPushButton {
                background-color: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 5px;
                padding: 6px 18px;
                min-width: 60px;
                min-height: 28px;
                font-weight: 600;
            }
            QMessageBox QPushButton:hover {
                background-color: #dcebd3;
                border-color: #9eb78e;
            }
            QMessageBox QPushButton:pressed {
                background-color: #cddfc1;
            }
            """
        )
        box.exec()

    # ---------------------------------------------------------
    # Edit Property
    # ---------------------------------------------------------

    def _selected_listing(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def edit_selected_property(self) -> None:
        listing = self._selected_listing()
        if listing is None:
            self._show_message(
                "Edit Property",
                "Select a property first.",
                QMessageBox.Icon.Warning,
            )
            return
        dialog = PropertyEditDialog(self, listing=listing)
        dialog.save_button.clicked.connect(
            lambda: self._save_property(dialog, listing["listing_id"])
        )
        dialog.exec()

    def delete_selected_property(self) -> None:
        listing = self._selected_listing()
        if listing is None:
            self._show_message(
                "Delete Property",
                "Select a property first.",
                QMessageBox.Icon.Warning,
            )
            return
        listing_id = listing["listing_id"]
        title = listing.get("title") or "this property"
        confirmation = QMessageBox(self)
        confirmation.setWindowTitle("Delete Property?")
        confirmation.setIcon(QMessageBox.Icon.Warning)
        confirmation.setText("Are you sure you want to delete this property?")
        confirmation.setInformativeText(
            f"{title}\nThis action cannot be undone."
        )
        confirmation.setStandardButtons(
            QMessageBox.StandardButton.Cancel
            | QMessageBox.StandardButton.Yes
        )
        confirmation.button(QMessageBox.StandardButton.Yes).setText("Delete")
        confirmation.setDefaultButton(QMessageBox.StandardButton.Cancel)
        confirmation.setStyleSheet(
            "QMessageBox { background: #ffffff; color: #17310a; }"
            "QMessageBox QLabel { color: #17310a; }"
            "QMessageBox QPushButton { background: #e7eedc; color: #17310a; "
            "border: 1px solid #cbd8be; border-radius: 5px; padding: 6px 16px; }"
        )
        if confirmation.exec() != QMessageBox.StandardButton.Yes:
            return
        if not self.token:
            self._show_message(
                "Delete Failed",
                "Please sign in again before deleting a property.",
                QMessageBox.Icon.Warning,
            )
            return
        try:
            self.api.delete_property_listing(listing_id, token=self.token)
            self.load_properties()
        except httpx.HTTPStatusError as exc:
            self._show_message(
                "Delete Failed",
                self._api_error_message(exc),
                QMessageBox.Icon.Critical,
            )
        except httpx.RequestError:
            self._show_message(
                "Delete Failed",
                "Unable to connect to the FastAPI server.",
                QMessageBox.Icon.Critical,
            )
        except Exception as exc:
            self._show_message(
                "Delete Failed",
                f"The property could not be deleted: {exc}",
                QMessageBox.Icon.Critical,
            )

    def _save_property(
        self,
        dialog: PropertyEditDialog,
        listing_id: int,
    ) -> None:
        try:
            payload = dialog.payload()
        except ValueError as exc:
            dialog.show_error(str(exc))
            return

        if not self.token:
            dialog.show_error("Please sign in again before saving a property.")
            return

        dialog.save_button.setEnabled(False)
        try:
            result = self.api.update_property_listing(
                listing_id,
                payload,
                token=self.token,
            )
        except httpx.HTTPStatusError as exc:
            try:
                detail = exc.response.json().get("detail")
            except ValueError:
                detail = None
            if isinstance(detail, list):
                message = "\n".join(
                    str(item.get("msg", "Invalid value"))
                    for item in detail
                    if isinstance(item, dict)
                )
            else:
                message = str(detail or "The server rejected this property.")
            dialog.show_error(message)
        except httpx.RequestError:
            dialog.show_error(
                "Unable to connect to the FastAPI server. "
                "Check the connection and try again."
            )
        except Exception as exc:
            dialog.show_error(f"Unable to save the property: {exc}")
        else:
            dialog.accept()
            self.search_input.clear()
            self.category_filter.setCurrentIndex(0)
            self.status_filter.setCurrentIndex(0)
            self.sync_filter.setCurrentIndex(0)
            self.load_properties()
            self._show_message(
                "Property Updated Successfully"
                if listing_id is not None
                else "Property Added Successfully",
                (
                    f"{result.get('title', 'Property')} was "
                    f"{'updated' if listing_id is not None else 'added'} successfully.\n"
                    f"Listing ID: {result.get('listing_id')}\n"
                    f"Property status: "
                    f"{self._status_label(result.get('status'))}\n"
                    f"Sync status: {result.get('sync_status', 'PENDING')}"
                ),
            )
        finally:
            if dialog.isVisible():
                dialog.save_button.setEnabled(True)

    # ---------------------------------------------------------
    # Load Properties
    # ---------------------------------------------------------

    def load_properties(self, sync_cloud: bool = False) -> None:
        # Listings come from documents and the backend's cloud sync; the page
        # only reads them. Explicit sync is the "Sync Listings" button.
        if not self.token:
            self.record_count.setText("Sign in to load properties.")
            return
        self.sync_button.setEnabled(False)
        self.record_count.setText("Loading properties...")
        cloud_sync_warning = None

        try:
            if sync_cloud:
                try:
                    sync_result = self.api.sync_property_listings(token=self.token)
                    sync_errors = int(sync_result.get("errors", 0))
                    if sync_errors:
                        cloud_sync_warning = (
                            f"Cloud sync reported {sync_errors} listing error(s)."
                        )
                except Exception as exc:
                    cloud_sync_warning = str(exc)

            data = self.api.get_property_listings(token=self.token)

            if not isinstance(data, list):
                raise RuntimeError(
                    "The server returned an invalid property listing response."
                )

            self.listings = data

            self.populate_category_filter()
            self.apply_filters()
            if cloud_sync_warning:
                self.record_count.setText(
                    f"{self.record_count.text()} | Showing local cache; "
                    f"cloud sync unavailable: {cloud_sync_warning}"
                )

        except httpx.RequestError as exc:
            self.record_count.setText("Unable to connect to server.")

            self._show_message(
                "Connection Error",
                (
                    "Unable to connect to the FastAPI server.\n\n"
                    "Make sure the backend is running on:\n"
                    "http://localhost:8000\n\n"
                    f"Details: {exc}"
                ),
                QMessageBox.Icon.Critical,
            )

        except httpx.HTTPStatusError as exc:
            self.record_count.setText("Server returned an error.")

            self._show_message(
                "Server Error",
                (
                    f"The server returned HTTP "
                    f"{exc.response.status_code}.\n\n"
                    "Please check the FastAPI backend."
                ),
                QMessageBox.Icon.Critical,
            )

        except Exception as exc:
            self.record_count.setText("Unable to load properties.")

            self._show_message(
                "Property Loading Error",
                f"Unable to load property listings.\n\n{exc}",
                QMessageBox.Icon.Critical,
            )

        finally:
            self.sync_button.setEnabled(True)

    # ---------------------------------------------------------
    # Populate Categories
    # ---------------------------------------------------------

    def populate_category_filter(self) -> None:
        current = self.category_filter.currentText()

        categories = sorted(
            {
                str(item.get("category")).strip()
                for item in self.listings
                if item.get("category")
            }
        )

        self.category_filter.blockSignals(True)

        self.category_filter.clear()
        self.category_filter.addItem("All Categories")

        for category in categories:
            self.category_filter.addItem(category.title())

        index = self.category_filter.findText(current)

        if index >= 0:
            self.category_filter.setCurrentIndex(index)
        else:
            self.category_filter.setCurrentIndex(0)

        self.category_filter.blockSignals(False)

    # ---------------------------------------------------------
    # Filtering
    # ---------------------------------------------------------

    def apply_filters(self) -> None:
        search_text = self.search_input.text().strip().lower()

        selected_category = self.category_filter.currentText()
        selected_sync = self.sync_filter.currentText()
        selected_status = self.status_filter.currentData()

        if selected_category == "All Categories":
            selected_category = ""

        if selected_sync == "All Sync Status":
            selected_sync = ""

        filtered: list[dict[str, Any]] = []

        for listing in self.listings:
            title = str(listing.get("title") or "")
            category = str(listing.get("category") or "")
            location = str(listing.get("village_name") or "")
            sync_status = str(listing.get("sync_status") or "")
            property_status = str(listing.get("status") or "AVAILABLE").upper()

            searchable_text = (
                f"{title} {category} {location}"
            ).lower()

            if search_text and search_text not in searchable_text:
                continue

            if selected_category:
                if category.lower() != selected_category.lower():
                    continue

            if selected_sync:
                if sync_status.upper() != selected_sync.upper():
                    continue

            if selected_status and property_status != selected_status:
                continue

            filtered.append(listing)

        self.populate_table(filtered)
        self.card_grid.set_listings(filtered)

    # ---------------------------------------------------------
    # Card view helpers
    # ---------------------------------------------------------

    def _set_view(self, index: int) -> None:
        self.views.setCurrentIndex(index)
        self.cards_view_button.setChecked(index == 0)
        self.table_view_button.setChecked(index == 1)

    def _select_status_chip(self, value) -> None:
        for chip in self.status_chips:
            chip.setChecked(chip.property("statusValue") == value)
        self.status_filter.setCurrentIndex(max(self.status_filter.findData(value), 0))

    def _table_row_for(self, listing: dict[str, Any]) -> int:
        for row in range(self.table.rowCount()):
            item = self.table.item(row, 0)
            data = item.data(Qt.ItemDataRole.UserRole) if item else None
            if isinstance(data, dict) and data.get("listing_id") == listing.get("listing_id"):
                return row
        return -1

    def _card_selected(self, listing: dict[str, Any]) -> None:
        row = self._table_row_for(listing)
        if row >= 0:
            self.table.selectRow(row)  # Edit/Delete act on the selected card

    def _card_opened(self, listing: dict[str, Any]) -> None:
        row = self._table_row_for(listing)
        if row >= 0:
            self.table.selectRow(row)
            self.show_property_details(row, 0)

    # ---------------------------------------------------------
    # Populate Table
    # ---------------------------------------------------------

    def populate_table(
        self,
        listings: list[dict[str, Any]],
    ) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(0)

        for listing in listings:
            row = self.table.rowCount()
            self.table.insertRow(row)

            listing_id = listing.get("listing_id")
            title = listing.get("title") or "Untitled Property"
            category = listing.get("category") or "-"
            location = listing.get("village_name") or "-"
            price = listing.get("price_total")
            monthly = listing.get("monthly_rate")
            bedrooms = listing.get("num_bedrooms")
            bathrooms = listing.get("num_bathrooms")
            sync_status = listing.get("sync_status") or "-"
            status = str(listing.get("status") or "AVAILABLE").upper()
            status_label, status_color = next(
                (
                    (label, color)
                    for label, value, color in PROPERTY_STATUSES
                    if value == status
                ),
                ("Available", "#e5efdc"),
            )

            self.table.setItem(
                row,
                0,
                self.make_item(str(listing_id or "-")),
            )

            self.table.setItem(
                row,
                1,
                self.make_item(str(title)),
            )

            self.table.setItem(
                row,
                2,
                self.make_item(str(category).title()),
            )

            self.table.setItem(
                row,
                3,
                self.make_item(str(location)),
            )

            self.table.setItem(
                row,
                4,
                self.make_item(self.format_currency(price)),
            )

            self.table.setItem(
                row,
                5,
                self.make_item(self.format_currency(monthly)),
            )

            bed_bath = f"{bedrooms or 0} / {bathrooms or 0}"

            self.table.setItem(
                row,
                6,
                self.make_item(bed_bath),
            )

            status_item = self.make_item(status_label, center=True)
            self.table.setItem(row, 7, status_item)

            sync_item = self.make_item(
                str(sync_status),
                center=True,
            )

            self.table.setItem(row, 8, sync_item)
            self.table.item(row, 0).setData(
                Qt.ItemDataRole.UserRole,
                listing,
            )
            # Status badge on the status cell only (readable on the dark theme).
            _text, _bg = badge_colors(listing.get("status") or "AVAILABLE")
            status_item.setForeground(_text)
            status_item.setBackground(_bg)
            status_font = status_item.font()
            status_font.setBold(True)
            status_item.setFont(status_font)

        self.table.setSortingEnabled(True)

        self.record_count.setText(
            f"{len(listings)} "
            f"{'property' if len(listings) == 1 else 'properties'}"
        )

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    @staticmethod
    def make_item(
        value: str,
        center: bool = False,
    ) -> QTableWidgetItem:
        item = QTableWidgetItem(value)

        if center:
            item.setTextAlignment(
                Qt.AlignmentFlag.AlignCenter
            )

        return item

    @staticmethod
    def format_currency(value: Any) -> str:
        if value is None:
            return "-"

        try:
            return f"₱{float(value):,.2f}"
        except (TypeError, ValueError):
            return "-"

    # ---------------------------------------------------------
    # Sync
    # ---------------------------------------------------------

    def sync_listings(self) -> None:
        self.sync_button.setEnabled(False)
        self.sync_button.setText("↻  Syncing...")

        try:
            result = self.api.sync_property_listings(token=self.token)

            total = result.get("total", 0)
            inserted = result.get("inserted", 0)
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)

            if errors > 0:
                self._show_message(
                    "Synchronization Completed",
                    (
                        f"Total listings: {total}\n"
                        f"Inserted: {inserted}\n"
                        f"Updated: {updated}\n"
                        f"Errors: {errors}"
                    ),
                    QMessageBox.Icon.Warning,
                )
            else:
                self._show_message(
                    "Synchronization Completed",
                    (
                        f"Successfully synchronized {total} "
                        f"property listings.\n\n"
                        f"Inserted: {inserted}\n"
                        f"Updated: {updated}"
                    ),
                )

            self.load_properties(sync_cloud=False)

        except httpx.RequestError as exc:
            self._show_message(
                "Sync Error",
                (
                    "Unable to connect to the FastAPI server.\n\n"
                    f"Details: {exc}"
                ),
                QMessageBox.Icon.Critical,
            )

        except httpx.HTTPStatusError as exc:
            self._show_message(
                "Sync Error",
                (
                    f"Synchronization failed with HTTP "
                    f"{exc.response.status_code}."
                ),
                QMessageBox.Icon.Critical,
            )

        except Exception as exc:
            self._show_message(
                "Sync Error",
                f"Unable to synchronize listings.\n\n{exc}",
                QMessageBox.Icon.Critical,
            )

        finally:
            self.sync_button.setEnabled(True)
            self.sync_button.setText("↻  Sync Listings")

    # ---------------------------------------------------------
    # Property Details
    # ---------------------------------------------------------

    def show_property_details(
        self,
        row: int,
        column: int,
    ) -> None:
        id_item = self.table.item(row, 0)

        if id_item is None:
            return

        try:
            listing_id = int(id_item.text())
        except ValueError:
            return

        listing = next(
            (
                item
                for item in self.listings
                if item.get("listing_id") == listing_id
            ),
            None,
        )

        if listing is None:
            return

        from app.views.main.pages.property_profile import PropertyProfileDialog

        PropertyProfileDialog(
            listing,
            self,
            category=standard_category(listing.get("category")) or None,
            status_label=self._status_label(listing.get("status")),
            on_edit=self.edit_selected_property,
        ).exec()