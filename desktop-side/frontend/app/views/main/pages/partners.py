from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QScrollArea,
    QVBoxLayout,
    QWidget,
    QFrame,
    QSizePolicy,
)


TYPE_LABELS = {
    "DEVELOPER": "Developer",
    "BROKERAGE": "Brokerage",
    "BANK": "Bank / Financing",
    "CONTRACTOR": "Contractor",
    "OTHER": "Partner",
}


class PartnerCard(QFrame):
    def __init__(self, partner: dict, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setObjectName("partnerCard")
        # Cards keep their natural height instead of stretching to fill space.
        self.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(12)

        # Company icon
        icon = QLabel("▣")
        icon.setFixedWidth(32)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setStyleSheet(
            """
            QLabel {
                background-color: #e4eddb;
                color: #486b2a;
                border-radius: 8px;
                font-size: 17px;
                font-weight: 700;
            }
            """
        )

        layout.addWidget(icon)

        # Company information
        information = QVBoxLayout()
        information.setSpacing(3)

        name_label = QLabel(partner.get("name") or "—")
        name_label.setStyleSheet(
            """
            QLabel {
                color: #17310a;
                font-size: 14px;
                font-weight: 700;
            }
            """
        )

        details = [TYPE_LABELS.get(partner.get("partner_type") or "", "Type not set")]
        if partner.get("contact_person"):
            details.append(partner["contact_person"])
        if partner.get("phone_number") or partner.get("email"):
            details.append(partner.get("phone_number") or partner.get("email"))
        listings = int(partner.get("listings") or 0)
        details.append(f"{listings} listing{'' if listings == 1 else 's'}"
                       + (f" · {partner.get('available_listings', 0)} available" if listings else ""))
        type_label = QLabel("  ·  ".join(details))
        type_label.setWordWrap(True)
        type_label.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 11px;
            }
            """
        )

        information.addWidget(name_label)
        information.addWidget(type_label)

        layout.addLayout(information)
        layout.addStretch()

        # Status
        active = str(partner.get("status") or "").upper() == "ACTIVE"
        status = QLabel("ACTIVE" if active else "INACTIVE")
        status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status.setStyleSheet(
            """
            QLabel {
                background-color: %s;
                color: %s;
                border-radius: 10px;
                padding: 4px 9px;
                font-size: 10px;
                font-weight: 700;
            }
            """ % (("#e5efdc", "#486b2a") if active else ("#e5e7e3", "#65745b"))
        )

        layout.addWidget(status)

        self.setStyleSheet(
            """
            QFrame#partnerCard {
                background-color: #f7f9f3;
                border: 1px solid #d9e2d0;
                border-radius: 10px;
            }

            QFrame#partnerCard:hover {
                background-color: #f0f5eb;
                border: 1px solid #b9cdaa;
            }
            """
        )


class PartnersPage(QWidget):
    """Partners / developers from the database (GET /api/v1/partners).
    Added and edited by management on the web Management System."""

    def __init__(self, controller=None) -> None:
        super().__init__()

        self.controller = controller
        self.partners: list[dict] = []

        self._build_ui()
        self._populate_partners()

    def refresh(self) -> None:
        """Called by the main window each time the page is opened."""
        from app.api.client import ApiClient, error_message

        token = self.controller.session.state.token if self.controller else None
        try:
            self.partners = ApiClient().get_partners(token=token)
        except Exception as exc:
            self.partners = []
            self._populate_partners()
            self.count_label.setText(f"Couldn't load partners: {error_message(exc)}")
            return
        self._filter_partners(self.search_input.text())

    # ---------------------------------------------------------
    # UI
    # ---------------------------------------------------------

    def _build_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(20, 18, 20, 20)
        main_layout.setSpacing(14)

        # -----------------------------------------------------
        # Header
        # -----------------------------------------------------

        header = QHBoxLayout()
        header.setSpacing(10)

        title_layout = QVBoxLayout()
        title_layout.setSpacing(2)

       

        subtitle = QLabel(
            "Abellar Realty's property developers and business partners. "
            "Management adds and edits them in the web Management System."
        )
        subtitle.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 13px;
            }
            """
        )

        title_layout.addWidget(subtitle)

        header.addLayout(title_layout)
        header.addStretch()

        main_layout.addLayout(header)

        # -----------------------------------------------------
        # Search
        # -----------------------------------------------------

        search_layout = QHBoxLayout()

        search_icon = QLabel("⌕")
        search_icon.setStyleSheet(
            """
            QLabel {
                color: #486b2a;
                font-size: 20px;
                font-weight: 700;
            }
            """
        )

        search_layout.addWidget(search_icon)

        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText(
            "Search developers and partners..."
        )
        self.search_input.setFixedHeight(38)
        self.search_input.setClearButtonEnabled(True)

        self.search_input.setStyleSheet(
            """
            QLineEdit {
                background-color: #ffffff;
                color: #17310a;
                border: 1px solid #cbd6c1;
                border-radius: 7px;
                padding: 0 12px;
                font-size: 13px;
            }

            QLineEdit:focus {
                border: 1px solid #6b8e52;
            }
            """
        )

        self.search_input.textChanged.connect(
            self._filter_partners
        )

        search_layout.addWidget(self.search_input, 1)

        main_layout.addLayout(search_layout)

        # -----------------------------------------------------
        # Count
        # -----------------------------------------------------

        self.count_label = QLabel()
        self.count_label.setStyleSheet(
            """
            QLabel {
                color: #65745b;
                font-size: 12px;
                font-weight: 600;
            }
            """
        )

        main_layout.addWidget(self.count_label)

        # -----------------------------------------------------
        # Scroll Area
        # -----------------------------------------------------

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        self.container = QWidget()

        self.grid = QGridLayout(self.container)
        self.grid.setContentsMargins(2, 2, 2, 12)
        self.grid.setHorizontalSpacing(12)
        self.grid.setVerticalSpacing(12)

        self.scroll.setWidget(self.container)

        main_layout.addWidget(self.scroll, 1)

    # ---------------------------------------------------------
    # Populate
    # ---------------------------------------------------------

    def _populate_partners(
        self,
        partners: list[dict] | None = None,
    ) -> None:

        if partners is None:
            partners = self.partners

        # Remove existing cards and the previous trailing stretch row
        for row in range(self.grid.rowCount()):
            self.grid.setRowStretch(row, 0)
        while self.grid.count():
            item = self.grid.takeAt(0)

            widget = item.widget()

            if widget is not None:
                widget.deleteLater()

        # Two-column layout
        columns = 2

        for index, partner in enumerate(partners):
            row = index // columns
            column = index % columns

            card = PartnerCard(partner)

            self.grid.addWidget(
                card,
                row,
                column,
            )

        self.count_label.setText(
            f"{len(partners)} "
            f"{'partner' if len(partners) == 1 else 'partners'}"
        )

        self.grid.setColumnStretch(0, 1)
        self.grid.setColumnStretch(1, 1)
        # An empty stretch row after the last card absorbs the spare height,
        # so one search result stays card-sized at the top.
        self.grid.setRowStretch((len(partners) + columns - 1) // columns, 1)

    # ---------------------------------------------------------
    # Search
    # ---------------------------------------------------------

    def _filter_partners(self, text: str) -> None:
        search = text.strip().lower()

        if not search:
            filtered = self.partners
        else:
            filtered = [
                partner
                for partner in self.partners
                if search in " ".join(
                    str(partner.get(key) or "")
                    for key in ("name", "partner_type", "contact_person", "email", "phone_number")
                ).lower()
            ]

        self._populate_partners(filtered)