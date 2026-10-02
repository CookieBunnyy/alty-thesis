from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QComboBox, QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox, QSizePolicy, QWidget

from app import i18n, theme
from app.api.client import error_message
from app.i18n import tr
from app.views.main.pages._common import BUTTON_STYLE, DataPage, button, fill, table

ADMINISTRATOR = "administrator"


class SettingsPage(DataPage):
    """Everyone: appearance (dark/light) and language.
    Administrator only: server preferences, system configuration and sync."""

    def __init__(self, controller=None) -> None:
        # Instance titles so they follow the language chosen at runtime.
        self.title = tr("Settings")
        self.subtitle = tr("Choose your appearance and language.")
        super().__init__(controller)

    @property
    def is_admin(self) -> bool:
        return self.role.casefold() == ADMINISTRATOR

    def build(self) -> None:
        # ---- Appearance (everyone) ----
        appearance = QGroupBox(tr("Appearance"))
        appearance_row = QHBoxLayout(appearance)
        caption = QLabel(tr("Theme"))
        caption.setMinimumWidth(110)
        appearance_row.addWidget(caption)
        self.theme_buttons = {}
        for mode, label, icon in (("dark", "Dark mode", "fa5s.moon"), ("light", "Light mode", "fa5s.sun")):
            option = button(tr(label), icon)
            option.setCheckable(True)
            # Legacy colours are translated: #17310a -> accent, white -> ink.
            option.setStyleSheet(BUTTON_STYLE + "QPushButton:checked { background: #17310a; color: white; }")
            option.setChecked(theme.current_mode() == mode)
            option.clicked.connect(lambda _checked, m=mode: self.set_theme(m))
            appearance_row.addWidget(option)
            self.theme_buttons[mode] = option
        appearance_row.addStretch()
        note = QLabel(tr("Applies immediately and is remembered on this computer."))
        note.setObjectName("themeNote")
        appearance_row.addWidget(note)
        self.layout_.addWidget(appearance)

        # ---- Language (everyone) ----
        language = QGroupBox(tr("Language"))
        language_row = QHBoxLayout(language)
        language_caption = QLabel(tr("Language"))
        language_caption.setMinimumWidth(110)
        language_row.addWidget(language_caption)
        self.language_input = QComboBox()
        for code, name in i18n.LANGUAGES.items():
            self.language_input.addItem(name, code)
        self.language_input.setCurrentIndex(self.language_input.findData(i18n.current_language()))
        self.language_input.currentIndexChanged.connect(
            lambda _index: self.set_language(self.language_input.currentData()))
        language_row.addWidget(self.language_input)
        language_row.addStretch()
        language_note = QLabel(tr("Page contents stay in English; the menus, titles and this page follow your language."))
        language_note.setWordWrap(True)
        language_row.addWidget(language_note, 1)
        self.layout_.addWidget(language)

        # ---- Administrator only ----
        self.preferences = QGroupBox("Application preferences (this computer)")
        form = QFormLayout(self.preferences)
        self.api_url = QLineEdit(QSettings("Alty", "Desktop").value("api_url", self.api.base_url))
        save = button("Save", "fa5s.save")
        save.clicked.connect(self.save_preferences)
        form.addRow("API server URL", self.api_url)
        form.addRow("", save)
        self.layout_.addWidget(self.preferences)

        self.config = table(["Section", "Setting", "Value"])
        self.layout_.addWidget(self.config, 2)

        self.sync_box = QGroupBox("Synchronization with the central database (Supabase)")
        sync_layout = QFormLayout(self.sync_box)
        self.sync_summary = QLabel("—")
        self.sync_summary.setWordWrap(True)
        self.push_button = button("Push pending records", "fa5s.cloud-upload-alt", primary=True)
        self.push_button.clicked.connect(self.push)
        sync_layout.addRow(self.sync_summary)
        sync_layout.addRow(self.push_button)
        self.layout_.addWidget(self.sync_box)
        # Without the administrator table, keep the two groups at the top.
        self.filler = QWidget()
        self.filler.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        self.layout_.addWidget(self.filler, 1)
        self._apply_role()

    def _apply_role(self) -> None:
        """Hide (not just disable) the administrator sections for other roles."""
        admin = self.is_admin
        for widget in (self.preferences, self.config, self.sync_box, self.refresh_button):
            widget.setVisible(admin)
        self.filler.setVisible(not admin)

    def refresh(self) -> None:
        self._apply_role()
        if not self.is_admin:
            self.status.setText("")
            return
        super().refresh()

    def load(self) -> None:
        settings = self.api.get_system_settings(token=self.token)
        rows = []
        for section, values in settings.items():
            for key, value in values.items():
                if isinstance(value, dict):
                    value = ", ".join(f"{k}: {v}" for k, v in value.items())
                elif isinstance(value, list):
                    value = ", ".join(map(str, value))
                rows.append([section.title(), key.replace("_", " "), value])
        fill(self.config, rows)
        state = self.api.get_sync_status(token=self.token)
        lines = [f"Cloud sync {'enabled' if state['enabled'] else 'disabled / not configured'}."]
        for name, counts in state["counts"].items():
            lines.append(f"{name}: " + (", ".join(f"{k} {v}" for k, v in counts.items()) or "none"))
        self.sync_summary.setText("\n".join(lines))
        self.status.setText(f"Connected to {self.api.base_url}")

    def set_theme(self, mode: str) -> None:
        for key, option in self.theme_buttons.items():
            option.setChecked(key == mode)
        if mode != theme.current_mode() and self.controller is not None:
            self.controller.apply_theme(mode)

    def set_language(self, code: str | None) -> None:
        if code and code != i18n.current_language() and self.controller is not None:
            self.controller.apply_language(code)

    def save_preferences(self) -> None:
        QSettings("Alty", "Desktop").setValue("api_url", self.api_url.text().strip())
        QMessageBox.information(self, "Preferences saved",
                                "The API server URL is used the next time the application starts.")

    def push(self) -> None:
        try:
            report = self.api.push_sync(token=self.token)
        except Exception as exc:
            QMessageBox.warning(self, "Synchronization failed", error_message(exc))
            return
        lines = [report.get("reason") or "Push complete."]
        for table_name, stats in report.get("tables", {}).items():
            lines.append(f"{table_name}: pushed {stats['pushed']}, failed {stats['failed']}")
            lines += [f"   {error}" for error in stats["errors"][:5]]
        lines += report.get("warnings", [])
        QMessageBox.information(self, "Synchronization", "\n".join(lines))
        self.refresh()
