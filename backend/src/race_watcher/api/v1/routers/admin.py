from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from race_watcher.api.deps import (
    CardSourceDep,
    EngineDep,
    OddsSourceDep,
    SessionDep,
    require_admin,
)
from race_watcher.api.v1.schemas.responses import AdminOverviewOut
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource
from race_watcher.services.admin_overview import overview
from race_watcher.services.agent_runs import record_run, take_sites
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.poller import describe_poll, poll_once
from race_watcher.services.predictions import run_predictions_for_race
from race_watcher.services.watched import watched_meetings, watched_races

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/overview", response_model=AdminOverviewOut)
def admin_overview(session: Session = SessionDep) -> AdminOverviewOut:
    """The agents (schedules, models, prompts, recent runs), what's watched, and key settings."""
    return overview(session)


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
    meetings = watched_meetings(session, meeting_id)
    if not meetings:
        return {"created": 0, "skipped": "no_meeting"}
    created = 0
    with record_run(session, "ratings", "refresh") as run:
        for meeting in meetings:
            for race in watched_races(meeting):
                created += len(run_predictions_for_race(session, race, engine))
                run.races += 1
        session.commit()
        run.result = f"{created} runners rated"
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
    with record_run(session, "odds", "refresh") as run:
        result = poll_once(session, odds, meeting_id=meeting_id, force=True)
        run.races = result.get("races", 0)
        run.result = describe_poll(result)
        run.sites = take_sites(odds)
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

    with record_run(session, "tipster", "refresh") as run:
        result = refresh_all_races(session, odds, meeting_id)
        run.races = result.get("races", 0)
        run.result = f"{result.get('picks', 0)} picks in {run.races} races"
        run.sites = take_sites(odds)
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

    with record_run(session, "field", "refresh") as run:
        result = expand_all_races(session, odds, meeting_id)
        run.races = result.get("races", 0)
        run.result = f"{result.get('added', 0)} runners added, {result.get('updated', 0)} updated"
        run.sites = take_sites(odds)
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
    meetings = watched_meetings(session, meeting_id)
    if not meetings:
        return {"deleted": 0, "skipped": "no_meeting"}

    deleted = 0
    for meeting in meetings:
        for race in watched_races(meeting):
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
    from race_watcher.services.race_summary import describe_notes, summarize_all

    with record_run(session, "notes", "refresh") as run:
        result = summarize_all(session, odds, meeting_id, force=force)
        run.races = result.get("written", 0) + result.get("unchanged", 0) + result.get("failed", 0)
        run.result = describe_notes(result)
    return {"source": odds.name, **result}
