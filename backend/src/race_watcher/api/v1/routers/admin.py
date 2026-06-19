from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from race_watcher.api.deps import CardSourceDep, EngineDep, OddsSourceDep, SessionDep
from race_watcher.core.config import settings
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource
from race_watcher.repositories import race_repo
from race_watcher.services.ingest import ingest_meeting
from race_watcher.services.poller import poll_once
from race_watcher.services.predictions import run_predictions_for_race

router = APIRouter(prefix="/admin", tags=["admin"])


@router.post("/ingest")
def ingest(
    session: Session = SessionDep,
    source: RaceCardSource = CardSourceDep,
) -> dict:
    meeting = ingest_meeting(session, source)
    return {"meeting_id": meeting.id, "track": meeting.track, "date": str(meeting.date)}


@router.post("/predict")
def predict(
    session: Session = SessionDep,
    engine: PredictionEngine = EngineDep,
) -> dict:
    meeting = race_repo.get_meeting_by_date(session, settings.race_date)
    if meeting is None:
        return {"created": 0, "skipped": "no_meeting"}
    created = 0
    for race in meeting.races:
        created += len(run_predictions_for_race(session, race, engine))
    session.commit()
    return {"created": created}


@router.post("/refresh-odds")
def refresh_odds(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
) -> dict:
    """Run the configured OddsSource once (on-demand) and write price snapshots + movement alerts.

    Bypasses the race-window gate so it works any time. Use this in place of the 5-min worker poll.
    """
    result = poll_once(session, odds, force=True)
    return {"source": odds.name, **result}


@router.post("/refresh-tips")
def refresh_tips(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
) -> dict:
    """Run the LLM research agent once per race to refresh top-3 picks.

    Re-uses the OpenRouter odds adapter (it has a fetch_race_top_picks() method).
    Idempotent: replaces prior picks per race.
    """
    from race_watcher.services.top_picks import refresh_all_races

    result = refresh_all_races(session, odds)
    return {"source": odds.name, **result}
