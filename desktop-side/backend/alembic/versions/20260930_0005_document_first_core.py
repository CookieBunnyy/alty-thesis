"""document-first core: buyer clients, transaction history, audit, media

Revision ID: 20260930_0005
Revises: 20260930_0004
Create Date: 2026-09-30 12:00:00.000000

- clients: a client can exist before any transaction (Buyer Document) and can
  appear on more than one property, so property/agent/transaction summary
  columns become nullable and the one-client-per-property UNIQUE is dropped.
- transactions: provenance + sync columns, and a partial unique index that
  makes reservation/sale creation idempotent per client+property+type.
- documents: processing outcome columns (stage, error, OCR/TEXT method).
- property_listings: lifecycle timestamps (NULL for pre-existing rows).
- audit_events, property_media: new tables.
- roles: reference rows for the known roles (not demo data).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20260930_0005"
down_revision: Union[str, None] = "20260930_0004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

ROLES = [
    ("Administrator", "Full system administration"),
    ("General Manager", "Management of all business modules"),
    ("President", "Executive access to all business modules"),
    ("Filing Manager", "Document repository management"),
    ("Agent", "Real estate agent"),
    ("Employee", "General staff"),
]


def upgrade() -> None:
    # ---- clients ---------------------------------------------------------
    op.drop_constraint("uq_clients_property_id", "clients", type_="unique")
    op.create_index("ix_clients_property_id", "clients", ["property_id"])
    op.drop_constraint("clients_property_id_fkey", "clients", type_="foreignkey")
    op.create_foreign_key(
        "fk_clients_property_id_listings",
        "clients",
        "property_listings",
        ["property_id"],
        ["listing_id"],
        ondelete="SET NULL",
    )
    op.alter_column("clients", "property_id", nullable=True)
    op.alter_column("clients", "agent_id", nullable=True)
    op.alter_column("clients", "transaction_type", nullable=True)
    op.drop_constraint("ck_clients_status", "clients", type_="check")
    op.create_check_constraint(
        "ck_clients_status",
        "clients",
        "status IN ('PROSPECT', 'RESERVED', 'SOLD', 'CANCELLED')",
    )
    for name, length in (
        ("occupation", 160),
        ("civil_status", 40),
        ("preferred_contact", 60),
        ("purpose_of_purchase", 160),
    ):
        op.add_column("clients", sa.Column(name, sa.String(length=length), nullable=True))
    # Existing rows were pulled from Supabase, hence SYNC / SYNCED defaults.
    op.add_column(
        "clients",
        sa.Column("source", sa.String(length=24), nullable=False, server_default="SYNC"),
    )
    op.add_column(
        "clients",
        sa.Column("sync_status", sa.String(length=24), nullable=False, server_default="SYNCED"),
    )
    op.add_column("clients", sa.Column("last_synced_at", sa.DateTime(), nullable=True))

    # ---- transactions ----------------------------------------------------
    op.add_column(
        "transactions",
        sa.Column("source", sa.String(length=24), nullable=False, server_default="SYNC"),
    )
    op.add_column(
        "transactions", sa.Column("source_document_id", sa.String(length=36), nullable=True)
    )
    op.create_index(
        "ix_transactions_source_document_id", "transactions", ["source_document_id"]
    )
    op.add_column(
        "transactions",
        sa.Column("sync_status", sa.String(length=24), nullable=False, server_default="SYNCED"),
    )
    op.add_column("transactions", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    op.create_index(
        "uq_transactions_active_client_property_type",
        "transactions",
        ["client_id", "property_id", "transaction_type"],
        unique=True,
        postgresql_where=sa.text("status <> 'CANCELLED'"),
    )

    # ---- documents -------------------------------------------------------
    op.add_column("documents", sa.Column("processing_stage", sa.String(length=32), nullable=True))
    op.add_column("documents", sa.Column("processing_error", sa.Text(), nullable=True))
    op.add_column("documents", sa.Column("extraction_method", sa.String(length=16), nullable=True))
    op.add_column("documents", sa.Column("source_format", sa.String(length=24), nullable=True))
    op.add_column("documents", sa.Column("processed_at", sa.DateTime(), nullable=True))
    op.add_column(
        "documents",
        sa.Column("sync_status", sa.String(length=24), nullable=False, server_default="SYNCED"),
    )
    # Audit rows must survive document deletion.
    op.drop_constraint(
        "document_audit_events_document_row_id_fkey",
        "document_audit_events",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "document_audit_events_document_row_id_fkey",
        "document_audit_events",
        "documents",
        ["document_row_id"],
        ["id"],
        ondelete="SET NULL",
    )

    # ---- property_listings / users ----------------------------------------
    op.add_column("property_listings", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.add_column("property_listings", sa.Column("updated_at", sa.DateTime(), nullable=True))
    op.add_column(
        "property_listings", sa.Column("status_changed_at", sa.DateTime(), nullable=True)
    )
    op.add_column("users", sa.Column("last_login_at", sa.DateTime(), nullable=True))

    # ---- audit_events ------------------------------------------------------
    op.create_table(
        "audit_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_label", sa.String(length=120), nullable=False),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("entity_type", sa.String(length=48), nullable=True),
        sa.Column("entity_id", sa.String(length=120), nullable=True),
        sa.Column("result", sa.String(length=16), nullable=False),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "created_at", "actor_id", "action", "entity_type", "entity_id"):
        op.create_index(f"ix_audit_events_{column}", "audit_events", [column])

    # ---- property_media ----------------------------------------------------
    op.create_table(
        "property_media",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("listing_id", sa.Integer(), nullable=False),
        sa.Column("file_name", sa.String(length=255), nullable=False),
        sa.Column("storage_path", sa.String(length=1000), nullable=False),
        sa.Column("storage_bucket", sa.String(length=120), nullable=False),
        sa.Column("mime_type", sa.String(length=80), nullable=False),
        sa.Column("file_size", sa.Integer(), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("width", sa.Integer(), nullable=True),
        sa.Column("height", sa.Integer(), nullable=True),
        sa.Column("orientation", sa.String(length=16), nullable=True),
        sa.Column("blur_score", sa.Float(), nullable=True),
        sa.Column("brightness", sa.Float(), nullable=True),
        sa.Column("contrast", sa.Float(), nullable=True),
        sa.Column("quality_status", sa.String(length=16), nullable=False),
        sa.Column("quality_issues", sa.JSON(), nullable=False),
        sa.Column("uploaded_by", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["listing_id"], ["property_listings.listing_id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["uploaded_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    for column in ("id", "listing_id", "file_hash", "quality_status"):
        op.create_index(f"ix_property_media_{column}", "property_media", [column])

    # ---- roles reference data ---------------------------------------------
    roles = sa.table(
        "roles",
        sa.column("name", sa.String()),
        sa.column("description", sa.String()),
        sa.column("created_at", sa.DateTime()),
    )
    connection = op.get_bind()
    existing = {row[0] for row in connection.execute(sa.text("SELECT name FROM roles"))}
    for name, description in ROLES:
        if name not in existing:
            connection.execute(
                roles.insert().values(name=name, description=description, created_at=sa.func.now())
            )


def downgrade() -> None:
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM clients
                    WHERE property_id IS NULL OR agent_id IS NULL
                       OR transaction_type IS NULL OR status = 'PROSPECT'
                ) OR EXISTS (
                    SELECT property_id FROM clients
                    GROUP BY property_id HAVING count(*) > 1
                ) THEN
                    RAISE EXCEPTION
                        'Cannot downgrade: document-first client records exist that the old schema cannot represent';
                END IF;
            END
            $$;
            """
        )
    )
    op.drop_table("property_media")
    op.drop_table("audit_events")
    op.drop_column("users", "last_login_at")
    for column in ("status_changed_at", "updated_at", "created_at"):
        op.drop_column("property_listings", column)
    op.drop_constraint(
        "document_audit_events_document_row_id_fkey", "document_audit_events", type_="foreignkey"
    )
    op.create_foreign_key(
        "document_audit_events_document_row_id_fkey",
        "document_audit_events",
        "documents",
        ["document_row_id"],
        ["id"],
    )
    for column in (
        "sync_status", "processed_at", "source_format", "extraction_method",
        "processing_error", "processing_stage",
    ):
        op.drop_column("documents", column)
    op.drop_index("uq_transactions_active_client_property_type", table_name="transactions")
    op.drop_index("ix_transactions_source_document_id", table_name="transactions")
    for column in ("last_synced_at", "sync_status", "source_document_id", "source"):
        op.drop_column("transactions", column)
    for column in (
        "last_synced_at", "sync_status", "source", "purpose_of_purchase",
        "preferred_contact", "civil_status", "occupation",
    ):
        op.drop_column("clients", column)
    op.drop_constraint("ck_clients_status", "clients", type_="check")
    op.create_check_constraint(
        "ck_clients_status", "clients", "status IN ('RESERVED', 'SOLD', 'CANCELLED')"
    )
    op.alter_column("clients", "transaction_type", nullable=False)
    op.alter_column("clients", "agent_id", nullable=False)
    op.alter_column("clients", "property_id", nullable=False)
    op.drop_constraint("fk_clients_property_id_listings", "clients", type_="foreignkey")
    op.create_foreign_key(
        "clients_property_id_fkey",
        "clients",
        "property_listings",
        ["property_id"],
        ["listing_id"],
        ondelete="CASCADE",
    )
    op.drop_index("ix_clients_property_id", table_name="clients")
    op.create_unique_constraint("uq_clients_property_id", "clients", ["property_id"])
