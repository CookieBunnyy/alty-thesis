"""align property listing id sequence

Revision ID: bf28bc395c16
Revises: fd97657259dd
Create Date: 2026-09-29 19:35:13.039867
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'bf28bc395c16'
down_revision: Union[str, None] = 'fd97657259dd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Unqualified table names: resolved through the connection's search_path,
    # so this works in `public` locally and in a dedicated schema in the cloud.
    op.execute(
        sa.text(
            "SELECT setval("
            "pg_get_serial_sequence('property_listings', 'listing_id'), "
            "GREATEST(COALESCE((SELECT MAX(listing_id) "
            "FROM property_listings), 1), 1), "
            "EXISTS(SELECT 1 FROM property_listings)"
            ")"
        )
    )


def downgrade() -> None:
    pass
