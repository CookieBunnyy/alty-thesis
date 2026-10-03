"""Agent Management: real agents from the backend (no sample data).

Data flow: Supabase -> (Sync) -> local PostgreSQL -> FastAPI /api/v1/agents
-> ApiClient -> this page. Two ratings are shown and kept distinct:

* Client rating – average of client reviews (agent_reviews), with count.
* System rating – the legacy ``star_rating`` synced from Supabase.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import qtawesome as qta
from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.api.client import ApiClient, error_message
from app.theme import TOKENS as T
from app.theme import badge_colors


# ---------------------------------------------------------------------------
# Formatting helpers (shared by the table and the profile)
# ---------------------------------------------------------------------------

def _number(value: Any) -> float | None:
    try:
        return None if value is None or value == "" else float(value)
    except (TypeError, ValueError):
        return None


def stars(value: Any) -> str:
    rating = _number(value)
    if rating is None:
        return ""
    full = int(round(rating))
    return "★" * full + "☆" * max(0, 5 - full)


def client_rating_text(agent: dict[str, Any]) -> str:
    count = int(agent.get("review_count") or 0)
    rating = _number(agent.get("client_rating"))
    if not count or rating is None:
        return "No reviews yet"
    return f"{stars(rating)} {rating:.1f}  ({count} review{'s' if count != 1 else ''})"


def system_rating_text(value: Any) -> str:
    rating = _number(value)
    return "—" if rating is None else f"{stars(rating)} {rating:.1f}"


def money(value: Any) -> str:
    amount = _number(value)
    return "—" if amount is None else f"₱{amount:,.2f}"


def percent(value: Any) -> str:
    amount = _number(value)
    return "—" if amount is None else f"{amount:.1f}%"


class SortItem(QTableWidgetItem):
    """Sorts by a numeric key while displaying formatted text."""

    def __init__(self, text: str, key: float | str | None = None) -> None:
        super().__init__(text)
        self.key = key

    def __lt__(self, other: QTableWidgetItem) -> bool:
        if isinstance(other, SortItem) and isinstance(self.key, (int, float)) \
                and isinstance(other.key, (int, float)):
            return self.key < other.key
        return super().__lt__(other)


# ---------------------------------------------------------------------------
# Agent profile
# ---------------------------------------------------------------------------

class AgentProfileDialog(QDialog):
    def __init__(self, agent: dict[str, Any], api: ApiClient | None = None, token: str | None = None,
                 parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.agent = agent
        self.api = api
        self.token = token
        self.setWindowTitle(f"Agent Profile — {agent.get('full_name') or agent.get('agent_id')}")
        self.setMinimumSize(720, 640)
        self.setStyleSheet(
            f"""/*alty-raw*/
            QDialog {{ background: {T['bg']}; }}
            QLabel {{ color: {T['text']}; background: transparent; }}
            QLabel#muted {{ color: {T['text_muted']}; }}
            QLabel#faint {{ color: {T['text_faint']}; font-size: 11px; }}
            QLabel#section {{ color: {T['text']}; font-size: 15px; font-weight: 700; }}
            QFrame#card {{ background: {T['card']}; border: 1px solid {T['border']}; border-radius: 12px; }}
            QFrame#review {{ background: {T['card_2']}; border: 1px solid {T['border']}; border-radius: 10px; }}
            QProgressBar {{ background: {T['card_2']}; border: none; border-radius: 4px; max-height: 8px; }}
            QProgressBar::chunk {{ background: {T['warning']}; border-radius: 4px; }}
            """
        )
        self._build()

    def _card(self) -> tuple[QFrame, QVBoxLayout]:
        card = QFrame()
        card.setObjectName("card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(8)
        return card, layout

    def _label(self, text: str, name: str | None = None, wrap: bool = False) -> QLabel:
        label = QLabel(text)
        if name:
            label.setObjectName(name)
        label.setWordWrap(wrap)
        return label

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(22, 20, 22, 20)
        layout.setSpacing(14)
        scroll.setWidget(body)
        outer.addWidget(scroll)

        # Header
        header = QHBoxLayout()
        avatar = QLabel()
        avatar.setPixmap(qta.icon("fa5s.user-tie", color=T["accent"]).pixmap(44, 44))
        header.addWidget(avatar)
        names = QVBoxLayout()
        names.setSpacing(2)
        title = self._label(self.agent.get("full_name") or "Unknown agent")
        title.setStyleSheet(f"/*alty-raw*/ color: {T['text']}; font-size: 22px; font-weight: 800;")
        names.addWidget(title)
        names.addWidget(self._label(
            f"{self.agent.get('agent_id', '—')} · {self.agent.get('agent_location') or 'No location'}", "muted"))
        header.addLayout(names, 1)
        status = str(self.agent.get("status") or "—").upper()
        text_color, background = badge_colors(status)
        badge = self._label(status)
        badge.setStyleSheet(
            f"/*alty-raw*/ background: {background.name()}; color: {text_color.name()}; border-radius: 10px;"
            " padding: 5px 12px; font-size: 10px; font-weight: 800;")
        header.addWidget(badge, 0, Qt.AlignmentFlag.AlignTop)
        layout.addLayout(header)

        # Ratings
        ratings, ratings_layout = self._card()
        ratings_layout.addWidget(self._label("Ratings", "section"))
        grid = QGridLayout()
        grid.setHorizontalSpacing(24)
        self.client_rating_label = self._label(client_rating_text(self.agent))
        self.client_rating_label.setStyleSheet(
            f"/*alty-raw*/ color: {T['warning']}; font-size: 16px; font-weight: 800;")
        grid.addWidget(self._label("Client rating (from client reviews)", "faint"), 0, 0)
        grid.addWidget(self.client_rating_label, 1, 0)
        grid.addWidget(self._label("System rating (synced from Supabase)", "faint"), 0, 1)
        grid.addWidget(self._label(system_rating_text(self.agent.get("star_rating"))), 1, 1)
        ratings_layout.addLayout(grid)
        self.distribution = QGridLayout()
        self.distribution.setHorizontalSpacing(8)
        ratings_layout.addLayout(self.distribution)
        layout.addWidget(ratings)

        # Contact
        contact, contact_layout = self._card()
        contact_layout.addWidget(self._label("Contact & location", "section"))
        form = QFormLayout()
        form.setHorizontalSpacing(24)
        for label, value in (("Phone number", self.agent.get("phone_number")),
                             ("Location", self.agent.get("agent_location")),
                             ("Coordinates", f"{self.agent.get('latitude')}, {self.agent.get('longitude')}"
                              if self.agent.get("latitude") is not None else None)):
            form.addRow(self._label(label, "muted"), self._label(str(value or "—")))
        contact_layout.addLayout(form)
        layout.addWidget(contact)

        # Performance
        performance, perf_layout = self._card()
        perf_layout.addWidget(self._label("Performance", "section"))
        metrics = QGridLayout()
        metrics.setSpacing(10)
        values = (
            ("Assignments", self.agent.get("assignments_count", 0)),
            ("Transactions", self.agent.get("transactions_count", 0)),
            ("Completed sales", self.agent.get("completed_sales", 0)),
            ("Performance", percent(self.agent.get("performance_score"))),
            ("Total sales", money(self.agent.get("total_sales"))),
            ("Commission", money(self.agent.get("total_commission"))),
        )
        for index, (label, value) in enumerate(values):
            tile = QFrame()
            tile.setObjectName("review")
            tile_layout = QVBoxLayout(tile)
            tile_layout.setContentsMargins(12, 10, 12, 10)
            number = self._label(str(value))
            number.setStyleSheet(f"/*alty-raw*/ color: {T['text']}; font-size: 18px; font-weight: 800;")
            tile_layout.addWidget(number)
            tile_layout.addWidget(self._label(label, "faint"))
            metrics.addWidget(tile, index // 3, index % 3)
        perf_layout.addLayout(metrics)
        layout.addWidget(performance)

        # Client reviews
        reviews, self.reviews_layout = self._card()
        self.reviews_layout.addWidget(self._label("Client reviews", "section"))
        self.reviews_status = self._label("Loading client reviews…", "muted", wrap=True)
        self.reviews_layout.addWidget(self.reviews_status)
        layout.addWidget(reviews)
        layout.addStretch()
        # Closed with the window's own ✕ (or Esc); no separate Close button.

        self.load_reviews()

    def load_reviews(self) -> None:
        if self.api is None or not self.token:
            self.reviews_status.setText("Sign in to load client reviews.")
            return
        try:
            data = self.api.get_agent_reviews(str(self.agent.get("agent_id")), token=self.token)
        except Exception as exc:  # shown in the dialog, not hidden
            self.reviews_status.setText(f"Unable to load client reviews: {error_message(exc)}")
            return
        self.client_rating_label.setText(client_rating_text(data))
        total = int(data.get("review_count") or 0)
        for row, (star, count) in enumerate((data.get("distribution") or {}).items()):
            self.distribution.addWidget(self._label(f"{star} ★", "faint"), row, 0)
            bar = QProgressBar()
            bar.setTextVisible(False)
            bar.setMaximum(max(total, 1))
            bar.setValue(int(count))
            self.distribution.addWidget(bar, row, 1)
            self.distribution.addWidget(self._label(str(count), "faint"), row, 2)
        reviews = data.get("reviews") or []
        if not reviews:
            self.reviews_status.setText("No client reviews yet.")
            return
        self.reviews_status.setText(f"{total} review{'s' if total != 1 else ''} · most recent first")
        for review in reviews:
            card = QFrame()
            card.setObjectName("review")
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(12, 10, 12, 10)
            top = QHBoxLayout()
            rating = self._label(stars(review.get("rating")))
            rating.setStyleSheet(f"/*alty-raw*/ color: {T['warning']}; font-size: 14px;")
            top.addWidget(rating)
            top.addStretch()
            top.addWidget(self._label(self._date(review.get("updated_at") or review.get("created_at")), "faint"))
            card_layout.addLayout(top)
            if review.get("review"):
                card_layout.addWidget(self._label(f"“{review['review']}”", wrap=True))
            details = f"— {review.get('reviewer') or 'Verified client'} · verified client"
            if review.get("property_title"):
                details += f" · {review['property_title']}"
            card_layout.addWidget(self._label(details, "faint", wrap=True))
            self.reviews_layout.addWidget(card)

    @staticmethod
    def _date(value: Any) -> str:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).strftime("%b %d, %Y")
        except ValueError:
            return ""


# ---------------------------------------------------------------------------
# Agent Management page
# ---------------------------------------------------------------------------

COLUMNS = ["Agent ID", "Full Name", "Phone Number", "Location", "Client Rating", "System Rating",
           "Assignments", "Transactions", "Completed Sales", "Performance", "Status"]
CENTERED = {0, 6, 7, 8, 9, 10}


class AgentsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.agents: list[dict[str, Any]] = []
        self._build_ui()
        if self.token:
            self.load_agents()
        else:
            self.count_label.setText("Sign in to load agents.")

    @property
    def token(self) -> str | None:
        return self.controller.session.state.token if self.controller is not None else None

    # -- UI -----------------------------------------------------------------

    def _build_ui(self) -> None:
        self.setStyleSheet(
            f"""/*alty-raw*/
            QLabel#pageHeading {{ color: {T['text']}; font-size: 26px; font-weight: 800; }}
            QLabel#pageSub {{ color: {T['text_muted']}; font-size: 13px; }}
            QLabel#countLabel {{ color: {T['text_muted']}; font-size: 12px; font-weight: 600; }}
            QLabel#errorLabel {{ color: {T['danger']}; font-size: 12px; font-weight: 600; }}
            QLabel#hint {{ color: {T['text_faint']}; font-size: 11px; }}
            QPushButton#primary {{ background: {T['accent']}; color: {T['accent_ink']}; border: none;
                border-radius: 8px; padding: 8px 14px; font-weight: 700; }}
            QPushButton#primary:hover {{ background: {T['accent_hover']}; }}
            QPushButton#primary:disabled {{ background: {T['disabled']}; color: {T['text_faint']}; }}
            QTableWidget {{ font-size: 13px; }}
            QTableWidget::item:hover {{ background: {T['hover']}; }}
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(12)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = QLabel("Agent Management")
        title.setObjectName("pageHeading")
        subtitle = QLabel("Manage agent profiles, assignments, transactions, performance and client reviews.")
        subtitle.setObjectName("pageSub")
        subtitle.setWordWrap(True)
        titles.addWidget(title)
        titles.addWidget(subtitle)
        header.addLayout(titles, 1)

        self.sync_button = QPushButton("Sync from Supabase")
        self.sync_button.setIcon(qta.icon("fa5s.cloud-download-alt", color=T["text"]))
        self.sync_button.setToolTip("Copy the current Supabase agents table into the local database")
        self.sync_button.clicked.connect(self.sync_agents)
        header.addWidget(self.sync_button)
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(qta.icon("fa5s.sync-alt", color=T["text"]))
        self.refresh_button.setToolTip("Reload agents from the backend")
        self.refresh_button.clicked.connect(self.load_agents)
        header.addWidget(self.refresh_button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        filters.setSpacing(8)
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search agent name, Agent ID, phone, or location…")
        self.search_input.setClearButtonEnabled(True)
        self.search_input.addAction(qta.icon("fa5s.search", color=T["text_faint"]),
                                    QLineEdit.ActionPosition.LeadingPosition)
        self.search_input.setFixedHeight(38)
        self.search_input.textChanged.connect(self.filter_agents)
        filters.addWidget(self.search_input, 1)
        self.status_filter = QComboBox()
        self.status_filter.addItems(["All statuses", "Active", "Inactive"])
        self.status_filter.setFixedHeight(38)
        self.status_filter.currentIndexChanged.connect(self.filter_agents)
        filters.addWidget(self.status_filter)
        self.review_filter = QComboBox()
        self.review_filter.addItems(["Any reviews", "With client reviews", "No client reviews"])
        self.review_filter.setFixedHeight(38)
        self.review_filter.currentIndexChanged.connect(self.filter_agents)
        filters.addWidget(self.review_filter)
        layout.addLayout(filters)

        info = QHBoxLayout()
        self.count_label = QLabel("0 agents")
        self.count_label.setObjectName("countLabel")
        info.addWidget(self.count_label)
        info.addStretch()
        self.profile_button = QPushButton("View Profile")
        self.profile_button.setObjectName("primary")
        self.profile_button.setEnabled(False)
        self.profile_button.clicked.connect(self.open_selected_profile)
        hint = QLabel("Tip: double-click a row to open the profile")
        hint.setObjectName("hint")
        info.addWidget(hint)
        info.addWidget(self.profile_button)
        layout.addLayout(info)

        self.error_label = QLabel("")
        self.error_label.setObjectName("errorLabel")
        self.error_label.setWordWrap(True)
        self.error_label.hide()
        layout.addWidget(self.error_label)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.setSortingEnabled(True)
        self.table.setMouseTracking(True)
        self.table.verticalHeader().setVisible(False)
        self.table.verticalHeader().setDefaultSectionSize(40)
        self.table.setShowGrid(False)
        header_view = self.table.horizontalHeader()
        header_view.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        header_view.setStretchLastSection(True)
        header_view.setHighlightSections(False)
        self.table.cellDoubleClicked.connect(self.open_agent_profile)
        self.table.itemSelectionChanged.connect(
            lambda: self.profile_button.setEnabled(bool(self.table.selectedItems())))
        layout.addWidget(self.table, 1)

        self.empty_label = QLabel("No agents found.")
        self.empty_label.setObjectName("pageSub")
        self.empty_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.empty_label.hide()
        layout.addWidget(self.empty_label)

    # -- Data ---------------------------------------------------------------

    def _show_error(self, title: str, message: str) -> None:
        self.error_label.setText(message)
        self.error_label.show()
        QMessageBox.warning(self, title, message)  # themed by ui_polish

    def load_agents(self) -> None:
        if not self.token:
            self.count_label.setText("Sign in to load agents.")
            return
        self.refresh_button.setEnabled(False)
        self.count_label.setText("Loading agents…")
        self.error_label.hide()
        try:
            data = self.api.get_agents(token=self.token)
            if not isinstance(data, list):
                raise RuntimeError("The server returned an invalid agent list.")
            self.agents = data
            self.filter_agents()
        except Exception as exc:
            # No fallback data: show the real problem and an empty table.
            self.agents = []
            self.populate_table([])
            self.count_label.setText("Unable to load agent information.")
            self._show_error("Unable to load agent information", error_message(exc))
        finally:
            self.refresh_button.setEnabled(True)

    def sync_agents(self) -> None:
        if not self.token:
            self.count_label.setText("Sign in to synchronize agents.")
            return
        self.sync_button.setEnabled(False)
        self.count_label.setText("Synchronizing agents from Supabase…")
        try:
            result = self.api.sync_agents(token=self.token)
        except Exception as exc:
            self.count_label.setText("Agent sync failed.")
            self._show_error("Agent sync failed", error_message(exc))
            self.sync_button.setEnabled(True)
            return
        self.sync_button.setEnabled(True)
        self.load_agents()
        QMessageBox.information(
            self, "Agent sync complete",
            f"Supabase records: {result.get('total', 0)}\n"
            f"Inserted: {result.get('inserted', 0)}\n"
            f"Updated: {result.get('updated', 0)}\n"
            f"Skipped with errors: {result.get('errors', 0)}",
        )

    def filter_agents(self, *_args) -> None:
        search = self.search_input.text().strip().casefold()
        status = self.status_filter.currentText()
        reviews = self.review_filter.currentText()
        filtered = []
        for agent in self.agents:
            haystack = " ".join(str(agent.get(key) or "") for key in
                                ("agent_id", "full_name", "phone_number", "agent_location")).casefold()
            is_active = str(agent.get("status") or "").upper() == "ACTIVE"
            has_reviews = int(agent.get("review_count") or 0) > 0
            if search and search not in haystack:
                continue
            if status == "Active" and not is_active or status == "Inactive" and is_active:
                continue
            if reviews == "With client reviews" and not has_reviews or reviews == "No client reviews" and has_reviews:
                continue
            filtered.append(agent)
        self.populate_table(filtered)

    def populate_table(self, agents: list[dict[str, Any]]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(agents))
        for row, agent in enumerate(agents):
            status = str(agent.get("status") or "—").upper()
            cells = [
                SortItem(str(agent.get("agent_id") or "—")),
                SortItem(str(agent.get("full_name") or "—")),
                SortItem(str(agent.get("phone_number") or "—")),
                SortItem(str(agent.get("agent_location") or "—")),
                SortItem(client_rating_text(agent),
                         (_number(agent.get("client_rating")) or 0) * 1000 + int(agent.get("review_count") or 0)),
                SortItem(system_rating_text(agent.get("star_rating")), _number(agent.get("star_rating")) or 0),
                SortItem(str(agent.get("assignments_count", 0)), int(agent.get("assignments_count") or 0)),
                SortItem(str(agent.get("transactions_count", 0)), int(agent.get("transactions_count") or 0)),
                SortItem(str(agent.get("completed_sales", 0)), int(agent.get("completed_sales") or 0)),
                SortItem(percent(agent.get("performance_score")), _number(agent.get("performance_score")) or 0),
                SortItem(status),
            ]
            for column, item in enumerate(cells):
                if column in CENTERED:
                    item.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
                self.table.setItem(row, column, item)
            text_color, background = badge_colors(status)
            cells[10].setForeground(text_color)
            cells[10].setBackground(background)
            if not int(agent.get("review_count") or 0):
                cells[4].setForeground(badge_colors("UNAVAILABLE")[0])
            cells[0].setData(Qt.ItemDataRole.UserRole, agent)
        self.table.setSortingEnabled(True)
        self.table.resizeColumnsToContents()
        self.empty_label.setVisible(not agents)
        if self.agents and not agents:
            self.empty_label.setText("No agents match these filters.")
        else:
            self.empty_label.setText("No agents found.")
        total = len(self.agents)
        shown = f"{len(agents)} of {total}" if len(agents) != total else str(total)
        self.count_label.setText(f"{shown} {'agent' if total == 1 else 'agents'}")
        self.profile_button.setEnabled(False)

    # -- Profile ------------------------------------------------------------

    def open_selected_profile(self) -> None:
        rows = self.table.selectionModel().selectedRows()
        if rows:
            self.open_agent_profile(rows[0].row(), 0)

    def open_agent_profile(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        agent = item.data(Qt.ItemDataRole.UserRole) if item else None
        if agent:
            AgentProfileDialog(agent, self.api, self.token, self).exec()

    # Kept for callers of the previous API.
    rating_display = staticmethod(system_rating_text)
    format_percentage = staticmethod(percent)
