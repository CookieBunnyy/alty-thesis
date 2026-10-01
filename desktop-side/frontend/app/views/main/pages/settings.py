from __future__ import annotations

from PyQt6.QtCore import QSettings
from PyQt6.QtWidgets import QFormLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QMessageBox

from app import theme

from app.api.client import error_message
from app.views.main.pages._common import BUTTON_STYLE, DataPage, button, fill, table


class SettingsPage(DataPage):
    title = "System Settings"
    subtitle = ("Server configuration, storage, processing engines and synchronization state. "
                "Secrets are never shown.")

    def build(self) -> None:
        appearance = QGroupBox("Appearance")
        appearance_row = QHBoxLayout(appearance)
        caption = QLabel("Theme")
        caption.setMinimumWidth(110)
        appearance_row.addWidget(caption)
        self.theme_buttons = {}
        for mode, label, icon in (("dark", "Dark mode", "fa5s.moon"), ("light", "Light mode", "fa5s.sun")):
            option = button(label, icon)
            option.setCheckable(True)
            # Legacy colours are translated: #17310a -> accent, white -> ink.
            option.setStyleSheet(BUTTON_STYLE + "QPushButton:checked { background: #17310a; color: white; }")
            option.setChecked(theme.current_mode() == mode)
            option.clicked.connect(lambda _checked, m=mode: self.set_theme(m))
            appearance_row.addWidget(option)
            self.theme_buttons[mode] = option
        appearance_row.addStretch()
        note = QLabel("Applies immediately and is remembered on this computer.")
        note.setObjectName("themeNote")
        appearance_row.addWidget(note)
        self.layout_.addWidget(appearance)

        preferences = QGroupBox("Application preferences (this computer)")
        form = QFormLayout(preferences)
        self.api_url = QLineEdit(QSettings("Alty", "Desktop").value("api_url", self.api.base_url))
        save = button("Save", "fa5s.save")
        save.clicked.connect(self.save_preferences)
        form.addRow("API server URL", self.api_url)
        form.addRow("", save)
        self.layout_.addWidget(preferences)

        self.config = table(["Section", "Setting", "Value"])
        self.layout_.addWidget(self.config, 2)

        sync_box = QGroupBox("Synchronization with the central database (Supabase)")
        sync_layout = QFormLayout(sync_box)
        self.sync_summary = QLabel("—")
        self.sync_summary.setWordWrap(True)
        self.push_button = button("Push pending records", "fa5s.cloud-upload-alt", primary=True)
        self.push_button.clicked.connect(self.push)
        sync_layout.addRow(self.sync_summary)
        sync_layout.addRow(self.push_button)
        self.layout_.addWidget(sync_box)

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
        self.push_button.setVisible(self.role.casefold() in {"administrator", "general manager", "president"})
        self.status.setText(f"Connected to {self.api.base_url}")

    def set_theme(self, mode: str) -> None:
        for key, option in self.theme_buttons.items():
            option.setChecked(key == mode)
        if mode != theme.current_mode() and self.controller is not None:
            self.controller.apply_theme(mode)

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
