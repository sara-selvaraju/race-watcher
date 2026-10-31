from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from race_watcher.adapters.openrouter import OpenRouterAdapter
from race_watcher.adapters.seed import SeedFileAdapter
from race_watcher.agents import DailyAt, Every, agents, daily_times, interval_seconds
from race_watcher.core.config import settings
from race_watcher.db import models as m
from race_watcher.db.base import Base
from race_watcher.services.admin_overview import describe_schedule, overview
from race_watcher.services.agent_runs import record_run
from race_watcher.services.ingest import ingest_meetings
from race_watcher.worker.main import DAILY_JOBS, TIMER_JOBS


@pytest.fixture
def session(tiny_seed: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "race_date", date(2026, 6, 20))
    monkeypatch.setattr(settings, "race_date_end", None)
    # One shared connection, so runs recorded in their own session land in the same database.
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        ingest_meetings(s, SeedFileAdapter(path=tiny_seed))
        s.commit()
        yield s


def test_agent_list_drives_the_worker_timings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "poll_interval_seconds", 1200)
    monkeypatch.setattr(settings, "odds_check_times", "09:15, 11:00")
    keys = [a.key for a in agents()]
    assert len(keys) == len(set(keys))
    assert set(TIMER_JOBS) | set(DAILY_JOBS) <= set(keys)
    assert interval_seconds("odds") == 1200
    assert daily_times("odds") == (time(9, 15), time(11, 0))
    assert interval_seconds("notes") == 600


def test_schedules_read_as_plain_english() -> None:
    assert (
        describe_schedule(Every(900, covers="races jumping soon")) == "Every 15 min, for races jumping soon"
    )
    assert describe_schedule(DailyAt((time(9, 15),))).startswith("9:15am on race days")
    ratings = next(a for a in agents() if a.key == "ratings")
    assert describe_schedule(ratings.schedules[0]) == "Just before the race-note writer, in the same job"


def test_record_run_saves_result_and_sites(session: Session) -> None:
    with record_run(session, "odds", "timer") as run:
        run.races = 2
        run.result = "20 prices, 1 moves"
        run.sites = {"tab.com.au": 2}
    row = session.scalars(select(m.AgentRun)).one()
    assert (row.agent, row.status, row.races, row.sites) == ("odds", "ok", 2, {"tab.com.au": 2})


def test_record_run_logs_failures_and_reraises(session: Session) -> None:
    with pytest.raises(ValueError), record_run(session, "tipster", "refresh"):
        raise ValueError("no key")
    row = session.scalars(select(m.AgentRun)).one()
    assert row.status == "error"
    assert row.error == "ValueError: no key"


def test_overview_shows_next_runs_and_hides_idle_checks(session: Session) -> None:
    now = datetime(2026, 6, 19, 22, 0, tzinfo=UTC)  # 8am Melbourne on race day
    session.add(
        m.AgentRun(
            agent="odds",
            trigger="timer",
            started_at=now - timedelta(minutes=20),
            status="ok",
            races=1,
            result="10 prices, 0 moves",
        )
    )
    session.add(
        m.AgentRun(
            agent="odds", trigger="timer", started_at=now - timedelta(minutes=5), status="idle", races=0
        )
    )
    session.commit()

    out = overview(session, now=now)
    odds = next(a for a in out.agents if a.key == "odds")
    # Next timer run is 15 min after the last one (idle or not); the 9:15 check is later.
    assert odds.next_run == now + timedelta(minutes=10)
    assert [r.result for r in odds.runs] == ["10 prices, 0 moves"]
    assert odds.last_checked == now - timedelta(minutes=5)
    assert out.watching[0].track == "Flemington" and out.watching[0].loaded_races == 1


def test_morning_check_is_next_on_a_race_day(session: Session) -> None:
    now = datetime(2026, 6, 19, 1, 0, tzinfo=UTC)  # the day before, no timer runs yet
    odds = next(a for a in overview(session, now=now).agents if a.key == "odds")
    assert odds.next_run == datetime(2026, 6, 19, 23, 15, tzinfo=UTC)  # 9:15am AEST, 20 June


def test_adapter_counts_cited_sites_by_domain() -> None:
    adapter = OpenRouterAdapter(client=object())
    adapter._note_sites(["https://www.tab.com.au/racing/1", "https://www.tab.com.au/racing/2"])
    adapter._note_sites(["https://racing.com/form", "not a url"])
    assert adapter.take_sites() == {"tab.com.au": 1, "racing.com": 1}
    assert adapter.take_sites() == {}
