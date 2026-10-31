from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from race_watcher.agents import agents
from race_watcher.api.deps import (
    CardSourceDep,
    EngineDep,
    OddsSourceDep,
    SessionDep,
    require_admin,
)
from race_watcher.api.v1.schemas.responses import (
    AdminOverviewOut,
    ModelOptionOut,
    PlaygroundIn,
    PlaygroundOut,
    SetModelIn,
)
from race_watcher.domain.ports import OddsSource, PredictionEngine, RaceCardSource
from race_watcher.services.admin_overview import model_option, overview
from race_watcher.services.agent_models import catalogue, model_problem, set_model
from race_watcher.services.agent_runs import collect, model_used, record_run
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.poller import describe_poll, poll_once
from race_watcher.services.predictions import run_predictions_for_race
from race_watcher.services.watched import watched_meetings, watched_races

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

@router.get("/overview", response_model=AdminOverviewOut)
def admin_overview(session: Session = SessionDep) -> AdminOverviewOut:
    """The agents (schedules, models, prompts, recent runs), what's watched, and key settings."""
    return overview(session)


@router.get("/models", response_model=list[ModelOptionOut])
def list_models() -> list[ModelOptionOut]:
    """OpenRouter's current models, with prices, for the admin page's model picker."""
    listed = catalogue()
    if listed is None:
        raise HTTPException(status_code=502, detail="Couldn't fetch OpenRouter's model list")
    return [model_option(info) for info in sorted(listed.values(), key=lambda i: i.id)]


@router.put("/agents/{key}/model", response_model=AdminOverviewOut)
def choose_model(key: str, body: SetModelIn, session: Session = SessionDep) -> AdminOverviewOut:
    """Choose an agent's model, used from its next run. `model: null` goes back to the default."""
    spec = next((a for a in agents() if a.key == key), None)
    if spec is None:
        raise HTTPException(status_code=404, detail=f"No agent called {key!r}")
    if spec.model_setting is None:
        raise HTTPException(status_code=400, detail=f"{spec.name} doesn't use an AI model")
    model = (body.model or "").strip().removesuffix(":online") or None
    if model is not None:
        problem = model_problem(spec.name, spec.needs_tools, model)
        if problem:
            raise HTTPException(status_code=400, detail=problem)
        if model == spec.default_model:
            model = None  # choosing the default is the same as going back to it
    set_model(session, key, model)
    return overview(session)


@router.post("/playground", response_model=PlaygroundOut)
def playground(body: PlaygroundIn, session: Session = SessionDep) -> PlaygroundOut:
    """Run one agent once on one race, with any model, and return what it produced. Spends real
    OpenRouter credit, but saves nothing: the race page and run log are unchanged."""
    from race_watcher.services.playground import PlaygroundError, run_playground

    try:
        return run_playground(session, body.agent, body.race_id, body.model)
    except PlaygroundError as exc:
        raise HTTPException(status_code=exc.status, detail=str(exc)) from exc


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
        run.model = model_used(odds, "odds")
        result = poll_once(session, odds, meeting_id=meeting_id, force=True)
        run.races = result.get("races", 0)
        run.result = describe_poll(result)
        collect(run, odds)
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
        run.model = model_used(odds, "tipster")
        result = refresh_all_races(session, odds, meeting_id)
        run.races = result.get("races", 0)
        run.result = f"{result.get('picks', 0)} picks in {run.races} races"
        collect(run, odds)
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
        run.model = model_used(odds, "field")
        result = expand_all_races(session, odds, meeting_id)
        run.races = result.get("races", 0)
        run.result = f"{result.get('added', 0)} runners added, {result.get('updated', 0)} updated"
        collect(run, odds)
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
        run.model = model_used(odds, "notes")
        result = summarize_all(session, odds, meeting_id, force=force)
        collect(run, odds)
        run.races = result.get("written", 0) + result.get("unchanged", 0) + result.get("failed", 0)
        run.result = describe_notes(result)
    return {"source": odds.name, **result}
