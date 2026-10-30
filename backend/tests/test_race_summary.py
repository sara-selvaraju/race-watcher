from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from race_watcher.adapters.heuristic import HeuristicEngine
from race_watcher.adapters.seed import SeedFileAdapter
from race_watcher.core.config import settings
from race_watcher.db import models as m
from race_watcher.db.base import Base
from race_watcher.repositories import race_repo, summary_repo
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.predictions import run_predictions_for_race
from race_watcher.services.race_summary import build_facts, summarize_all

# Before the tiny seed's 11:55 Melbourne start on 2026-06-20.
BEFORE_RACE = datetime(2026, 6, 20, 0, 0, tzinfo=UTC)
AFTER_RACE = datetime(2026, 6, 20, 6, 0, tzinfo=UTC)


class _FakeSummarizer:
    name = "fake"
    summary_model = "fake/model"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def summarize_race(self, facts: str) -> str:
        self.calls.append(facts)
        return f"note {len(self.calls)}"


@pytest.fixture
def session(tiny_seed: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "race_date", datetime(2026, 6, 20).date())
    monkeypatch.setattr(settings, "race_date_end", None)
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        ingest_meetings(s, SeedFileAdapter(path=tiny_seed))
        for meeting in race_repo.list_meetings_between(s, *settings.race_days):
            for race in meeting.races:
                run_predictions_for_race(s, race, HeuristicEngine())
        s.commit()
        yield s


def test_facts_list_heuristic_picks_in_rank_order(session: Session) -> None:
    meeting = race_repo.list_meetings_between(session, *settings.race_days)[0]
    facts = build_facts(session, meeting, meeting.races[0])
    assert "Picks from: heuristic rating" in facts
    assert facts.index("Pick 1: Alpha (1)") < facts.index("Pick 2: Bravo (2)")


def test_unchanged_facts_skip_the_llm(session: Session) -> None:
    fake = _FakeSummarizer()
    assert summarize_all(session, fake, now=BEFORE_RACE)["written"] == 1
    assert summarize_all(session, fake, now=BEFORE_RACE) == {"written": 0, "unchanged": 1, "failed": 0}
    assert len(fake.calls) == 1

    # A scratching changes the facts, so the note is rewritten.
    session.query(m.Runner).filter(m.Runner.name == "Charlie").one().scratched = True
    session.flush()
    assert summarize_all(session, fake, now=BEFORE_RACE)["written"] == 1
    race_id = session.query(m.Race).one().id
    assert summary_repo.get_for_race(session, race_id).summary == "note 2"


def test_races_that_have_run_are_skipped(session: Session) -> None:
    fake = _FakeSummarizer()
    assert summarize_all(session, fake, now=AFTER_RACE)["written"] == 0
    assert fake.calls == []


def test_form_figures_are_read_most_recent_first() -> None:
    from race_watcher.services.race_summary import describe_form

    assert describe_form("Last-10 figures 211x331x44") == (
        "most recent first: 4th, 4th, spell, 1st, 3rd, 3rd"
    )
    assert describe_form("Last 10: 6x50") == "most recent first: 10th or worse, 5th, spell, 6th"
    assert describe_form("Strong wet-track form.") == "Strong wet-track form."


def test_race_day_window_spans_carnival_days(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    later = m.Meeting(
        track="Flemington", date=datetime(2026, 6, 23).date(), going=None, rail=None,
        timezone="Australia/Melbourne", source="test",
    )
    session.add(later)
    session.flush()
    assert len(race_repo.list_meetings_between(session, *settings.race_days)) == 1

    monkeypatch.setattr(settings, "race_date_end", datetime(2026, 6, 23).date())
    dates = [mt.date for mt in race_repo.list_meetings_between(session, *settings.race_days)]
    assert dates == [datetime(2026, 6, 20).date(), datetime(2026, 6, 23).date()]
