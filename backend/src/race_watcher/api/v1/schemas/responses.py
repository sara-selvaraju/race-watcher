from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _ApiBase(BaseModel):
    model_config = ConfigDict(from_attributes=False)


class PriceOut(_ApiBase):
    price: Decimal
    source: str
    taken_at: datetime


class FormLineOut(_ApiBase):
    line_date: date | None
    track: str | None
    distance_m: int | None
    going: str | None
    finish_pos: int | None
    margin: Decimal | None
    weight_kg: Decimal | None
    note: str | None


class PredictionOut(_ApiBase):
    engine: str
    score: Decimal | None
    win_prob: Decimal | None
    rating: str | None
    rationale: str | None
    created_at: datetime


class RunnerOut(_ApiBase):
    id: int
    number: int
    name: str
    jockey: str | None
    trainer: str | None
    barrier: int | None
    weight_kg: Decimal | None
    silk: str | None
    scratched: bool
    # True when this runner originated from the curated seed JSON (connections trusted).
    # False when it was added by /admin/expand-field — treat connections as research-derived.
    seeded: bool
    form_lines: list[FormLineOut]
    current_price: PriceOut | None
    price_history: list[PriceOut]
    prediction: PredictionOut | None


class TopPickOut(_ApiBase):
    rank: int
    runner_id: int
    runner_number: int
    runner_name: str
    rationale: str | None
    source: str
    created_at: datetime


class RaceOut(_ApiBase):
    id: int
    number: int
    name: str
    distance_m: int | None
    klass: str | None
    start_time_local: time | None
    status: str
    runners: list[RunnerOut]
    top_picks: list[TopPickOut]
    summary: RaceSummaryOut | None = None


class RaceSummaryOut(_ApiBase):
    text: str
    model: str
    updated_at: datetime


class MeetingOut(_ApiBase):
    id: int
    track: str
    date: date
    going: str | None
    rail: str | None
    timezone: str
    races: list[RaceOut]


class MovementAlertOut(_ApiBase):
    id: int
    runner_id: int
    runner_name: str
    race_id: int
    race_number: int
    meeting_id: int
    track: str
    from_price: Decimal
    to_price: Decimal
    pct_change: Decimal
    direction: str
    baseline: str
    created_at: datetime


class StatusOut(_ApiBase):
    race_date: date
    race_date_end: date
    odds_source: str
    race_card_source: str
    prediction_engine: str
    last_snapshot_at: datetime | None
    snapshot_count: int
    alert_count: int
    in_window: bool


class ErrorOut(_ApiBase):
    error: str
    detail: str | None = None
