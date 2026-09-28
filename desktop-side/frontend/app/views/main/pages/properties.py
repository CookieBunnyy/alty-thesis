from __future__ import annotations

from typing import Any

import httpx

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from app.api.client import ApiClient


class PropertiesPage(QWidget):
    def __init__(self) -> None:
        super().__init__()

        self.api = ApiClient()
        self.listings: list[dict[str, Any]] = []

        self._build_ui()
        self.load_properties()

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
        self.table.setColumnCount(8)

        self.table.setHorizontalHeaderLabels(
            [
                "ID",
                "Property",
                "Category",
                "Location",
                "Price",
                "Monthly",
                "Beds / Baths",
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

        self.table.cellDoubleClicked.connect(
            self.show_property_details
        )

        main_layout.addWidget(self.table, 1)

    # ---------------------------------------------------------
    # Load Properties
    # ---------------------------------------------------------

    def load_properties(self) -> None:
        self.sync_button.setEnabled(False)
        self.record_count.setText("Loading properties...")

        try:
            data = self.api.get_property_listings()

            if not isinstance(data, list):
                raise RuntimeError(
                    "The server returned an invalid property listing response."
                )

            self.listings = data

            self.populate_category_filter()
            self.apply_filters()

        except httpx.RequestError as exc:
            self.record_count.setText("Unable to connect to server.")

            QMessageBox.critical(
                self,
                "Connection Error",
                (
                    "Unable to connect to the FastAPI server.\n\n"
                    "Make sure the backend is running on:\n"
                    "http://localhost:8000\n\n"
                    f"Details: {exc}"
                ),
            )

        except httpx.HTTPStatusError as exc:
            self.record_count.setText("Server returned an error.")

            QMessageBox.critical(
                self,
                "Server Error",
                (
                    f"The server returned HTTP "
                    f"{exc.response.status_code}.\n\n"
                    "Please check the FastAPI backend."
                ),
            )

        except Exception as exc:
            self.record_count.setText("Unable to load properties.")

            QMessageBox.critical(
                self,
                "Property Loading Error",
                f"Unable to load property listings.\n\n{exc}",
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

            filtered.append(listing)

        self.populate_table(filtered)

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

            sync_item = self.make_item(
                str(sync_status),
                center=True,
            )

            self.table.setItem(row, 7, sync_item)

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
            result = self.api.post(
                "/api/v1/property-listings/sync"
            )

            total = result.get("total", 0)
            inserted = result.get("inserted", 0)
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)

            if errors > 0:
                QMessageBox.warning(
                    self,
                    "Synchronization Completed",
                    (
                        f"Total listings: {total}\n"
                        f"Inserted: {inserted}\n"
                        f"Updated: {updated}\n"
                        f"Errors: {errors}"
                    ),
                )
            else:
                QMessageBox.information(
                    self,
                    "Synchronization Completed",
                    (
                        f"Successfully synchronized {total} "
                        f"property listings.\n\n"
                        f"Inserted: {inserted}\n"
                        f"Updated: {updated}"
                    ),
                )

            self.load_properties()

        except httpx.RequestError as exc:
            QMessageBox.critical(
                self,
                "Sync Error",
                (
                    "Unable to connect to the FastAPI server.\n\n"
                    f"Details: {exc}"
                ),
            )

        except httpx.HTTPStatusError as exc:
            QMessageBox.critical(
                self,
                "Sync Error",
                (
                    f"Synchronization failed with HTTP "
                    f"{exc.response.status_code}."
                ),
            )

        except Exception as exc:
            QMessageBox.critical(
                self,
                "Sync Error",
                f"Unable to synchronize listings.\n\n{exc}",
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

        title = listing.get("title") or "Untitled Property"
        category = listing.get("category") or "-"
        location = listing.get("village_name") or "-"
        price = self.format_currency(
            listing.get("price_total")
        )
        initial_dp = self.format_currency(
            listing.get("initial_dp")
        )
        monthly = self.format_currency(
            listing.get("monthly_rate")
        )

        bedrooms = listing.get("num_bedrooms") or 0
        bathrooms = listing.get("num_bathrooms") or 0

        layout = listing.get("layout_type") or "-"
        sync_status = listing.get("sync_status") or "-"

        details = listing.get("details") or "No description available."

        message = (
            f"<b>{title}</b><br><br>"
            f"<b>Category:</b> {category.title()}<br>"
            f"<b>Location:</b> {location}<br>"
            f"<b>Layout:</b> {layout}<br>"
            f"<b>Bedrooms:</b> {bedrooms}<br>"
            f"<b>Bathrooms:</b> {bathrooms}<br><br>"
            f"<b>Total Price:</b> {price}<br>"
            f"<b>Initial DP:</b> {initial_dp}<br>"
            f"<b>Monthly Rate:</b> {monthly}<br><br>"
            f"<b>Sync Status:</b> {sync_status}<br><br>"
            f"<b>Details:</b><br>{details}"
        )

        QMessageBox.information(
            self,
            f"Property #{listing_id}",
            message,
        )