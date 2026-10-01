from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import httpx
import qtawesome as qta
from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtGui import QColor, QDesktopServices, QPixmap
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.theme import badge_colors
from app.api.client import ApiClient


# Fallback only; the live list comes from GET /api/v1/documents/types so the
# UI never offers a type the processing engine cannot handle.
DOCUMENT_TYPES: list[dict[str, str]] = [{"code": "AUTO", "label": "Auto-detect"}]
STATUSES = ["All Statuses", "Processing", "Success", "Failed", "Archived", "Superseded"]
MANAGER_ROLES = {"administrator", "general manager", "president", "filing manager"}


def _type_label(code: str | None) -> str:
    for item in DOCUMENT_TYPES:
        if item["code"] == code:
            return item["label"]
    return str(code or "—").replace("_", " ").title()


def processing_report(document: dict[str, Any]) -> str:
    """Plain-text account of what processing did (or why it failed)."""
    processing = document.get("processing") or {}
    status = document.get("status", "")
    lines = [
        "FILE STORAGE: stored" + (f" (cloud metadata: {document.get('sync_status')})"
                                  if document.get("sync_status") else ""),
        f"PROCESSING: {status}",
    ]
    if processing.get("stage"):
        lines.append(f"Stage: {processing['stage']}")
    if processing.get("error_reason"):
        lines.append(f"Reason: {processing['error_reason']}")
    extraction = processing.get("extraction") or {}
    if extraction:
        pages = f", OCR pages {extraction.get('ocr_pages')}" if extraction.get("ocr_pages") else ""
        lines.append(f"Extraction: {extraction.get('method')} from {extraction.get('source_format')}{pages}")
    classification = processing.get("classification") or {}
    if classification:
        lines.append(
            f"Classification: {processing.get('document_type') or '—'} "
            f"(detected {classification.get('detected_type') or 'nothing'}, "
            f"{classification.get('confidence')}: {classification.get('reason')})"
        )
    errors = (processing.get("validation_result") or {}).get("errors") or []
    if errors:
        lines.append("Validation errors:")
        lines += [f"  • {error.get('field')}: {error.get('message')}" for error in errors]
    for entity, match in (processing.get("matched_entities") or {}).items():
        lines.append(f"Matched {entity}: {match.get('id')} (by {match.get('matched_by')})")
    for label, key in (("Created", "created_records"), ("Updated", "updated_records")):
        if processing.get(key):
            lines.append(f"{label}: " + ", ".join(processing[key]))
    if processing.get("idempotent") and status == "SUCCESS":
        lines.append("No changes were needed — every record already existed.")
    for warning in processing.get("warnings") or []:
        lines.append(f"Warning: {warning}")
    for field, values in (processing.get("field_conflicts") or {}).items():
        lines.append(f"Conflicting values for {field}: {', '.join(values)}")
    fields = processing.get("extracted_fields") or {}
    if fields:
        lines.append("Extracted fields:")
        lines += [f"  {name}: {value}" for name, value in fields.items()]
    return "\n".join(lines)


def _error_text(error: Exception) -> str:
    if isinstance(error, httpx.HTTPStatusError):
        try:
            detail = error.response.json().get("detail", "")
            if isinstance(detail, dict):
                message = detail.get("message") or str(detail)
                existing = detail.get("existing_document") or {}
                if existing:
                    message += (
                        f"\n\nExisting: {existing.get('document_name', 'Document')}"
                        f"\nID: {existing.get('document_id', existing.get('id', ''))}"
                        f"\nUploaded: {existing.get('created_at', 'Unknown')}"
                        f"\nStatus: {existing.get('status', 'Unknown')}"
                    )
                return message
            return str(detail or f"Request failed (HTTP {error.response.status_code}).")
        except (ValueError, AttributeError):
            return f"Request failed (HTTP {error.response.status_code})."
    if isinstance(error, httpx.RequestError):
        return "Unable to connect to the server. Check that it is running and try again."
    return str(error) or "The document operation could not be completed."


