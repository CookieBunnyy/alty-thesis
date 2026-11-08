"""remove the Broker role

Revision ID: 20261109_0022
Revises: 20261108_0021
Create Date: 2026-11-09 09:00:00.000000

Abellar Realty dropped the separate Broker role. Accounts that had it become
Administrator (same company-wide access, nothing is deleted). The application
still reads "Broker" (and "President") as Administrator.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261109_0022"
down_revision: Union[str, None] = "20261108_0021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    users = sa.table("users", sa.column("role", sa.String))
    op.execute(users.update().where(sa.func.lower(users.c.role).in_(["broker", "president"]))
               .values(role="Administrator"))
    roles = sa.table("roles", sa.column("name", sa.String))
    op.execute(roles.delete().where(roles.c.name == "Broker"))


def downgrade() -> None:
    # Which Administrators were Brokers isn't recorded; only the role row returns.
    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String),
                     sa.column("created_at", sa.DateTime))
    op.execute(roles.insert().values(name="Broker", description="Broker / company owner: company-wide information and reports",
                                     created_at=sa.func.now()))
