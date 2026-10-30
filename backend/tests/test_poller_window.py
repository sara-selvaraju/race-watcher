from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from race_watcher.adapters.seed import SeedFileAdapter
from race_watcher.core.config import settings
from race_watcher.db.base import Base
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.poller import poll_once


class _CountingOdds:
    name = "fake"

    def __init__(self) -> None:
        self.races_asked: list[int] = []

    def fetch_prices(self, meeting):
        self.races_asked.extend(r.number for r in meeting.races)
        return []


@pytest.fixture
def session(tiny_seed: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "race_date", datetime(2026, 6, 20).date())
    monkeypatch.setattr(settings, "race_date_end", None)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        ingest_meetings(s, SeedFileAdapter(path=tiny_seed))
        s.commit()
        yield s


def test_poll_inside_window_asks_for_races_still_to_run(session: Session) -> None:
    odds = _CountingOdds()
    poll_once(session, odds, now=datetime(2026, 6, 20, 0, 30, tzinfo=UTC))  # 10:30 Melbourne
    assert odds.races_asked == [1]


def test_poll_outside_window_costs_nothing(session: Session) -> None:
    odds = _CountingOdds()
    poll_once(session, odds, now=datetime(2026, 6, 19, 0, 0, tzinfo=UTC))
    assert odds.races_asked == []


def test_each_race_is_fetched_in_its_own_request(
    tiny_seed: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import json

    data = json.loads(tiny_seed.read_text())
    late = json.loads(json.dumps(data["races"][0]))
    late.update(number=2, start_time="15:30")
    data["races"].append(late)
    seed = tmp_path / "two-races.json"
    seed.write_text(json.dumps(data))
    monkeypatch.setattr(settings, "race_date", datetime(2026, 6, 20).date())
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        ingest_meetings(s, SeedFileAdapter(path=seed))
        s.commit()
        calls: list[list[int]] = []

        class Odds:
            name = "fake"

            def fetch_prices(self, meeting):
                calls.append([r.number for r in meeting.races])
                return []

        # 10:30 Melbourne: R1 (11:55) is in its 2-hour build-up, R2 (15:30) isn't yet.
        poll_once(s, Odds(), now=datetime(2026, 6, 20, 0, 30, tzinfo=UTC))
        assert calls == [[1]]
        # Refresh (forced) fetches every race still to run, one request each.
        calls.clear()
        poll_once(s, Odds(), now=datetime(2026, 6, 20, 0, 30, tzinfo=UTC), force=True)
        assert sorted(calls) == [[1], [2]]


def test_forced_poll_skips_races_that_have_run(session: Session) -> None:
    odds = _CountingOdds()
    poll_once(session, odds, now=datetime(2026, 6, 20, 6, 0, tzinfo=UTC), force=True)
    assert odds.races_asked == []
