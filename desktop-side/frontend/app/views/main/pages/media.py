from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap
from PyQt6.QtWidgets import QComboBox, QFileDialog, QHBoxLayout, QLabel, QMessageBox

from app.api.client import error_message
from app.views.main.pages._common import Card, DataPage, button, fill, fmt_date, table

EDITOR_ROLES = {"administrator", "general manager", "president", "filing manager"}


class MediaPage(DataPage):
    title = "Digital Preview Management"
    subtitle = ("Property images with OpenCV quality analysis: resolution, orientation, blur, "
                "exposure and contrast. Room or feature recognition is not performed. "
                "Only GOOD/ACCEPTABLE images are published to the website.")

    def build(self) -> None:
        self.listing = QComboBox()
        self.listing.setMinimumWidth(280)
        self.listing.currentIndexChanged.connect(self._load_media)
        self.upload_button = button("Upload Images", "fa5s.images", primary=True)
        self.upload_button.clicked.connect(self.upload)
        self.delete_button = button("Delete", "fa5s.trash-alt")
        self.delete_button.clicked.connect(self.delete)
        for widget in (self.delete_button, self.upload_button, self.listing):
            self.actions.insertWidget(0, widget)
        cards = QHBoxLayout()
        self.total_card = Card("Images")
        self.good_card = Card("Good", "#486b2a")
        self.ok_card = Card("Acceptable", "#9a6a13")
        self.poor_card = Card("Poor", "#9b3030")
        for card in (self.total_card, self.good_card, self.ok_card, self.poor_card):
            cards.addWidget(card)
        self.layout_.addLayout(cards)
        body = QHBoxLayout()
        self.table = table(["File", "Quality", "Resolution", "Orientation", "Sharpness", "Brightness",
                            "Contrast", "Issues", "Uploaded"])
        self.table.itemSelectionChanged.connect(self._preview)
        body.addWidget(self.table, 3)
        self.preview = QLabel("Select an image")
        self.preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview.setMinimumWidth(320)
        self.preview.setStyleSheet("background: #f7f9f3; border: 1px solid #d9e2d0; border-radius: 8px;")
        body.addWidget(self.preview, 2)
        self.layout_.addLayout(body, 1)
        self.media: list[dict] = []

    def load(self) -> None:
        editor = self.role.casefold() in EDITOR_ROLES
        self.upload_button.setVisible(editor)
        self.delete_button.setVisible(editor)
        current = self.listing.currentData()
        listings = self.api.get_property_listings(token=self.token)
        self.listing.blockSignals(True)
        self.listing.clear()
        self.listing.addItem("All properties", None)
        for item in listings:
            code = item.get("external_listing_id") or item["listing_id"]
            self.listing.addItem(f"{code} — {item.get('title') or 'Untitled'}", item["listing_id"])
        self.listing.setCurrentIndex(max(self.listing.findData(current), 0))
        self.listing.blockSignals(False)
        summary = self.api.get_media_summary(token=self.token)
        by_quality = summary["by_quality"]
        self.total_card.set(summary["total"])
        self.good_card.set(by_quality.get("GOOD", 0))
        self.ok_card.set(by_quality.get("ACCEPTABLE", 0))
        self.poor_card.set(by_quality.get("POOR", 0) + by_quality.get("INVALID", 0))
        self._load_media()

    def _load_media(self) -> None:
        if not self.token:
            return
        self.media = self.api.get_media(token=self.token, listing_id=self.listing.currentData())
        fill(self.table, ([m["file_name"], m["quality_status"], f"{m['width']}×{m['height']}",
                           m["orientation"], m["blur_score"], m["brightness"], m["contrast"],
                           "; ".join(m["quality_issues"]) or "None", fmt_date(m["created_at"])]
                          for m in self.media), self.media)
        self.status.setText(f"{len(self.media)} image(s)" if self.media else
                            "No images uploaded for this selection.")

    def _selected(self) -> dict | None:
        item = self.table.item(self.table.currentRow(), 0) if self.table.currentRow() >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _preview(self) -> None:
        media = self._selected()
        if media is None:
            return
        try:
            pixmap = QPixmap()
            pixmap.loadFromData(self.api.get_media_file(media["id"], token=self.token))
            self.preview.setPixmap(pixmap.scaled(420, 320, Qt.AspectRatioMode.KeepAspectRatio,
                                                 Qt.TransformationMode.SmoothTransformation))
        except Exception as exc:
            self.preview.setText(error_message(exc))

    def upload(self) -> None:
        listing_id = self.listing.currentData()
        if listing_id is None:
            QMessageBox.information(self, "Upload images", "Choose a property first.")
            return
        paths, _ = QFileDialog.getOpenFileNames(self, "Choose images", "",
                                                "Images (*.png *.jpg *.jpeg *.webp *.bmp *.tif *.tiff)")
        results = []
        for path in paths:
            try:
                media = self.api.upload_media(listing_id, path, token=self.token)
                issues = "; ".join(media["quality_issues"]) or "no issues"
                results.append(f"{media['file_name']}: {media['quality_status']} ({issues})")
            except Exception as exc:
                results.append(f"{path}: {error_message(exc)}")
        if results:
            QMessageBox.information(self, "Image analysis", "\n".join(results))
            self.refresh()

    def delete(self) -> None:
        media = self._selected()
        if media is None or QMessageBox.question(
                self, "Delete image", f"Delete {media['file_name']}?") != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_media(media["id"], token=self.token)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Delete failed", error_message(exc))
