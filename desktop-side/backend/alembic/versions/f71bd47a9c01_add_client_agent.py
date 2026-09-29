"""link clients to agents

Revision ID: f71bd47a9c01
Revises: c84e9a31d6f2
Create Date: 2026-09-29
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f71bd47a9c01"
down_revision: Union[str, None] = "c84e9a31d6f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, None] = None


def upgrade() -> None:
    op.add_column(
        "clients",
        sa.Column("agent_id", sa.String(length=32), nullable=True),
    )
    op.execute(
        sa.text(
            """
            UPDATE clients AS client
            SET agent_id = assignment.agent_id
            FROM (VALUES
                (1, 'AGT-0001'),
                (2, 'AGT-0002'),
                (3, 'AGT-0003'),
                (4, 'AGT-0004'),
                (5, 'AGT-0005'),
                (12, 'AGT-0001'),
                (14, 'AGT-0002')
            ) AS assignment(property_id, agent_id)
            WHERE client.property_id = assignment.property_id
              AND EXISTS (
                  SELECT 1 FROM agents
                  WHERE agents.agent_id = assignment.agent_id
              )
            """
        )
    )
    op.execute(
        sa.text(
            """
            DO $$
            BEGIN
                IF EXISTS (SELECT 1 FROM clients WHERE agent_id IS NULL) THEN
                    RAISE EXCEPTION
                        'Cannot migrate clients: assign every existing client to a valid agent first';
                END IF;
            END
            $$;
            """
        )
    )
    op.create_foreign_key(
        "fk_clients_agent_id_agents",
        "clients",
        "agents",
        ["agent_id"],
        ["agent_id"],
        ondelete="RESTRICT",
    )
    op.alter_column("clients", "agent_id", nullable=False)
    op.create_index("ix_clients_agent_id", "clients", ["agent_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_clients_agent_id", table_name="clients")
    op.drop_constraint("fk_clients_agent_id_agents", "clients", type_="foreignkey")
    op.drop_column("clients", "agent_id")