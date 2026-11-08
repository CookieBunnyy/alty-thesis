"""roles from the Abellar Realty interview

Revision ID: 20261108_0016
Revises: 20261014_0015
Create Date: 2026-11-08 09:00:00.000000

The four user groups confirmed in the interview: Administrator (Admin /
Marketing staff), Broker (company owner), Filing Manager and Seller.
Existing accounts move to the closest new role (users are not deleted):
President -> Broker, General Manager -> Administrator, Employee -> Filing
Manager, Agent -> Seller. The application still accepts the old names.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0016"
down_revision: Union[str, None] = "20261014_0015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None

MOVES = {"President": "Broker", "General Manager": "Administrator", "Employee": "Filing Manager",
         "Agent": "Seller"}
DESCRIPTIONS = {
    "Administrator": "Admin / Marketing staff: users, listings, sellers, recruitment, reports",
    "Broker": "Broker / company owner: company-wide information and reports",
    "Filing Manager": "Sales reports, commission vouchers and the document repository",
    "Seller": "Seller / agent: own listings, deals and permitted records only",
}


def upgrade() -> None:
    users = sa.table("users", sa.column("role", sa.String))
    for old, new in MOVES.items():
        op.execute(users.update().where(sa.func.lower(users.c.role) == old.lower()).values(role=new))
    roles = sa.table("roles", sa.column("name", sa.String), sa.column("description", sa.String),
                     sa.column("created_at", sa.DateTime))
    for old, new in (("President", "Broker"), ("Agent", "Seller")):
        op.execute(roles.update().where(roles.c.name == old).values(name=new))
    op.execute(roles.delete().where(roles.c.name.in_(["General Manager", "Employee"])))
    for name, description in DESCRIPTIONS.items():
        op.execute(roles.update().where(roles.c.name == name).values(description=description))
    bind = op.get_bind()
    present = {row[0] for row in bind.execute(sa.text("SELECT name FROM roles"))}
    for name, description in DESCRIPTIONS.items():
        if name not in present:
            op.execute(roles.insert().values(name=name, description=description, created_at=sa.func.now()))


def downgrade() -> None:
    users = sa.table("users", sa.column("role", sa.String))
    op.execute(users.update().where(users.c.role == "Broker").values(role="President"))
    op.execute(users.update().where(users.c.role == "Seller").values(role="Agent"))
    roles = sa.table("roles", sa.column("name", sa.String))
    op.execute(roles.update().where(roles.c.name == "Broker").values(name="President"))
    op.execute(roles.update().where(roles.c.name == "Seller").values(name="Agent"))
