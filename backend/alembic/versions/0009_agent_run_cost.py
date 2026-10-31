"""agent_run: tokens and cost of each run

Revision ID: 0009_agent_run_cost
Revises: 0008_agent_model
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009_agent_run_cost"
down_revision: str | None = "0008_agent_model"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("agent_run", sa.Column("tokens", sa.Integer(), nullable=True))
    op.add_column("agent_run", sa.Column("cost_usd", sa.Numeric(12, 6), nullable=True))


def downgrade() -> None:
    op.drop_column("agent_run", "cost_usd")
    op.drop_column("agent_run", "tokens")
