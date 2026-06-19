"""widen prediction.rationale and top_pick.rationale to fit linkified citations

Revision ID: 0005_widen_rationale
Revises: 0004_top_picks
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0005_widen_rationale"
down_revision: str | None = "0004_top_picks"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("prediction", "rationale", existing_type=sa.String(800), type_=sa.String(2000))
    op.alter_column("top_pick", "rationale", existing_type=sa.String(800), type_=sa.String(2000))


def downgrade() -> None:
    op.alter_column("top_pick", "rationale", existing_type=sa.String(2000), type_=sa.String(800))
    op.alter_column("prediction", "rationale", existing_type=sa.String(2000), type_=sa.String(800))
