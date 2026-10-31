"""A log of agent runs for the admin page: what ran, when, why, what it did and which sites it used."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from race_watcher.core.logging import get_logger
from race_watcher.db import models as m

log = get_logger("agent_runs")

KEEP_DAYS = 30


@dataclass
class Run:
    """Filled in by the code being recorded."""

    races: int = 0
    result: str | None = None
    sites: dict[str, int] = field(default_factory=dict)
    model: str | None = None
    tokens: int | None = None
    cost_usd: Decimal | None = None
    # Nothing to do (e.g. no race in its build-up). Recorded so the page can show the worker is alive.
    idle: bool = False


@contextmanager
def record_run(session: Session, agent: str, trigger: str) -> Iterator[Run]:
    """Record one run of `agent`. Saved in its own session so a failed run is still logged.

    Recording never breaks the work itself: if the log can't be written, it's only logged.
    """
    run = Run()
    started = datetime.now(UTC)
    error: str | None = None
    try:
        yield run
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}"[:500]
        raise
    finally:
        try:
            with Session(bind=session.get_bind()) as s:
                s.add(
                    m.AgentRun(
                        agent=agent,
                        trigger=trigger,
                        started_at=started,
                        finished_at=datetime.now(UTC),
                        status="error" if error else "idle" if run.idle else "ok",
                        races=run.races,
                        result=run.result,
                        sites=run.sites or None,
                        error=error,
                        model=run.model,
                        tokens=run.tokens,
                        cost_usd=run.cost_usd,
                    )
                )
                s.execute(delete(m.AgentRun).where(m.AgentRun.started_at < started - timedelta(days=KEEP_DAYS)))
                s.commit()
        except Exception as exc:
            log.warning("agent_runs.record_failed", agent=agent, error=str(exc))


def collect(run: Run, source: object) -> None:
    """Fill in the sites, tokens and cost an adapter used during the run."""
    run.sites = take_sites(source)
    take = getattr(source, "take_usage", None)
    usage = take() if callable(take) else None
    if usage is not None and usage.calls:
        run.tokens = usage.prompt_tokens + usage.completion_tokens
        run.cost_usd = usage.cost


def take_sites(source: object) -> dict[str, int]:
    """Sites an adapter cited since last asked (adapters without web search have none)."""
    take = getattr(source, "take_sites", None)
    return take() if callable(take) else {}


def model_used(source: object, agent: str) -> str | None:
    """The model `source` calls for `agent`, if it's an LLM adapter."""
    try:
        if agent == "odds":
            return getattr(source, "effective_model", None)
        if agent == "notes":
            return getattr(source, "summary_model", None)
        if agent in ("tipster", "field") and hasattr(source, "research_model_for"):
            return source.research_model_for(agent)
    except Exception:
        pass
    return None


def recent_runs(session: Session, agent: str, *, limit: int = 8) -> list[m.AgentRun]:
    """The agent's latest runs that did something (idle checks left out)."""
    return list(
        session.scalars(
            select(m.AgentRun)
            .where(m.AgentRun.agent == agent, m.AgentRun.status != "idle")
            .order_by(m.AgentRun.started_at.desc())
            .limit(limit)
        )
    )


def last_run(session: Session, agent: str, trigger: str | None = None) -> m.AgentRun | None:
    """The agent's latest run of any kind, including idle checks."""
    q = select(m.AgentRun).where(m.AgentRun.agent == agent)
    if trigger:
        q = q.where(m.AgentRun.trigger == trigger)
    return session.scalars(q.order_by(m.AgentRun.started_at.desc()).limit(1)).first()
