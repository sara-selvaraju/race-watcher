"""add top_pick table for race-level top-3 finisher predictions

Revision ID: 0004_top_picks
Revises: 0003_runner_seed_fields
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_top_picks"
down_revision: str | None = "0003_runner_seed_fields"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "top_pick",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("race.id", ondelete="CASCADE"), nullable=False),
        sa.Column("runner_id", sa.Integer, sa.ForeignKey("runner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("rationale", sa.String(800)),
        sa.Column("source", sa.String(40), nullable=False, server_default="openrouter"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("race_id", "rank", name="uq_top_pick_race_rank"),
    )
    op.create_index("ix_top_pick_race", "top_pick", ["race_id"])


def downgrade() -> None:
    op.drop_index("ix_top_pick_race", table_name="top_pick")
    op.drop_table("top_pick")
