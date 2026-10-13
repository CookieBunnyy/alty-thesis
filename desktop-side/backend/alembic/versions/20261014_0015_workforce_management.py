"""branches, agent assignment, recruitment, assessments

Revision ID: 20261014_0015
Revises: 20261013_0014
Create Date: 2026-10-14 09:00:00.000000

- agents.branch_id / designation / work_area / hired_on: where an agent works
  and their position (ALTY only, not part of the central agents sync).
- property_listings.branch_id: the branch that handles a listing.
- agent_applicants: the recruitment pipeline.
- agent_assessments: periodic agent evaluations.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "20261014_0015"
down_revision: Union[str, None] = "20261013_0014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column("agents", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.add_column("agents", sa.Column("designation", sa.String(length=60), nullable=True))
    op.add_column("agents", sa.Column("work_area", sa.String(length=255), nullable=True))
    op.add_column("agents", sa.Column("hired_on", sa.Date(), nullable=True))
    op.create_foreign_key("fk_agents_branch", "agents", "branches", ["branch_id"], ["id"], ondelete="SET NULL")
    op.create_index("ix_agents_branch_id", "agents", ["branch_id"])

    op.add_column("property_listings", sa.Column("branch_id", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_property_listings_branch", "property_listings", "branches", ["branch_id"], ["id"],
                          ondelete="SET NULL")
    op.create_index("ix_property_listings_branch_id", "property_listings", ["branch_id"])

    op.create_table(
        "agent_applicants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(length=200), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("phone_number", sa.String(length=40), nullable=True),
        sa.Column("address", sa.String(length=500), nullable=True),
        sa.Column("branch_id", sa.Integer(), sa.ForeignKey("branches.id", ondelete="SET NULL"), nullable=True),
        sa.Column("desired_designation", sa.String(length=60), nullable=True),
        sa.Column("source", sa.String(length=30), nullable=True),
        sa.Column("experience_years", sa.Numeric(4, 1), nullable=True),
        sa.Column("has_license", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("license_number", sa.String(length=60), nullable=True),
        sa.Column("screening_score", sa.Integer(), nullable=True),
        sa.Column("interview_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="APPLIED"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("history", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("agent_id", sa.String(length=32), sa.ForeignKey("agents.agent_id", ondelete="SET NULL"),
                  nullable=True),
        sa.Column("created_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_applicants_status", "agent_applicants", ["status"])
    op.create_index("ix_agent_applicants_branch_id", "agent_applicants", ["branch_id"])

    op.create_table(
        "agent_assessments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent_id", sa.String(length=32), sa.ForeignKey("agents.agent_id", ondelete="CASCADE"),
                  nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("scores", sa.JSON(), nullable=False),
        sa.Column("overall", sa.Numeric(3, 2), nullable=False),
        sa.Column("rating", sa.String(length=40), nullable=False),
        sa.Column("recommendation", sa.String(length=60), nullable=True),
        sa.Column("kpis", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("remarks", sa.Text(), nullable=True),
        sa.Column("assessed_by", sa.String(length=200), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_agent_assessments_agent_id", "agent_assessments", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_assessments_agent_id", table_name="agent_assessments")
    op.drop_table("agent_assessments")
    op.drop_index("ix_agent_applicants_branch_id", table_name="agent_applicants")
    op.drop_index("ix_agent_applicants_status", table_name="agent_applicants")
    op.drop_table("agent_applicants")
    op.drop_index("ix_property_listings_branch_id", table_name="property_listings")
    op.drop_constraint("fk_property_listings_branch", "property_listings", type_="foreignkey")
    op.drop_column("property_listings", "branch_id")
    op.drop_index("ix_agents_branch_id", table_name="agents")
    op.drop_constraint("fk_agents_branch", "agents", type_="foreignkey")
    op.drop_column("agents", "hired_on")
    op.drop_column("agents", "work_area")
    op.drop_column("agents", "designation")
    op.drop_column("agents", "branch_id")
