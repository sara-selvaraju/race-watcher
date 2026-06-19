"""add seed-derived fields to runner

Revision ID: 0003_runner_seed_fields
Revises: 0002_widen_meeting
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003_runner_seed_fields"
down_revision: str | None = "0002_widen_meeting"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("runner", sa.Column("seed_price", sa.Numeric(8, 3)))
    op.add_column("runner", sa.Column("seed_price_source", sa.String(40)))
    op.add_column("runner", sa.Column("seed_prediction_rating", sa.String(40)))
    op.add_column("runner", sa.Column("seed_prediction_rationale", sa.String(400)))


def downgrade() -> None:
    op.drop_column("runner", "seed_prediction_rationale")
    op.drop_column("runner", "seed_prediction_rating")
    op.drop_column("runner", "seed_price_source")
    op.drop_column("runner", "seed_price")
