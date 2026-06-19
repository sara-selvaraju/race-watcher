"""widen meeting going/rail/source columns

Revision ID: 0002_widen_meeting
Revises: 0001_init
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0002_widen_meeting"
down_revision: str | None = "0001_init"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column("meeting", "going", existing_type=sa.String(40), type_=sa.String(120))
    op.alter_column("meeting", "rail", existing_type=sa.String(80), type_=sa.String(120))
    op.alter_column("meeting", "source", existing_type=sa.String(40), type_=sa.String(200))


def downgrade() -> None:
    op.alter_column("meeting", "source", existing_type=sa.String(200), type_=sa.String(40))
    op.alter_column("meeting", "rail", existing_type=sa.String(120), type_=sa.String(80))
    op.alter_column("meeting", "going", existing_type=sa.String(120), type_=sa.String(40))
