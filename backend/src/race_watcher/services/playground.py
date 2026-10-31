"""Run one agent once, on one race, with any model, and show what it produced. Nothing is saved:
no prices, picks, runners or notes change, and the run isn't added to the run log."""

from __future__ import annotations

import time
from datetime import UTC, datetime

from sqlalchemy.orm import Session

from race_watcher.adapters import get_odds_source
from race_watcher.agents import agents
from race_watcher.api.v1.schemas.responses import (
    PlaygroundNoteOut,
    PlaygroundOut,
    PlaygroundPickOut,
    PlaygroundPriceOut,
    PlaygroundRunnerOut,
)
from race_watcher.core.logging import get_logger
from race_watcher.db import models as m
from race_watcher.domain.models import DomainMeeting
from race_watcher.repositories import price_repo, summary_repo
from race_watcher.services.agent_models import model_overrides, model_problem
from race_watcher.services.agent_runs import model_used

log = get_logger("playground")


class PlaygroundError(Exception):
    """The run can't start: unknown agent or race, or an unusable model."""

    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def _domain_meeting(meeting: m.Meeting) -> DomainMeeting:
    return DomainMeeting(
        track=meeting.track,
        date=meeting.date,
        going=meeting.going,
        rail=meeting.rail,
        timezone=meeting.timezone,
        source=meeting.source,
    )


def run_playground(session: Session, agent_key: str, race_id: int, model: str | None) -> PlaygroundOut:
    from race_watcher.services.expand_field import _to_domain_race as field_race
    from race_watcher.services.poller import _domain_race_meeting
    from race_watcher.services.race_summary import build_facts
    from race_watcher.services.top_picks import _to_domain_race as picks_race

    spec = next((a for a in agents() if a.key == agent_key), None)
    if spec is None:
        raise PlaygroundError(f"No agent called {agent_key!r}", 404)
    if spec.model_setting is None:
        raise PlaygroundError(f"{spec.name} doesn't use an AI model")
    race = session.get(m.Race, race_id)
    if race is None:
        raise PlaygroundError(f"No race with id {race_id}", 404)
    meeting = race.meeting
    if agent_key in ("odds", "tipster") and not race.runners:
        raise PlaygroundError(f"{meeting.track} R{race.number} has no runners on the card yet")

    models = model_overrides(session)
    if model:
        model = model.strip().removesuffix(":online")
        problem = model_problem(spec.name, spec.needs_tools, model)
        if problem:
            raise PlaygroundError(problem)
        models[agent_key] = model
    adapter = get_odds_source(models=models)

    started = datetime.now(UTC)
    t0 = time.monotonic()
    out: dict = {}
    error: str | None = None
    names = {r.number: r.name for r in race.runners}
    try:
        if agent_key == "odds":
            prices = adapter.fetch_prices(_domain_race_meeting(meeting, race))
            by_number = {r.number: r for r in race.runners}
            rows = []
            for p in sorted(prices, key=lambda p: p.runner_number):
                runner = by_number.get(p.runner_number)
                saved = price_repo.latest_price(session, runner.id) if runner else None
                rows.append(
                    PlaygroundPriceOut(
                        runner_number=p.runner_number,
                        runner_name=names.get(p.runner_number, "?"),
                        price=p.price,
                        source=p.source,
                        saved_price=saved.price if saved else None,
                        saved_source=saved.source if saved else None,
                    )
                )
            out["prices"] = rows
        elif agent_key == "tipster":
            picks = adapter.fetch_race_top_picks(_domain_meeting(meeting), picks_race(race))
            out["picks"] = [
                PlaygroundPickOut(
                    rank=p["rank"],
                    runner_number=p["runner_number"],
                    runner_name=names.get(p["runner_number"], "?"),
                    rationale=p.get("rationale"),
                )
                for p in picks
            ]
        elif agent_key == "field":
            runners = adapter.fetch_race_field(_domain_meeting(meeting), field_race(race))
            card = {n.casefold() for n in names.values()}
            out["field"] = [
                PlaygroundRunnerOut(
                    runner_number=r["runner_number"],
                    runner_name=r["runner_name"],
                    jockey=r.get("jockey"),
                    trainer=r.get("trainer"),
                    barrier=r.get("barrier"),
                    scratched=bool(r.get("scratched")),
                    on_card=r["runner_name"].casefold() in card,
                )
                for r in runners
            ]
        elif agent_key == "notes":
            facts = build_facts(session, meeting, race)
            current = summary_repo.get_for_race(session, race.id)
            out["note"] = PlaygroundNoteOut(
                text=adapter.summarize_race(facts),
                facts=facts,
                current=current.summary if current else None,
            )
        else:
            raise PlaygroundError(f"The playground can't run {spec.name} yet")
    except PlaygroundError:
        raise
    except Exception as exc:
        log.warning("playground.failed", agent=agent_key, race=race_id, error=str(exc))
        error = f"{type(exc).__name__}: {exc}"[:500]
    finally:
        session.rollback()  # belt and braces: nothing from a playground run is kept

    usage = adapter.take_usage() if hasattr(adapter, "take_usage") else None
    take_sites = getattr(adapter, "take_sites", None)
    return PlaygroundOut(
        agent=agent_key,
        agent_name=spec.name,
        model=model_used(adapter, agent_key) or (model or ""),
        race_id=race.id,
        race_label=f"{meeting.track} R{race.number}, {race.name} ({meeting.date:%a %-d %b})",
        started_at=started,
        seconds=round(time.monotonic() - t0, 1),
        calls=usage.calls if usage else 0,
        prompt_tokens=usage.prompt_tokens if usage else 0,
        completion_tokens=usage.completion_tokens if usage else 0,
        cost_usd=usage.cost if usage else None,
        sites=take_sites() if callable(take_sites) else {},
        error=error,
        **out,
    )
