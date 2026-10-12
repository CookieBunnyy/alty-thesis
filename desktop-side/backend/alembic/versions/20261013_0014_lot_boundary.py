"""lot boundary drawn on the map

Revision ID: 20261013_0014
Revises: 20261013_0013
Create Date: 2026-10-13 12:00:00.000000

- property_listings.boundary: the lot's outline as a GeoJSON Polygon
  ([lng, lat] points, WGS84), drawn by staff. Area and perimeter are
  calculated from it when read (services/lot_geometry.py), not stored.
- property_listings.boundary_updated_at / boundary_updated_by: who mapped it.
Not part of the central listings sync.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "20261013_0014"
down_revision: Union[str, None] = "20261013_0013"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("property_listings", sa.Column("boundary", postgresql.JSONB(), nullable=True))
    op.add_column("property_listings", sa.Column("boundary_updated_at", sa.DateTime(), nullable=True))
    op.add_column("property_listings", sa.Column("boundary_updated_by", sa.String(length=200), nullable=True))


def downgrade() -> None:
    op.drop_column("property_listings", "boundary_updated_by")
    op.drop_column("property_listings", "boundary_updated_at")
    op.drop_column("property_listings", "boundary")
