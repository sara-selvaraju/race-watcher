from __future__ import annotations

from fastapi import APIRouter
from sqlalchemy.orm import Session

from race_watcher.api.deps import CardSourceDep, EngineDep, OddsSourceDep, SessionDep
from race_watcher.core.config import settings
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource
from race_watcher.repositories import race_repo
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.poller import poll_once
from race_watcher.services.predictions import run_predictions_for_race

router = APIRouter(prefix="/admin", tags=["admin"])

# Every LLM-backed action below accepts an optional `meeting_id` so the frontend can refresh one
# track at a time; omitted, it runs across every meeting on RACE_DATE.


@router.post("/ingest")
def ingest(
    session: Session = SessionDep,
    source: RaceCardSource = CardSourceDep,
) -> dict:
    meetings = ingest_meetings(session, source)
    return {
        "meetings": [
            {"meeting_id": mt.id, "track": mt.track, "date": str(mt.date)} for mt in meetings
        ]
    }


@router.post("/predict")
def predict(
    session: Session = SessionDep,
    engine: PredictionEngine = EngineDep,
    meeting_id: int | None = None,
) -> dict:
    meetings = race_repo.list_meetings_between(session, *settings.race_days, meeting_id)
    if not meetings:
        return {"created": 0, "skipped": "no_meeting"}
    created = 0
    for meeting in meetings:
        for race in meeting.races:
            created += len(run_predictions_for_race(session, race, engine))
    session.commit()
    return {"created": created}


@router.post("/refresh-odds")
def refresh_odds(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
    meeting_id: int | None = None,
) -> dict:
    """Run the configured OddsSource once (on-demand) and write price snapshots + movement alerts.

    Bypasses the race-window gate so it works any time. Use this in place of the 5-min worker poll.
    """
    result = poll_once(session, odds, meeting_id=meeting_id, force=True)
    return {"source": odds.name, **result}


@router.post("/refresh-tips")
def refresh_tips(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
    meeting_id: int | None = None,
) -> dict:
    """Run the LLM research agent once per race to refresh top-3 picks.

    Re-uses the OpenRouter odds adapter (it has a fetch_race_top_picks() method).
    Idempotent: replaces prior picks per race.
    """
    from race_watcher.services.top_picks import refresh_all_races

    result = refresh_all_races(session, odds, meeting_id)
    return {"source": odds.name, **result}


@router.post("/expand-field")
def expand_field(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
    meeting_id: int | None = None,
) -> dict:
    """Research the full field per race and add any missing runners.

    Re-uses the OpenRouter adapter (fetch_race_field). Existing runners are not clobbered;
    missing jockey/trainer/barrier/scratched on existing rows are backfilled if found.
    """
    from race_watcher.services.expand_field import expand_all_races

    result = expand_all_races(session, odds, meeting_id)
    return {"source": odds.name, **result}


@router.post("/cleanup-research-runners")
def cleanup_research_runners(
    session: Session = SessionDep, meeting_id: int | None = None
) -> dict:
    """Delete every runner on the race date that originated from /admin/expand-field
    (i.e. not in the curated seed JSON).

    Use this when Sonar has stacked hallucinated or duplicate runners and you want to
    reset the field back to the seed-only state. Top picks and predictions for the
    deleted runners cascade away via the existing FK ondelete=CASCADE.
    """
    meetings = race_repo.list_meetings_between(session, *settings.race_days, meeting_id)
    if not meetings:
        return {"deleted": 0, "skipped": "no_meeting"}

    deleted = 0
    for meeting in meetings:
        for race in meeting.races:
            for runner in list(race.runners):
                if runner.seed_price_source is None and runner.seed_price is None:
                    session.delete(runner)
                    deleted += 1
    session.commit()
    return {"deleted": deleted}


@router.post("/summarize")
def summarize(
    session: Session = SessionDep,
    odds: OddsSource = OddsSourceDep,
    meeting_id: int | None = None,
    force: bool = False,
) -> dict:
    """Write plain-English notes on each upcoming race's picks from data already stored.

    Races whose facts haven't changed since the last summary are skipped unless `force`.
    """
    from race_watcher.services.race_summary import summarize_all

    return {"source": odds.name, **summarize_all(session, odds, meeting_id, force=force)}