class UploadDocumentDialog(QDialog):
    def __init__(self, folders: list[dict], parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Upload Document")
        self.setMinimumWidth(520)
        self.setStyleSheet(
            """
            QDialog {
                background-color: #f7f9f3;
                color: #17310a;
            }
            QLabel { color: #17310a; background: transparent; }
            QLineEdit, QComboBox, QTextEdit {
                background-color: #ffffff;
                color: #17240f;
                border: 1px solid #cbd6c1;
                border-radius: 6px;
                padding: 7px;
            }
            QLineEdit:focus, QComboBox:focus, QTextEdit:focus {
                border: 1px solid #6b8e52;
            }
            QPushButton {
                background-color: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QPushButton:hover { background-color: #dce8ce; }
            QPushButton#primaryAction {
                background-color: #17310a;
                color: #ffffff;
                border-color: #17310a;
            }
            QPushButton#primaryAction:hover { background-color: #285214; }
            """
        )
        self.file_path = QLineEdit()
        self.file_path.setReadOnly(True)
        choose_file = QPushButton("  Browse…")
        choose_file.setIcon(qta.icon("fa5s.folder-open", color="#486b2a"))
        choose_file.clicked.connect(self._choose_file)
        file_row = QHBoxLayout()
        file_row.addWidget(self.file_path, 1)
        file_row.addWidget(choose_file)

        self.name_input = QLineEdit()
        self.type_input = QComboBox()
        for item in DOCUMENT_TYPES:
            self.type_input.addItem(item["label"], item["code"])
            if item.get("processing"):
                self.type_input.setItemData(
                    self.type_input.count() - 1, item["processing"], Qt.ItemDataRole.ToolTipRole
                )
        self.folder_input = QComboBox()
        self.folder_input.addItem("Unfiled", None)
        self.folder_names: dict[int, str] = {}
        for folder in folders:
            self.folder_input.addItem(folder["name"], folder["id"])
            self.folder_names[int(folder["id"])] = folder["name"]
        hint = QLabel(
            "The document is stored, then processed automatically: fields are extracted "
            "(OCR for scanned files), matched to existing records, and properties, clients, "
            "transactions or agents are created or updated."
        )
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #65745b; font-size: 12px;")

        form = QFormLayout()
        form.addRow("File", file_row)
        form.addRow("Document name", self.name_input)
        form.addRow("Document type", self.type_input)
        form.addRow("Folder", self.folder_input)
        form.addRow("", hint)

        self.error_label = QLabel()
        self.error_label.setStyleSheet("color: #9b3030;")
        cancel = QPushButton("Cancel")
        cancel.setIcon(qta.icon("fa5s.times", color="#486b2a"))
        upload = QPushButton("Upload Document")
        upload.setIcon(qta.icon("fa5s.cloud-upload-alt", color="#ffffff"))
        upload.setObjectName("primaryAction")
        cancel.clicked.connect(self.reject)
        upload.clicked.connect(self.accept)
        actions = QHBoxLayout()
        actions.addStretch()
        actions.addWidget(cancel)
        actions.addWidget(upload)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.error_label)
        layout.addLayout(actions)

    def _choose_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose document", "",
            "Documents (*.pdf *.docx *.png *.jpg *.jpeg *.tif *.tiff *.bmp *.webp)",
        )
        if path:
            self.file_path.setText(path)
            if not self.name_input.text().strip():
                self.name_input.setText(Path(path).name)

    def values(self) -> tuple[str, dict[str, Any]]:
        payload: dict[str, Any] = {
            "document_name": self.name_input.text().strip() or Path(self.file_path.text()).name,
            "document_type": self.type_input.currentData() or "AUTO",
            "folder_id": self.folder_input.currentData(),
        }
        return self.file_path.text(), payload


