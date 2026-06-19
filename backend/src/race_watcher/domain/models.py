from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class _Base(BaseModel):
    model_config = ConfigDict(frozen=True)


class DomainFormLine(_Base):
    line_date: date | None = None
    track: str | None = None
    distance_m: int | None = None
    going: str | None = None
    finish_pos: int | None = None
    margin: Decimal | None = None
    weight_kg: Decimal | None = None
    note: str | None = None


class DomainRunner(_Base):
    number: int
    name: str
    jockey: str | None = None
    trainer: str | None = None
    barrier: int | None = None
    weight_kg: Decimal | None = None
    silk: str | None = None
    scratched: bool = False
    betfair_selection_id: int | None = None
    form_lines: tuple[DomainFormLine, ...] = ()
    # seed-supplied indicative odds, if any
    seed_price: Decimal | None = None
    seed_price_source: str | None = None
    # seed-supplied tipster prediction, if any
    seed_prediction_rating: str | None = None
    seed_prediction_rationale: str | None = None


class DomainRace(_Base):
    number: int
    name: str
    distance_m: int | None = None
    klass: str | None = None
    start_time_local: time | None = None
    runners: tuple[DomainRunner, ...] = ()


class DomainMeeting(_Base):
    track: str
    date: date
    going: str | None = None
    rail: str | None = None
    timezone: str = "Australia/Melbourne"
    source: str = "seed"
    races: tuple[DomainRace, ...] = ()


class DomainPrice(_Base):
    runner_number: int
    race_number: int
    price: Decimal
    source: str
    taken_at: datetime


class DomainPrediction(_Base):
    runner_id: int
    engine: str
    score: Decimal | None = None
    win_prob: Decimal | None = None
    rating: str | None = None
    rationale: str | None = None
