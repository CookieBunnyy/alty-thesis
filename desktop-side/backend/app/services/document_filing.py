"""Automatic filing of processed documents into per-person / per-property folders.

After a document is processed successfully, it is moved into a folder named
after who or what it is about, under its category folder — for example a
Buyer Document for John Doe goes to ``Buyers / John Doe``. Later documents
for the same person reuse that folder, so each client's papers stay together.

Rules
* Only SUCCESS documents are filed (a failed one stays where it was uploaded).
* A folder the uploader chose themselves is respected; filing only happens when
  no folder was chosen or a standard category folder was chosen.
* Folder names come from the processed record (client, agent, property);
  nothing is guessed — without a name the document stays in the category.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.agent import Agent
from app.models.document import Document, DocumentFolder

# Category folders (also created by GET /documents/folders).
DEFAULT_FOLDERS = ("Properties", "Buyers", "Sellers", "Agents", "Transactions",
                   "Financial", "Contracts", "Archived")
FINANCIAL_SUBFOLDERS = ("Receipts", "Vouchers", "Proof of Payment", "Invoices")

# document type -> category path. Everything about a client's purchase is kept
# together under Buyers / <client>.
CATEGORY_BY_TYPE: dict[str, tuple[str, ...]] = {
    "BUYER_DOCUMENT": ("Buyers",),
    "RESERVATION_AGREEMENT": ("Buyers",),
    "SALE_AGREEMENT": ("Buyers",),
    "DEED": ("Buyers",),
    "TRANSACTION_DOCUMENT": ("Buyers",),
    "CONTRACT": ("Buyers",),
    "SELLER_DOCUMENT": ("Sellers",),
    "AGENT_INFORMATION": ("Agents",),
    "PROPERTY_INFORMATION": ("Properties",),
    "RECEIPT": ("Financial", "Receipts"),
    "VOUCHER": ("Financial", "Vouchers"),
    "PROOF_OF_PAYMENT": ("Financial", "Proof of Payment"),
    "INVOICE": ("Financial", "Invoices"),
}
MAX_NAME = 160


def _clean(name: str | None) -> str | None:
    text = " ".join(str(name or "").split()).strip(" /\\")
    return text[:MAX_NAME] or None


def _child(db: Session, name: str, parent: DocumentFolder | None) -> DocumentFolder | None:
    statement = select(DocumentFolder).where(func.lower(DocumentFolder.name) == name.lower(),
                                            DocumentFolder.is_archived.is_(False))
    statement = statement.where(DocumentFolder.parent_id == parent.id if parent else DocumentFolder.parent_id.is_(None))
    return db.execute(statement.order_by(DocumentFolder.id)).scalars().first()


def _ensure(db: Session, name: str, parent: DocumentFolder | None, actor_id: int | None, created: list) -> DocumentFolder:
    folder = _child(db, name, parent)
    if folder is None:
        folder = DocumentFolder(name=name, parent_id=parent.id if parent else None, created_by=actor_id)
        db.add(folder)
        db.flush()
        created.append(folder)
    return folder


def is_category_folder(db: Session, folder_id: int | None) -> bool:
    """No folder, or one of the standard category folders (not a custom one)."""
    if folder_id is None:
        return True
    folder = db.get(DocumentFolder, folder_id)
    if folder is None:
        return True
    if folder.parent_id is None:
        return folder.name in DEFAULT_FOLDERS
    parent = db.get(DocumentFolder, folder.parent_id)
    return bool(parent and parent.parent_id is None and parent.name == "Financial" and folder.name in FINANCIAL_SUBFOLDERS)


def subject_name(db: Session, document: Document, processing: dict) -> str | None:
    """Who or what the document is about, from the processed record."""
    if document.document_type == "PROPERTY_INFORMATION":
        return _clean(document.property_listing_title)
    if document.document_type == "AGENT_INFORMATION":
        agent = (processing.get("matched_entities") or {}).get("agent")
        agent_id = agent.get("id") if isinstance(agent, dict) else agent
        record = db.get(Agent, agent_id) if agent_id else None
        return _clean(record.full_name if record else document.related_party_name)
    return _clean(document.related_party_name)


def file_document(db: Session, document: Document, processing: dict, actor_id: int | None) -> dict | None:
    """File a successfully processed document. Returns {"folder_id", "path",
    "created": [names]} when it was moved, else None."""
    if document.status != "SUCCESS" or not is_category_folder(db, document.folder_id):
        return None
    category = CATEGORY_BY_TYPE.get(document.document_type)
    if not category:
        return None
    created: list[DocumentFolder] = []
    folder = None
    for name in category:
        folder = _ensure(db, name, folder, actor_id, created)
    name = subject_name(db, document, processing)
    if name:
        folder = _ensure(db, name, folder, actor_id, created)
    if folder is None or folder.id == document.folder_id:
        return None
    document.folder_id = folder.id
    return {"folder_id": folder.id, "path": folder_path(db, folder.id), "created": [f.name for f in created]}


def folder_path(db: Session, folder_id: int | None) -> str | None:
    """'Financial / Receipts / John Doe' for a folder (None when unfiled)."""
    names: list[str] = []
    seen: set[int] = set()
    while folder_id is not None and folder_id not in seen:
        seen.add(folder_id)
        folder = db.get(DocumentFolder, folder_id)
        if folder is None:
            break
        names.append(folder.name)
        folder_id = folder.parent_id
    return " / ".join(reversed(names)) or None