class DocumentDetailsDialog(QDialog):
    def __init__(
        self,
        document: dict[str, Any],
        api: ApiClient,
        token: str | None,
        role: str,
        folders: list[dict[str, Any]],
        refresh: Any,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.document = document
        self.api = api
        self.token = token
        self.role = role.casefold()
        self.folders = folders
        self.refresh = refresh
        self.setWindowTitle("Document Details")
        self.setMinimumSize(600, 540)
        self.setStyleSheet(
            """
            QDialog { background-color: #f7f9f3; color: #17310a; }
            QLabel { color: #17310a; background: transparent; }
            QPushButton {
                background-color: #e7eedc;
                color: #17310a;
                border: 1px solid #cbd8be;
                border-radius: 6px;
                padding: 7px 11px;
            }
            QPushButton:hover { background-color: #dce8ce; }
            QPushButton:pressed { background-color: #cfddc1; }
            """
        )

        title = QLabel(document.get("document_name", "Document"))
        title.setStyleSheet("font-size: 20px; font-weight: 700; color: #17240f;")
        detail_form = QFormLayout()
        extracted_fields = self.document.get("extracted_fields") or {}
        details = [
            ("Document ID", "document_id"),
            ("Type", "document_type_label"),
            ("Folder", "folder_name"),
            ("Property", "property_listing_title"),
            ("Listing ID", "property_listing_external_id"),
            ("Transaction", "transaction_reference"),
            ("Transaction Type", "transaction_type"),
            ("Transaction Date", "transaction_date"),
            ("Buyer / Seller", "related_party_name"),
            ("Uploaded by", "uploaded_by_name"),
            ("Upload date", "created_at"),
            ("File type", "mime_type"),
            ("File size", "file_size"),
            ("Version", "version"),
            ("Processing", "status"),
            ("Extraction", "extraction_method"),
            ("Last updated", "updated_at"),
        ]
        document = {**document, "document_type_label": _type_label(document.get("document_type"))}
        for label, key in details:
            value = document.get(key)
            if key == "property_listing_title":
                value = value or extracted_fields.get("property_title")
            elif key == "property_listing_external_id":
                value = value or extracted_fields.get("listing_id")
            elif key == "transaction_reference":
                value = (
                    value
                    or extracted_fields.get("transaction_id")
                    or extracted_fields.get("transaction_type")
                )
            elif key == "transaction_type":
                value = extracted_fields.get("transaction_type")
            elif key == "transaction_date":
                value = extracted_fields.get("transaction_date")
            elif key == "related_party_name":
                value = value or extracted_fields.get("full_name")
            if key == "file_size":
                value = self._format_size(value)
            detail_form.addRow(label, QLabel(str(value or "—")))
        description = QLabel(document.get("description") or "—")
        description.setWordWrap(True)
        detail_form.addRow("Description", description)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setStyleSheet("color: #9b3030;")
        if document.get("status") == "FAILED":
            processing = document.get("processing") or {}
            self.message.setText(
                f"FAILED at {processing.get('stage') or document.get('processing_stage') or '—'}: "
                f"{document.get('processing_error') or processing.get('error_reason') or 'no reason recorded'}"
            )
        self.buttons: dict[str, QPushButton] = {}
        actions = QHBoxLayout()
        for key, text, icon_name, callback in (
            ("preview", "Preview", "fa5s.eye", self.preview),
            ("download", "Download", "fa5s.download", self.download),
            ("print", "Print", "fa5s.print", self.print_document),
            ("report", "Processing Report", "fa5s.clipboard-list", self.show_processing_report),
            ("reprocess", "Reprocess", "fa5s.redo", self.reprocess),
            ("archive", "Archive", "fa5s.archive", lambda: self._change_status("archive")),
            ("version", "Replace Version", "fa5s.file-upload", self.replace_version),
            ("history", "Version History", "fa5s.history", self.show_version_history),
            ("move", "Move / Rename", "fa5s.folder-open", self.classify_or_move),
            ("delete", "Delete", "fa5s.trash-alt", self.delete_document),
        ):
            button = QPushButton(text)
            button.setIcon(qta.icon(icon_name, color="#17310a"))
            button.clicked.connect(callback)
            actions.addWidget(button)
            self.buttons[key] = button
        close = QPushButton("Close")
        close.setIcon(qta.icon("fa5s.times-circle", color="#486b2a"))
        close.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.addWidget(title)
        layout.addLayout(detail_form)
        layout.addWidget(self.message)
        layout.addLayout(actions)
        layout.addWidget(close, alignment=Qt.AlignmentFlag.AlignRight)
        self._apply_permissions()

    @staticmethod
    def _format_size(size: Any) -> str:
        try:
            size = int(size)
        except (TypeError, ValueError):
            return "—"
        return f"{size / 1024:.1f} KB" if size < 1024 * 1024 else f"{size / (1024 * 1024):.2f} MB"

    def _apply_permissions(self) -> None:
        manager = self.role in MANAGER_ROLES
        status = self.document.get("status", "")
        for key in ("reprocess", "archive", "version", "move", "delete"):
            self.buttons[key].setVisible(manager)
        self.buttons["reprocess"].setVisible(manager and status in {"FAILED", "SUCCESS"})
        if status == "ARCHIVED":
            archive = self.buttons["archive"]
            archive.setText("Restore")
            archive.clicked.disconnect()
            archive.clicked.connect(lambda: self._change_status("restore"))
            self.buttons["version"].setVisible(False)
        if status == "SUPERSEDED":
            for key in ("reprocess", "archive", "version"):
                self.buttons[key].setVisible(False)

    def show_processing_report(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Processing Report")
        dialog.resize(640, 520)
        text = QTextEdit()
        text.setReadOnly(True)
        text.setPlainText(processing_report(self.document))
        layout = QVBoxLayout(dialog)
        layout.addWidget(text)
        try:
            events = self.api.get_document_audit(self.document["document_id"], token=self.token)
            audit = QTextEdit()
            audit.setReadOnly(True)
            audit.setMaximumHeight(150)
            audit.setPlainText("\n".join(
                f"{event.get('created_at', '')[:19]}  v{event.get('version')}  "
                f"{event.get('event_type')}  by {event.get('actor')}"
                for event in events
            ))
            layout.addWidget(QLabel("Processing audit"))
            layout.addWidget(audit)
        except Exception:
            pass
        dialog.exec()

    def reprocess(self) -> None:
        if QMessageBox.question(
            self, "Reprocess document",
            "Run processing again on the stored file? Records that already exist are "
            "matched, not duplicated.",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            result = self.api.reprocess_document(self.document["document_id"], token=self.token)
            self.document.update(result)
            self.refresh()
            QMessageBox.information(self, "Reprocessed", processing_report(result))
            self.accept()
        except Exception as exc:
            self.message.setText(_error_text(exc))

    def delete_document(self) -> None:
        answer = QMessageBox.question(
            self,
            "Delete document",
            "Delete this document and all of its versions from the repository and storage? This cannot be undone.",
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.delete_document(self.document["document_id"], token=self.token)
            self.refresh()
            self.accept()
        except Exception as exc:
            self.message.setText(_error_text(exc))

    def _change_status(self, action: str) -> None:
        messages = {
            "archive": "Archive this document? Records it created are kept.",
            "restore": "Restore this document to its last processing status?",
        }
        if QMessageBox.question(self, "Confirm action", messages[action]) != QMessageBox.StandardButton.Yes:
            return
        try:
            result = getattr(self.api, f"{action}_document")(self.document["document_id"], token=self.token)
            self.document.update(result)
            self.message.setStyleSheet("color: #294c16;")
            self.message.setText(f"Document status: {result.get('status', '').replace('_', ' ').title()}")
            self.refresh()
        except Exception as exc:
            self.message.setText(_error_text(exc))

    def _download_to_temp(self, version: int | None = None) -> str:
        content, _content_type, _disposition = self.api.download_document(
            self.document["document_id"], token=self.token, version=version
        )
        return self._write_temp(content)

    def _write_temp(self, content: bytes) -> str:
        suffix = Path(self.document.get("document_name") or "document").suffix
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as temporary:
            temporary.write(content)
            return temporary.name

    def preview(self) -> None:
        try:
            content, content_type, _ = self.api.download_document(
                self.document["document_id"], token=self.token
            )
            if content_type.startswith("image/"):
                pixmap = QPixmap()
                if pixmap.loadFromData(content):
                    preview = QDialog(self)
                    preview.setWindowTitle("Document Preview")
                    image = QLabel()
                    image.setPixmap(pixmap.scaled(
                        1000, 760,
                        Qt.AspectRatioMode.KeepAspectRatio,
                        Qt.TransformationMode.SmoothTransformation,
                    ))
                    layout = QVBoxLayout(preview)
                    layout.addWidget(image)
                    preview.exec()
                    return
            local_path = self._write_temp(content)
            if content_type == "application/pdf" or local_path.lower().endswith(".pdf"):
                try:
                    from PyQt6.QtPdf import QPdfDocument
                    from PyQt6.QtPdfWidgets import QPdfView

                    preview = QDialog(self)
                    preview.setWindowTitle("PDF Preview")
                    preview.resize(1000, 760)
                    pdf_document = QPdfDocument(preview)
                    pdf_document.load(local_path)
                    if pdf_document.pageCount() > 0:
                        viewer = QPdfView(preview)
                        viewer.setDocument(pdf_document)
                        layout = QVBoxLayout(preview)
                        layout.addWidget(viewer)
                        preview.exec()
                        return
                except Exception:
                    pass
            opened = QDesktopServices.openUrl(QUrl.fromLocalFile(local_path))
            if not opened:
                QMessageBox.information(
                    self,
                    "Preview unavailable",
                    "This format cannot be previewed here. Use Download to save or open it.",
                )
        except Exception as exc:
            QMessageBox.warning(self, "Preview unavailable", _error_text(exc))

    def download(self, version: int | None = None) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save document", self.document.get("document_name", "document")
        )
        if not path:
            return
        try:
            content, _content_type, _ = self.api.download_document(
                self.document["document_id"], token=self.token, version=version
            )
            Path(path).write_bytes(content)
            self.message.setStyleSheet("color: #294c16;")
            self.message.setText(f"Saved to {path}")
        except Exception as exc:
            self.message.setText(_error_text(exc))

    def print_document(self) -> None:
        try:
            local_path = self._download_to_temp()
            if hasattr(os, "startfile"):
                os.startfile(local_path, "print")
            elif not QDesktopServices.openUrl(QUrl.fromLocalFile(local_path)):
                raise RuntimeError("No application is available to open this document for printing.")
        except Exception as exc:
            QMessageBox.warning(self, "Print unavailable", _error_text(exc))

    def show_version_history(self) -> None:
        from PyQt6.QtWidgets import QInputDialog

        try:
            versions = self.api.get_document_versions(
                self.document["document_id"], token=self.token
            )
            labels = [
                f"Version {item['version']} | {item.get('status', '')} | {item.get('created_at', '')}"
                for item in versions
            ]
            selected, accepted = QInputDialog.getItem(
                self, "Version History", "Select a version to download", labels, 0, False
            )
            if accepted:
                selected_version = versions[labels.index(selected)]["version"]
                self.download(version=selected_version)
        except Exception as exc:
            QMessageBox.warning(self, "Version history unavailable", _error_text(exc))

    def classify_or_move(self) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle("Classify or Move Document")
        dialog.setStyleSheet(
            """
            QDialog { background-color: #f7f9f3; color: #17310a; }
            QLabel { color: #17310a; background: transparent; }
            QComboBox, QTextEdit {
                background: #ffffff; color: #17240f;
                border: 1px solid #cbd6c1; border-radius: 6px; padding: 7px;
            }
            QComboBox:focus, QTextEdit:focus { border: 1px solid #6b8e52; }
            QPushButton {
                background: #e7eedc; color: #17310a;
                border: 1px solid #cbd8be; border-radius: 6px; padding: 7px 12px;
            }
            QPushButton:hover { background: #dce8ce; }
            """
        )
        name_input = QLineEdit(self.document.get("document_name") or "")
        folder_input = QComboBox()
        folder_input.addItem("Unfiled", None)
        for folder in self.folders:
            if not folder.get("is_archived"):
                folder_input.addItem(folder["name"], folder["id"])
        folder_input.setCurrentIndex(max(folder_input.findData(self.document.get("folder_id")), 0))
        description_input = QTextEdit()
        description_input.setPlainText(self.document.get("description") or "")
        description_input.setMaximumHeight(100)
        form = QFormLayout()
        form.addRow("Document name", name_input)
        form.addRow("Folder", folder_input)
        form.addRow("Description", description_input)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout = QVBoxLayout(dialog)
        layout.addLayout(form)
        layout.addWidget(buttons)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            result = self.api.update_document(
                self.document["document_id"],
                {
                    "document_name": name_input.text().strip() or self.document.get("document_name"),
                    "folder_id": folder_input.currentData(),
                    "description": description_input.toPlainText().strip() or None,
                },
                token=self.token,
            )
            self.document.update(result)
            self.refresh()
            self.message.setStyleSheet("color: #294c16;")
            self.message.setText("Document details saved.")
        except Exception as exc:
            self.message.setText(_error_text(exc))

    def replace_version(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Choose replacement version")
        if not path:
            return
        try:
            result = self.api.create_document_version(
                self.document["document_id"],
                path,
                {
                    "document_name": self.document.get("document_name"),
                    "folder_id": self.document.get("folder_id"),
                    "description": self.document.get("description"),
                },
                token=self.token,
            )
            self.document.update(result)
            self.refresh()
            QMessageBox.information(
                self, "Version created",
                f"Saved as version {result['version']}.\n\n{processing_report(result)}",
            )
        except Exception as exc:
            QMessageBox.warning(self, "Replacement failed", _error_text(exc))


class DocumentsPage(QWidget):
    def __init__(self, controller=None) -> None:
        super().__init__()
        self.controller = controller
        self.api = ApiClient()
        self.documents: list[dict[str, Any]] = []
        self.folders: list[dict[str, Any]] = []
        self._build_ui()
        if self.token:
            self.refresh()
        else:
            self.status_message.setText("Sign in to load the document repository.")

    @property
    def token(self) -> str | None:
        if self.controller is None:
            return None
        return self.controller.session.state.token

    @property
    def role(self) -> str:
        if self.controller is None:
            return "Employee"
        return self.controller.session.state.role

    def _build_ui(self) -> None:
        self.setStyleSheet(
            """
            QWidget { color: #17240f; }
            QFrame#repositoryPanel { background: #f7f9f3; border: 1px solid #dfe7d5; border-radius: 8px; }
            QLineEdit, QComboBox, QTextEdit { background: white; border: 1px solid #cbd6c1; border-radius: 5px; padding: 7px; }
            QPushButton { background: #e7eedc; color: #17310a; border: 1px solid #d1ddc4; border-radius: 5px; padding: 8px 12px; }
            QPushButton:hover { background: #dce8ce; }
            QPushButton#primaryAction { background: #17310a; color: white; border-color: #17310a; }
            QHeaderView::section { background: #eef3e5; color: #526449; padding: 7px; border: none; font-weight: 700; }
            QTableWidget { background: white; border: 1px solid #dfe7d5; gridline-color: #e8ede3; }
            QTreeWidget {
                background: #ffffff;
                border: none;
                outline: none;
                padding: 4px;
            }
            QTreeWidget::item {
                color: #314329;
                padding: 5px 6px;
                margin: 1px 0px;
                border-radius: 5px;
            }
            QTreeWidget::item:hover {
                background: #edf3e7;
            }
            QTreeWidget::item:selected {
                background: #d6e8c9;
                color: #17310a;
                font-weight: 700;
                border: 1px solid #b8d0a8;
            }
            QTableWidget::item:selected {
                background: #d6e8c9;
                color: #17310a;
            }
            """
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 16, 18, 18)
        layout.setSpacing(12)

        header = QHBoxLayout()
        header.setSpacing(8)
        subtitle = QLabel(
            "Upload documents to store them and automatically update properties, clients, "
            "transactions and agents. Failed documents show the stage and reason."
        )
        subtitle.setStyleSheet("color: #65745b; font-size: 13px; font-weight: 600;")
        header.addWidget(subtitle, 1)
        self.upload_button = QPushButton("Upload Document")
        self.upload_button.setIcon(qta.icon("fa5s.cloud-upload-alt", color="#ffffff"))
        self.upload_button.setObjectName("primaryAction")
        self.new_folder_button = QPushButton("New Folder")
        self.new_folder_button.setIcon(qta.icon("fa5s.folder-plus", color="#17310a"))
        self.refresh_button = QPushButton("Refresh")
        self.refresh_button.setIcon(qta.icon("fa5s.sync-alt", color="#17310a"))
        self.archive_button = QPushButton("Archive Selected")
        self.archive_button.setIcon(qta.icon("fa5s.archive", color="#17310a"))
        for button in (self.upload_button, self.new_folder_button, self.refresh_button, self.archive_button):
            header.addWidget(button)
        layout.addLayout(header)

        filters = QHBoxLayout()
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search filename, type, transaction, property, buyer / seller...")
        self.type_filter = QComboBox()
        self.type_filter.addItem("All Types", None)
        self.status_filter = QComboBox()
        self.status_filter.addItems(STATUSES)
        self.folder_filter = QComboBox()
        self.folder_filter.addItem("All Folders", None)
        filters.addWidget(self.search_input, 1)
        filters.addWidget(self.type_filter)
        filters.addWidget(self.status_filter)
        filters.addWidget(self.folder_filter)
        layout.addLayout(filters)

        split = QSplitter(Qt.Orientation.Horizontal)
        folder_panel = QFrame()
        folder_panel.setObjectName("repositoryPanel")
        folder_layout = QVBoxLayout(folder_panel)
        folder_header = QHBoxLayout()
        folder_icon = QLabel()
        folder_icon.setPixmap(qta.icon("fa5s.folder", color="#17310a").pixmap(16, 16))
        folder_title = QLabel("Folders")
        folder_title.setStyleSheet("font-weight: 700; font-size: 14px; color: #17310a;")
        folder_header.addWidget(folder_icon)
        folder_header.addWidget(folder_title)
        folder_header.addStretch()
        self.folder_tree = QTreeWidget()
        self.folder_tree.setIndentation(18)
        self.folder_tree.setAnimated(True)
        self.folder_tree.setUniformRowHeights(False)
        self.folder_tree.setHeaderHidden(True)
        self.folder_tree.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        folder_layout.addLayout(folder_header)
        folder_layout.addWidget(self.folder_tree)
        split.addWidget(folder_panel)

        table_panel = QFrame()
        table_panel.setObjectName("repositoryPanel")
        table_layout = QVBoxLayout(table_panel)
        self.status_message = QLabel("Connect to the backend to load documents.")
        self.status_message.setWordWrap(True)
        self.status_message.setStyleSheet("color: #65745b;")
        self.table = QTableWidget(0, 12)
        self.table.setHorizontalHeaderLabels([
            "Document ID", "Document Name", "Document Type", "Folder", "Property",
            "Transaction", "Related Party", "Uploaded By", "Date Uploaded", "Version",
            "Status", "File Size",
        ])
        self.table.setSortingEnabled(True)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QTableWidget.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        table_layout.addWidget(self.status_message)
        table_layout.addWidget(self.table)
        split.addWidget(table_panel)
        split.setStretchFactor(0, 1)
        split.setStretchFactor(1, 4)
        layout.addWidget(split, 1)

        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(350)
        self.search_timer.timeout.connect(self._load_documents)
        self.search_input.textChanged.connect(lambda _text: self.search_timer.start())
        self.type_filter.currentIndexChanged.connect(self._load_documents)
        self.status_filter.currentIndexChanged.connect(self._load_documents)
        self.folder_filter.currentIndexChanged.connect(self._load_documents)
        self.folder_tree.itemSelectionChanged.connect(self._folder_selected)
        self.folder_tree.customContextMenuRequested.connect(self._folder_menu)
        self.table.cellDoubleClicked.connect(self._open_selected_document)
        self.upload_button.clicked.connect(self.upload_document)
        self.new_folder_button.clicked.connect(self.create_folder)
        self.refresh_button.clicked.connect(self.refresh)
        self.archive_button.clicked.connect(self.archive_selected)

    def refresh(self) -> None:
        if not self.token:
            self.status_message.setText("Sign in to load the document repository.")
            return
        self.refresh_button.setEnabled(False)
        self.status_message.setText("Loading documents and folders…")
        try:
            self._load_types()
            self.folders = self.api.get_folders(token=self.token)
            self._populate_folder_controls()
            self._load_documents()
        except Exception as exc:
            self.status_message.setText(_error_text(exc))
            self.documents = []
            self._populate_table([])
        finally:
            self.refresh_button.setEnabled(True)

    def _load_types(self) -> None:
        global DOCUMENT_TYPES
        types = self.api.get_document_types(token=self.token)
        if types:
            DOCUMENT_TYPES = types
        current = self.type_filter.currentData()
        self.type_filter.blockSignals(True)
        self.type_filter.clear()
        self.type_filter.addItem("All Types", None)
        for item in DOCUMENT_TYPES:
            if item["code"] != "AUTO":
                self.type_filter.addItem(item["label"], item["code"])
        self.type_filter.setCurrentIndex(max(self.type_filter.findData(current), 0))
        self.type_filter.blockSignals(False)

    def _populate_folder_controls(self) -> None:
        current = self.folder_filter.currentData()
        self.folder_filter.blockSignals(True)
        self.folder_filter.clear()
        self.folder_filter.addItem("All Folders", None)
        for folder in self.folders:
            if not folder.get("is_archived"):
                self.folder_filter.addItem(folder["name"], folder["id"])
        index = self.folder_filter.findData(current)
        self.folder_filter.setCurrentIndex(max(index, 0))
        self.folder_filter.blockSignals(False)
        self.folder_tree.clear()
        items: dict[int, QTreeWidgetItem] = {}
        for folder in self.folders:
            if folder.get("is_archived"):
                continue
            item = QTreeWidgetItem([folder["name"]])
            item.setData(0, Qt.ItemDataRole.UserRole, folder["id"])
            item.setIcon(0, qta.icon("fa5s.folder", color="#17310a"))
            items[int(folder["id"])] = item
        for folder in self.folders:
            if folder.get("is_archived"):
                continue
            item = items[int(folder["id"])]
            parent = items.get(folder.get("parent_id"))
            (parent.addChild(item) if parent else self.folder_tree.addTopLevelItem(item))
        self.folder_tree.expandAll()

    def _folder_selected(self) -> None:
        selected = self.folder_tree.selectedItems()
        if not selected:
            return
        folder_id = selected[0].data(0, Qt.ItemDataRole.UserRole)
        index = self.folder_filter.findData(folder_id)
        if index >= 0:
            self.folder_filter.setCurrentIndex(index)

    def _load_documents(self, *_args: Any) -> None:
        params: dict[str, Any] = {}
        search = self.search_input.text().strip()
        document_type = self.type_filter.currentData()
        status = self.status_filter.currentText()
        folder_id = self.folder_filter.currentData()
        if search:
            params["search"] = search
        if document_type:
            params["document_type"] = document_type
        if status != "All Statuses":
            params["status"] = status.upper().replace(" ", "_")
        if folder_id is not None:
            params["folder_id"] = folder_id
        try:
            self.documents = self.api.get_documents(token=self.token, params=params)
            self._populate_table(self.documents)
            counts: dict[str, int] = {}
            for document in self.documents:
                counts[document.get("status", "")] = counts.get(document.get("status", ""), 0) + 1
            self.status_message.setText(
                f"{len(self.documents)} document(s)  ·  "
                + "  ·  ".join(f"{status.title()}: {count}" for status, count in sorted(counts.items()))
            )
        except Exception as exc:
            self.status_message.setText(_error_text(exc))

    def _populate_table(self, documents: list[dict[str, Any]]) -> None:
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(documents))
        for row, document in enumerate(documents):
            values = [
                document.get("document_id"),
                document.get("document_name"),
                _type_label(document.get("document_type")),
                document.get("folder_name"),
                document.get("property_listing_title")
                or document.get("property_name")
                or document.get("property_listing_external_id")
                or document.get("property_listing_id")
                or document.get("property_id"),
                document.get("transaction_reference") or document.get("transaction_id"),
                document.get("related_party_name"),
                document.get("uploaded_by_name") or document.get("uploaded_by"),
                document.get("created_at"),
                document.get("version"),
                document.get("status"),
                self._format_size(document.get("file_size")),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(str(value if value is not None else "—"))
                if column == 0:
                    item.setData(Qt.ItemDataRole.UserRole, document)
                if column == 10 and document.get("status") == "FAILED":
                    item.setToolTip(
                        f"{document.get('processing_stage')}: {document.get('processing_error')}"
                    )
                if column == 10:
                    colors = {
                        "PROCESSING": "#1d6384",
                        "SUCCESS": "#294c16",
                        "FAILED": "#9b3030",
                        "PENDING_REVIEW": "#9a6a13",
                        "CONFIRMED": "#294c16",
                        "ARCHIVED": "#65745b",
                        "REJECTED": "#9b3030",
                        "DUPLICATE": "#8b4c85",
                    }
                    _text, _bg = badge_colors(document.get("status"))
                    item.setForeground(_text)
                    item.setBackground(_bg)
                self.table.setItem(row, column, item)
        self.table.setSortingEnabled(True)

    @staticmethod
    def _format_size(size: Any) -> str:
        try:
            size = int(size)
        except (TypeError, ValueError):
            return "—"
        if size < 1024:
            return f"{size} B"
        if size < 1024 * 1024:
            return f"{size / 1024:.1f} KB"
        return f"{size / (1024 * 1024):.2f} MB"

    def _selected_document(self) -> dict[str, Any] | None:
        row = self.table.currentRow()
        item = self.table.item(row, 0) if row >= 0 else None
        return item.data(Qt.ItemDataRole.UserRole) if item else None

    def _open_selected_document(self, row: int, _column: int) -> None:
        item = self.table.item(row, 0)
        if item is None:
            return
        document = item.data(Qt.ItemDataRole.UserRole)
        if not document:
            return
        dialog = DocumentDetailsDialog(
            document, self.api, self.token, self.role, self.folders, self.refresh, self
        )
        dialog.exec()

    def upload_document(self) -> None:
        dialog = UploadDocumentDialog(self.folders, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            path, payload = dialog.values()
            if not path or not Path(path).is_file():
                raise ValueError("Choose a readable file to upload.")
            try:
                result = self.api.upload_document(path, payload, token=self.token)
            except httpx.HTTPStatusError as exc:
                detail = exc.response.json().get("detail", {})
                if exc.response.status_code != 409 or not isinstance(detail, dict):
                    raise
                existing = detail.get("existing_document", {})
                prompt = (
                    "Possible duplicate document detected.\n\n"
                    f"Existing document: {existing.get('document_name', 'Unknown')}\n"
                    f"ID: {existing.get('document_id', existing.get('id', 'Unknown'))}\n"
                    f"Uploaded: {existing.get('created_at', 'Unknown')}\n"
                    f"Status: {existing.get('status', 'Unknown')}\n\n"
                    "Upload another copy anyway? It is processed again; records that already "
                    "exist are matched, not duplicated."
                )
                if QMessageBox.question(self, "Possible duplicate", prompt) != QMessageBox.StandardButton.Yes:
                    return
                payload["allow_duplicate"] = True
                result = self.api.upload_document(path, payload, token=self.token)
            self.refresh()
            box = QMessageBox(self)
            box.setIcon(QMessageBox.Icon.Information if result.get("status") == "SUCCESS"
                        else QMessageBox.Icon.Warning)
            box.setWindowTitle("Document stored — processing " + str(result.get("status", "")).lower())
            box.setText(processing_report(result).split("\nExtracted fields:")[0])
            box.setDetailedText(processing_report(result))
            box.exec()
        except Exception as exc:
            QMessageBox.warning(self, "Upload failed", _error_text(exc))

    def create_folder(self) -> None:
        name, accepted = self._ask_folder_name()
        if not accepted:
            return
        selected = self.folder_tree.selectedItems()
        parent_id = selected[0].data(0, Qt.ItemDataRole.UserRole) if selected else None
        try:
            self.api.create_folder(name, parent_id=parent_id, token=self.token)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Folder could not be created", _error_text(exc))

    def _ask_folder_name(self) -> tuple[str, bool]:
        from PyQt6.QtWidgets import QInputDialog

        name, accepted = QInputDialog.getText(self, "New Folder", "Folder name")
        return name.strip(), accepted and bool(name.strip())

    def _folder_menu(self, position: Any) -> None:
        item = self.folder_tree.itemAt(position)
        if item is None:
            return
        menu = QMenu(self)
        rename = menu.addAction("Rename")
        archive = menu.addAction("Archive folder")
        chosen = menu.exec(self.folder_tree.viewport().mapToGlobal(position))
        folder_id = item.data(0, Qt.ItemDataRole.UserRole)
        if chosen == rename:
            from PyQt6.QtWidgets import QInputDialog

            name, accepted = QInputDialog.getText(self, "Rename Folder", "Folder name", text=item.text(0))
            if accepted and name.strip():
                self._update_folder(folder_id, {"name": name.strip()})
        elif chosen == archive:
            if QMessageBox.question(self, "Archive folder", f"Archive '{item.text(0)}'? Documents remain available.") == QMessageBox.StandardButton.Yes:
                self._update_folder(folder_id, {"is_archived": True})

    def _update_folder(self, folder_id: int, payload: dict[str, Any]) -> None:
        try:
            self.api.update_folder(folder_id, payload, token=self.token)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Folder could not be updated", _error_text(exc))

    def archive_selected(self) -> None:
        document = self._selected_document()
        if document is None:
            QMessageBox.information(self, "Archive document", "Select a document first.")
            return
        if QMessageBox.question(
            self,
            "Archive document",
            f"Archive '{document.get('document_name', 'this document')}'?",
        ) != QMessageBox.StandardButton.Yes:
            return
        try:
            self.api.archive_document(document["document_id"], token=self.token)
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Archive failed", _error_text(exc))