from __future__ import annotations

from datetime import date, datetime, time
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Time,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from race_watcher.db.base import Base


class Meeting(Base):
    __tablename__ = "meeting"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    track: Mapped[str] = mapped_column(String(80))
    date: Mapped[date] = mapped_column(Date)
    going: Mapped[str | None] = mapped_column(String(40), default=None)
    rail: Mapped[str | None] = mapped_column(String(80), default=None)
    timezone: Mapped[str] = mapped_column(String(40), default="Australia/Melbourne")
    source: Mapped[str] = mapped_column(String(40), default="seed")

    races: Mapped[list["Race"]] = relationship(
        back_populates="meeting", cascade="all, delete-orphan", default_factory=list
    )

    __table_args__ = (UniqueConstraint("track", "date", name="uq_meeting_track_date"),)


class Race(Base):
    __tablename__ = "race"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    meeting_id: Mapped[int] = mapped_column(ForeignKey("meeting.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(160))
    distance_m: Mapped[int | None] = mapped_column(Integer, default=None)
    klass: Mapped[str | None] = mapped_column(String(40), default=None)
    start_time_local: Mapped[time | None] = mapped_column(Time, default=None)
    status: Mapped[str] = mapped_column(String(20), default="open")

    meeting: Mapped[Meeting] = relationship(back_populates="races", default=None)
    runners: Mapped[list["Runner"]] = relationship(
        back_populates="race", cascade="all, delete-orphan", default_factory=list
    )

    __table_args__ = (UniqueConstraint("meeting_id", "number", name="uq_race_meeting_number"),)


class Runner(Base):
    __tablename__ = "runner"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    race_id: Mapped[int] = mapped_column(ForeignKey("race.id", ondelete="CASCADE"))
    number: Mapped[int] = mapped_column(Integer)
    name: Mapped[str] = mapped_column(String(120))
    jockey: Mapped[str | None] = mapped_column(String(80), default=None)
    trainer: Mapped[str | None] = mapped_column(String(80), default=None)
    barrier: Mapped[int | None] = mapped_column(Integer, default=None)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    silk: Mapped[str | None] = mapped_column(String(160), default=None)
    scratched: Mapped[bool] = mapped_column(Boolean, default=False)
    betfair_selection_id: Mapped[int | None] = mapped_column(Integer, default=None)

    race: Mapped[Race] = relationship(back_populates="runners", default=None)
    form_lines: Mapped[list["FormLine"]] = relationship(
        back_populates="runner", cascade="all, delete-orphan", default_factory=list
    )

    __table_args__ = (UniqueConstraint("race_id", "number", name="uq_runner_race_number"),)


class FormLine(Base):
    __tablename__ = "form_line"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runner.id", ondelete="CASCADE"))
    line_date: Mapped[date | None] = mapped_column(Date, default=None)
    track: Mapped[str | None] = mapped_column(String(80), default=None)
    distance_m: Mapped[int | None] = mapped_column(Integer, default=None)
    going: Mapped[str | None] = mapped_column(String(40), default=None)
    finish_pos: Mapped[int | None] = mapped_column(Integer, default=None)
    margin: Mapped[Decimal | None] = mapped_column(Numeric(6, 2), default=None)
    weight_kg: Mapped[Decimal | None] = mapped_column(Numeric(5, 2), default=None)
    note: Mapped[str | None] = mapped_column(String(800), default=None)

    runner: Mapped[Runner] = relationship(back_populates="form_lines", default=None)


class PriceSnapshot(Base):
    __tablename__ = "price_snapshot"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runner.id", ondelete="CASCADE"))
    source: Mapped[str] = mapped_column(String(40))
    price: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    taken_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_price_snapshot_runner_taken", "runner_id", "taken_at"),
    )


class Prediction(Base):
    __tablename__ = "prediction"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runner.id", ondelete="CASCADE"))
    engine: Mapped[str] = mapped_column(String(40))
    score: Mapped[Decimal | None] = mapped_column(Numeric(6, 3), default=None)
    win_prob: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), default=None)
    rating: Mapped[str | None] = mapped_column(String(40), default=None)
    rationale: Mapped[str | None] = mapped_column(String(800), default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class MovementAlert(Base):
    __tablename__ = "movement_alert"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, init=False)
    runner_id: Mapped[int] = mapped_column(ForeignKey("runner.id", ondelete="CASCADE"))
    from_price: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    to_price: Mapped[Decimal] = mapped_column(Numeric(8, 3))
    pct_change: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    direction: Mapped[str] = mapped_column(String(10))  # "firm" | "drift"
    baseline: Mapped[str] = mapped_column(String(20))  # "previous" | "open"
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    __table_args__ = (
        Index("ix_movement_alert_runner_created", "runner_id", "created_at"),
    )
