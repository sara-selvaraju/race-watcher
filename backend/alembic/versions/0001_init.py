"""init schema

Revision ID: 0001_init
Revises:
Create Date: 2026-06-19

"""
from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001_init"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "meeting",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("track", sa.String(80), nullable=False),
        sa.Column("date", sa.Date, nullable=False),
        sa.Column("going", sa.String(40)),
        sa.Column("rail", sa.String(80)),
        sa.Column("timezone", sa.String(40), nullable=False, server_default="Australia/Melbourne"),
        sa.Column("source", sa.String(40), nullable=False, server_default="seed"),
        sa.UniqueConstraint("track", "date", name="uq_meeting_track_date"),
    )
    op.create_table(
        "race",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("meeting_id", sa.Integer, sa.ForeignKey("meeting.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("distance_m", sa.Integer),
        sa.Column("klass", sa.String(40)),
        sa.Column("start_time_local", sa.Time),
        sa.Column("status", sa.String(20), nullable=False, server_default="open"),
        sa.UniqueConstraint("meeting_id", "number", name="uq_race_meeting_number"),
    )
    op.create_table(
        "runner",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("race_id", sa.Integer, sa.ForeignKey("race.id", ondelete="CASCADE"), nullable=False),
        sa.Column("number", sa.Integer, nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("jockey", sa.String(80)),
        sa.Column("trainer", sa.String(80)),
        sa.Column("barrier", sa.Integer),
        sa.Column("weight_kg", sa.Numeric(5, 2)),
        sa.Column("silk", sa.String(160)),
        sa.Column("scratched", sa.Boolean, nullable=False, server_default=sa.text("false")),
        sa.Column("betfair_selection_id", sa.Integer),
        sa.UniqueConstraint("race_id", "number", name="uq_runner_race_number"),
    )
    op.create_table(
        "form_line",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("runner_id", sa.Integer, sa.ForeignKey("runner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("line_date", sa.Date),
        sa.Column("track", sa.String(80)),
        sa.Column("distance_m", sa.Integer),
        sa.Column("going", sa.String(40)),
        sa.Column("finish_pos", sa.Integer),
        sa.Column("margin", sa.Numeric(6, 2)),
        sa.Column("weight_kg", sa.Numeric(5, 2)),
        sa.Column("note", sa.String(800)),
    )
    op.create_table(
        "price_snapshot",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("runner_id", sa.Integer, sa.ForeignKey("runner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source", sa.String(40), nullable=False),
        sa.Column("price", sa.Numeric(8, 3), nullable=False),
        sa.Column("taken_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_price_snapshot_runner_taken",
        "price_snapshot",
        ["runner_id", "taken_at"],
    )
    op.create_table(
        "prediction",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("runner_id", sa.Integer, sa.ForeignKey("runner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("engine", sa.String(40), nullable=False),
        sa.Column("score", sa.Numeric(6, 3)),
        sa.Column("win_prob", sa.Numeric(6, 4)),
        sa.Column("rating", sa.String(40)),
        sa.Column("rationale", sa.String(800)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "movement_alert",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("runner_id", sa.Integer, sa.ForeignKey("runner.id", ondelete="CASCADE"), nullable=False),
        sa.Column("from_price", sa.Numeric(8, 3), nullable=False),
        sa.Column("to_price", sa.Numeric(8, 3), nullable=False),
        sa.Column("pct_change", sa.Numeric(6, 2), nullable=False),
        sa.Column("direction", sa.String(10), nullable=False),
        sa.Column("baseline", sa.String(20), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index(
        "ix_movement_alert_runner_created",
        "movement_alert",
        ["runner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_movement_alert_runner_created", table_name="movement_alert")
    op.drop_table("movement_alert")
    op.drop_table("prediction")
    op.drop_index("ix_price_snapshot_runner_taken", table_name="price_snapshot")
    op.drop_table("price_snapshot")
    op.drop_table("form_line")
    op.drop_table("runner")
    op.drop_table("race")
    op.drop_table("meeting")
