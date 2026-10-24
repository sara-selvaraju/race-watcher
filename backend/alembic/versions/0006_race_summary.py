"""race_summary: LLM notes on each race's picks

Revision ID: 0006_race_summary
Revises: 0005_widen_rationale
Create Date: 2026-10-24

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_race_summary"
down_revision: str | None = "0005_widen_rationale"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "race_summary",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("race_id", sa.Integer(), sa.ForeignKey("race.id", ondelete="CASCADE"), nullable=False),
        sa.Column("summary", sa.String(3000), nullable=False),
        sa.Column("inputs_hash", sa.String(64), nullable=False),
        sa.Column("model", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("race_id", name="uq_race_summary_race"),
    )


def downgrade() -> None:
    op.drop_table("race_summary")
