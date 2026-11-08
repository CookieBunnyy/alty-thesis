"""configurable document schemas and verified extraction (commission vouchers)

Revision ID: 20261108_0021
Revises: 20261108_0020
Create Date: 2026-11-08 14:00:00.000000

- document_schemas: the fields to extract per document type. The commission
  voucher schema starts EMPTY: its printed labels are configured once Abellar
  provides a real voucher (none was available at the interview).
- document_extractions: label/value pairs found, schema-mapped fields, the
  human-verified values, links, and verification status.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0021"
down_revision: Union[str, None] = "20261108_0020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.create_table(
        "document_schemas",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_type", sa.String(80), nullable=False, unique=True),
        sa.Column("fields", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("updated_by", sa.String(200), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.execute("INSERT INTO document_schemas (document_type, fields, updated_by) "
               "VALUES ('COMMISSION_VOUCHER', '[]', 'Migration')")
    op.create_table(
        "document_extractions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("document_row_id", sa.Integer(), sa.ForeignKey("documents.id", ondelete="CASCADE"), nullable=False,
                  unique=True),
        sa.Column("document_type", sa.String(80), nullable=False),
        sa.Column("detected_pairs", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("mapped_fields", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verified_fields", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("links", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("verification_status", sa.String(16), nullable=False, server_default="NEEDS_REVIEW"),
        sa.Column("verified_by", sa.String(200), nullable=True),
        sa.Column("verified_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("document_extractions")
    op.drop_table("document_schemas")
