"""recruitment form scans; document folders reorganised

* applicant_forms: photos / scans of the recruitment form an applicant filled in.
* Folders: "Commission Vouchers" becomes "Commission Documents"; "Vouchers"
  moves out of "Financial" to the top level; receipts, proof of payment,
  invoices and contracts go to "Buyers" (they are about a client's purchase);
  the "Financial" and "Contracts" folders are removed.

Revision ID: 20261110_0025
Revises: 20261109_0024
Create Date: 2026-11-10 12:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261110_0025"
down_revision: Union[str, None] = "20261109_0024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

FINANCIAL_STANDARD = ("Receipts", "Proof of Payment", "Invoices")


def upgrade() -> None:
    op.create_table(
        "applicant_forms",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("applicant_id", sa.Integer(), sa.ForeignKey("agent_applicants.id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("bucket", sa.String(120), nullable=False),
        sa.Column("path", sa.String(300), nullable=False),
        sa.Column("mime_type", sa.String(80), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("uploaded_by", sa.String(200), nullable=True),
        sa.Column("uploaded_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_applicant_forms_applicant_id", "applicant_forms", ["applicant_id"])
    _reorganise_folders(op.get_bind())


def downgrade() -> None:
    # The folder changes are not reversed (documents stay where they were filed).
    op.drop_index("ix_applicant_forms_applicant_id", table_name="applicant_forms")
    op.drop_table("applicant_forms")


def _reorganise_folders(bind) -> None:
    def child(name: str, parent_id: int | None) -> int | None:
        if parent_id is None:
            row = bind.execute(sa.text("SELECT id FROM document_folders WHERE parent_id IS NULL AND lower(name) = lower(:n) "
                                       "AND is_archived = false ORDER BY id LIMIT 1"), {"n": name}).first()
        else:
            row = bind.execute(sa.text("SELECT id FROM document_folders WHERE parent_id = :p AND lower(name) = lower(:n) "
                                       "AND is_archived = false ORDER BY id LIMIT 1"), {"p": parent_id, "n": name}).first()
        return row[0] if row else None

    def ensure(name: str, parent_id: int | None = None) -> int:
        found = child(name, parent_id)
        if found is not None:
            return found
        return bind.execute(sa.text("INSERT INTO document_folders (name, parent_id, is_archived, created_at, updated_at) "
                                    "VALUES (:n, :p, false, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) RETURNING id"),
                            {"n": name, "p": parent_id}).scalar_one()

    def remove(folder_id: int, into: int | None) -> None:
        """Delete an emptied folder, pointing anything that referred to it at ``into``."""
        bind.execute(sa.text("UPDATE documents SET folder_id = :to WHERE folder_id = :f"), {"to": into, "f": folder_id})
        bind.execute(sa.text("UPDATE document_audit_events SET folder_id = :to WHERE folder_id = :f"),
                     {"to": into, "f": folder_id})
        bind.execute(sa.text("UPDATE document_folders SET parent_id = :to WHERE parent_id = :f"),
                     {"to": into, "f": folder_id})
        bind.execute(sa.text("DELETE FROM document_folders WHERE id = :f"), {"f": folder_id})

    def merge(folder_id: int, into: int | None) -> None:
        """Put the folder inside ``into``; when a folder of the same name is
        already there, move its contents into that one instead."""
        name, archived = bind.execute(sa.text("SELECT name, is_archived FROM document_folders WHERE id = :f"),
                                      {"f": folder_id}).one()
        same = None if archived else child(name, into)
        if same is None or same == folder_id:
            bind.execute(sa.text("UPDATE document_folders SET parent_id = :to WHERE id = :f"), {"to": into, "f": folder_id})
            return
        for (sub,) in bind.execute(sa.text("SELECT id FROM document_folders WHERE parent_id = :f ORDER BY id"),
                                   {"f": folder_id}).all():
            merge(sub, same)
        remove(folder_id, same)

    def empty_into(folder_id: int, into: int) -> None:
        """Move a folder's documents and subfolders into ``into``, then delete it."""
        for (sub,) in bind.execute(sa.text("SELECT id FROM document_folders WHERE parent_id = :f ORDER BY id"),
                                   {"f": folder_id}).all():
            merge(sub, into)
        remove(folder_id, into)

    old = child("Commission Vouchers", None)
    if old is not None:
        new = child("Commission Documents", None)
        if new is None:
            bind.execute(sa.text("UPDATE document_folders SET name = 'Commission Documents' WHERE id = :f"), {"f": old})
        else:
            empty_into(old, new)

    financial = child("Financial", None)
    contracts = child("Contracts", None)
    if financial is None and contracts is None:
        return
    buyers = ensure("Buyers")
    if financial is not None:
        vouchers = child("Vouchers", financial)
        if vouchers is not None:
            top = child("Vouchers", None)
            if top is None:
                bind.execute(sa.text("UPDATE document_folders SET parent_id = NULL WHERE id = :f"), {"f": vouchers})
            else:
                empty_into(vouchers, top)
        for name in FINANCIAL_STANDARD:
            folder = child(name, financial)
            if folder is not None:
                empty_into(folder, buyers)
        # Anything else someone made inside Financial goes to the top level.
        for (sub,) in bind.execute(sa.text("SELECT id FROM document_folders WHERE parent_id = :f ORDER BY id"),
                                   {"f": financial}).all():
            merge(sub, None)
        remove(financial, buyers)
    if contracts is not None:
        empty_into(contracts, buyers)
