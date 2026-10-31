"""agent_run: a log of each agent run, for the admin page

Revision ID: 0007_agent_run
Revises: 0006_race_summary
Create Date: 2026-10-31

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_agent_run"
down_revision: str | None = "0006_race_summary"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "agent_run",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("agent", sa.String(40), nullable=False),
        sa.Column("trigger", sa.String(20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("races", sa.Integer(), nullable=False),
        sa.Column("result", sa.String(300), nullable=True),
        sa.Column("sites", sa.JSON(), nullable=True),
        sa.Column("error", sa.String(500), nullable=True),
    )
    op.create_index("ix_agent_run_agent_started", "agent_run", ["agent", "started_at"])


def downgrade() -> None:
    op.drop_index("ix_agent_run_agent_started", table_name="agent_run")
    op.drop_table("agent_run")
