from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from race_watcher.adapters import get_race_card_source
from race_watcher.core.config import settings
from race_watcher.core.watchlist import watchlist
from race_watcher.db import models as m
from race_watcher.db.base import Base
from race_watcher.services.poller import poll_once
from race_watcher.services.watched import watched_meetings, watched_races


def _write_watch(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, data: dict) -> Path:
    path = tmp_path / "watch.json"
    path.write_text(json.dumps(data))
    monkeypatch.setattr(settings, "watch_file_path", path)
    return path


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        for track, day in [("Flemington", 3), ("Flemington", 7), ("Randwick", 7), ("Flemington", 10)]:
            mt = m.Meeting(
                track=track, date=date(2026, 11, day), going=None, rail=None,
                timezone="Australia/Melbourne", source="test",
            )
            s.add(mt)
            s.flush()
            for n in range(1, 4):
                s.add(m.Race(meeting_id=mt.id, number=n, name=f"R{n}", distance_m=1200,
                             klass=None, start_time_local=datetime(2026, 1, 1, 12 + n).time()))
        s.commit()
        yield s


def test_without_a_watch_file_every_race_in_the_date_window_is_watched(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(settings, "race_date", date(2026, 11, 3))
    monkeypatch.setattr(settings, "race_date_end", date(2026, 11, 7))
    meetings = watched_meetings(session)
    assert [(mt.track, mt.date.day) for mt in meetings] == [
        ("Flemington", 3), ("Flemington", 7), ("Randwick", 7)
    ]
    assert [r.number for r in watched_races(meetings[0])] == [1, 2, 3]


def test_watch_file_picks_meetings_and_races(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_watch(tmp_path, monkeypatch, {"watch": [
        {"track": "flemington", "date": "2026-11-03"},
        {"track": "Randwick", "date": "2026-11-07", "races": [2]},
    ]})
    meetings = watched_meetings(session)
    assert [(mt.track, mt.date.day) for mt in meetings] == [("Flemington", 3), ("Randwick", 7)]
    assert [r.number for r in watched_races(meetings[0])] == [1, 2, 3]
    assert [r.number for r in watched_races(meetings[1])] == [2]
    assert (watchlist().start, watchlist().end) == (date(2026, 11, 3), date(2026, 11, 7))


def test_odds_are_only_fetched_for_watched_races(
    session: Session, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_watch(tmp_path, monkeypatch, {"watch": [
        {"track": "Randwick", "date": "2026-11-07", "races": [2, 3]},
    ]})
    asked: list[tuple[str, int]] = []

    class Odds:
        name = "fake"

        def fetch_prices(self, meeting):
            asked.extend((meeting.track, r.number) for r in meeting.races)
            return []

    poll_once(session, Odds(), now=datetime(2026, 11, 7, 1, 0, tzinfo=UTC), force=True)
    assert asked == [("Randwick", 2), ("Randwick", 3)]


def test_watch_file_card_is_resolved_next_to_the_watch_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_watch(tmp_path, monkeypatch, {
        "card": "seed/my-card.json",
        "watch": [{"track": "Flemington", "date": "2026-11-03"}],
    })
    assert watchlist().card == tmp_path / "seed" / "my-card.json"
    assert get_race_card_source().path == tmp_path / "seed" / "my-card.json"


def test_empty_watch_file_is_an_error(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _write_watch(tmp_path, monkeypatch, {"watch": []})
    with pytest.raises(ValueError, match="no meetings"):
        watchlist()
