from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QInputDialog,
    QLineEdit,
    QMessageBox,
)

from app.api.client import error_message
from app.views.main.pages._common import DataPage, button, fill, fmt_date, table


class UserDialog(QDialog):
    def __init__(self, roles: list[str], user: dict | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit User" if user else "New User")
        self.setMinimumWidth(380)
        self.username = QLineEdit(user.get("username", "") if user else "")
        self.username.setEnabled(user is None)
        self.full_name = QLineEdit(user.get("full_name", "") if user else "")
        self.password = QLineEdit()
        self.password.setEchoMode(QLineEdit.EchoMode.Password)
        self.password.setPlaceholderText("At least 8 characters")
        self.role = QComboBox()
        self.role.addItems(roles)
        if user:
            self.role.setCurrentText(user.get("role", "Employee"))
        self.active = QCheckBox("Active")
        self.active.setChecked(user.get("is_active", True) if user else True)
        form = QFormLayout(self)
        form.addRow("Username", self.username)
        form.addRow("Full name", self.full_name)
        if user is None:
            form.addRow("Password", self.password)
        form.addRow("Role", self.role)
        form.addRow("", self.active)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def payload(self, creating: bool) -> dict:
        data = {"full_name": self.full_name.text().strip(), "role": self.role.currentText(),
                "is_active": self.active.isChecked()}
        if creating:
            data.update(username=self.username.text().strip(), password=self.password.text())
        return data


class UsersPage(DataPage):
    title = "User Management"
    subtitle = "Accounts, roles and access. Only administrators can create or change users."

    def build(self) -> None:
        self.users: list[dict] = []
        self.roles: list[str] = []
        self.new_button = button("New User", "fa5s.user-plus", primary=True)
        self.edit_button = button("Edit", "fa5s.user-edit")
        self.password_button = button("Reset Password", "fa5s.key")
        for widget, handler in ((self.new_button, self.create_user), (self.edit_button, self.edit_user),
                                (self.password_button, self.reset_password)):
            widget.clicked.connect(handler)
            self.actions.insertWidget(0, widget)
        self.table = table(["Username", "Full Name", "Role", "Active", "Last Login", "Created"])
        self.table.cellDoubleClicked.connect(lambda *_: self.edit_user())
        self.layout_.addWidget(self.table, 1)

    def load(self) -> None:
        admin = self.role.casefold() == "administrator"
        for widget in (self.new_button, self.edit_button, self.password_button):
            widget.setVisible(admin)
        self.users = self.api.get_users(token=self.token)
        self.roles = [role["name"] for role in self.api.get_roles(token=self.token)]
        fill(self.table, ([u["username"], u["full_name"], u["role"], "Yes" if u["is_active"] else "No",
                           fmt_date(u.get("last_login_at")), fmt_date(u.get("created_at"))]
                          for u in self.users), self.users)
        active = sum(1 for user in self.users if user["is_active"])
        self.status.setText(f"{len(self.users)} user(s), {active} active")

    def _selected(self) -> dict | None:
        item = self.table.item(self.table.currentRow(), 0) if self.table.currentRow() >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def create_user(self) -> None:
        dialog = UserDialog(self.roles, parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.create_user(dialog.payload(creating=True), token=self.token)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "User not created", error_message(exc))

    def edit_user(self) -> None:
        user = self._selected()
        if user is None or self.role.casefold() != "administrator":
            return
        dialog = UserDialog(self.roles, user, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self.api.update_user(user["id"], dialog.payload(creating=False), token=self.token)
            self.refresh()
            current = (self.controller.session.state.user or {}) if self.controller else {}
            if self.controller is not None and user["id"] == current.get("id"):
                self.controller.main_window.refresh_account()  # header card follows the edit
        except Exception as exc:
            QMessageBox.warning(self, "User not updated", error_message(exc))

    def reset_password(self) -> None:
        user = self._selected()
        if user is None:
            QMessageBox.information(self, "Reset password", "Select a user first.")
            return
        password, ok = QInputDialog.getText(self, "Reset password", f"New password for {user['username']}",
                                            QLineEdit.EchoMode.Password)
        if not ok or not password:
            return
        try:
            self.api.reset_user_password(user["id"], password, token=self.token)
            QMessageBox.information(self, "Reset password", "Password updated.")
        except Exception as exc:
            QMessageBox.warning(self, "Password not reset", error_message(exc))
