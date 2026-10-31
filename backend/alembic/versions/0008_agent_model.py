"""agent_model: models chosen per agent on the admin page; agent_run.model: the model each run used

Revision ID: 0008_agent_model
Revises: 0007_agent_run
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_agent_model"
down_revision: str | None = "0007_agent_run"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_model",
        sa.Column("agent", sa.String(40), primary_key=True),
        sa.Column("model", sa.String(120), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.add_column("agent_run", sa.Column("model", sa.String(120), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "model")
    op.drop_table("agent_model")
