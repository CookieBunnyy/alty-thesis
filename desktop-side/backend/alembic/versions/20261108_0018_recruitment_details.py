"""recruitment details from the interview

Revision ID: 20261108_0018
Revises: 20261108_0017
Create Date: 2026-11-08 11:00:00.000000

Interview: recruitment records hold the full name, birthday, contact number,
address, email, recruiter, team/cluster, and a declaration that the recruit
is not actively bound to another broker.
- agent_applicants.birthday, recruiter_agent_id / recruiter_name,
  not_bound_to_other_broker, declaration_date (team/cluster = branch_id).
- agents.recruited_by_agent_id / recruiter_name: who recruited each seller.
- agents.commission_visible: whether management lets the seller see their
  own commission records (off until management turns it on).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261108_0018"
down_revision: Union[str, None] = "20261108_0017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("agent_applicants", sa.Column("birthday", sa.Date(), nullable=True))
    op.add_column("agent_applicants", sa.Column("recruiter_agent_id", sa.String(32), nullable=True))
    op.add_column("agent_applicants", sa.Column("recruiter_name", sa.String(200), nullable=True))
    op.add_column("agent_applicants", sa.Column("not_bound_to_other_broker", sa.Boolean(), nullable=True))
    op.add_column("agent_applicants", sa.Column("declaration_date", sa.Date(), nullable=True))
    op.create_foreign_key("fk_agent_applicants_recruiter", "agent_applicants", "agents", ["recruiter_agent_id"],
                          ["agent_id"], ondelete="SET NULL")
    op.create_index("ix_agent_applicants_recruiter_agent_id", "agent_applicants", ["recruiter_agent_id"])

    op.add_column("agents", sa.Column("recruited_by_agent_id", sa.String(32), nullable=True))
    op.add_column("agents", sa.Column("recruiter_name", sa.String(200), nullable=True))
    op.add_column("agents", sa.Column("commission_visible", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.create_foreign_key("fk_agents_recruited_by", "agents", "agents", ["recruited_by_agent_id"], ["agent_id"],
                          ondelete="SET NULL")
    op.create_index("ix_agents_recruited_by_agent_id", "agents", ["recruited_by_agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agents_recruited_by_agent_id", table_name="agents")
    op.drop_constraint("fk_agents_recruited_by", "agents", type_="foreignkey")
    for column in ("commission_visible", "recruiter_name", "recruited_by_agent_id"):
        op.drop_column("agents", column)
    op.drop_index("ix_agent_applicants_recruiter_agent_id", table_name="agent_applicants")
    op.drop_constraint("fk_agent_applicants_recruiter", "agent_applicants", type_="foreignkey")
    for column in ("declaration_date", "not_bound_to_other_broker", "recruiter_name", "recruiter_agent_id", "birthday"):
        op.drop_column("agent_applicants", column)
