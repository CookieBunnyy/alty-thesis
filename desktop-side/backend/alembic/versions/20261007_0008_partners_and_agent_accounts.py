"""partners, listing developer, agent accounts

Revision ID: 20261007_0008
Revises: 20261003_0007
Create Date: 2026-10-07 09:00:00.000000

- partners: developers and other partner companies (replaces the list that
  was hard-coded in the desktop Partners page; those names are carried over,
  everything else about them starts empty — nothing is invented).
- property_listings.partner_id: the developer of a listing (optional; kept
  in ALTY, not pushed to the Supabase listings table).
- users.agent_id: links a staff account to its agent record (one each), for
  the agent's own "My Work" view.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261007_0008"
down_revision: Union[str, None] = "20261003_0007"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

# The names shown by the desktop Partners page before this table existed.
EXISTING_PARTNERS = [
    "NORTHACRE", "MY CITYHOMES", "GREENWOOD", "VANDERBILT", "PHINMA", "MASAITO", "JEIKA", "LUMINA",
    "HESTIA", "SUNTRUST", "SMDC", "OVALAND", "PARADISIMO", "ECOVERDE", "NEXTASIA", "DURAVILLE",
    "AMAIA", "WEECOMM", "AXELA", "LANDNET", "LYNNVILLE", "GOLDEN HORIZON", "RED OAK", "IDESIA",
]


def upgrade() -> None:
    partners = op.create_table(
        "partners",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("partner_type", sa.String(40), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="ACTIVE"),
        sa.Column("contact_person", sa.String(200), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone_number", sa.String(40), nullable=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("uq_partners_name_lower", "partners", [sa.text("lower(name)")], unique=True)
    op.bulk_insert(partners, [{"name": name, "status": "ACTIVE"} for name in EXISTING_PARTNERS])

    op.add_column("property_listings", sa.Column("partner_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_property_listings_partner_id", "property_listings", "partners",
                          ["partner_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_property_listings_partner_id", "property_listings", ["partner_id"])

    op.add_column("users", sa.Column("agent_id", sa.String(32), nullable=True))
    op.create_foreign_key("fk_users_agent_id", "users", "agents", ["agent_id"], ["agent_id"], ondelete="SET NULL")
    op.create_unique_constraint("uq_users_agent_id", "users", ["agent_id"])


def downgrade() -> None:
    op.drop_constraint("uq_users_agent_id", "users", type_="unique")
    op.drop_constraint("fk_users_agent_id", "users", type_="foreignkey")
    op.drop_column("users", "agent_id")
    op.drop_index("ix_property_listings_partner_id", table_name="property_listings")
    op.drop_constraint("fk_property_listings_partner_id", "property_listings", type_="foreignkey")
    op.drop_column("property_listings", "partner_id")
    op.drop_index("uq_partners_name_lower", table_name="partners")
    op.drop_table("partners")
