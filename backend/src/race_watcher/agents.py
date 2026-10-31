"""Every agent the app runs, in one place.

Each entry says what the agent does, when it runs, which model it uses, what it looks at and
what it reads and writes. The worker takes its schedules from here, and the admin page shows
this list, so the page always matches what's actually running.

To add an agent:
  1. Write the function that does the work (usually a service in `services/`, calling an
     adapter method in `adapters/`).
  2. Add an `Agent` entry to `agents()` below.
  3. If it runs on a timer, add its function to the worker's job table (`worker/main.py`).
  4. Wrap its runs in `record_run` (`services/agent_runs.py`) so they show on the admin page.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import time

from race_watcher.core.config import settings


@dataclass(frozen=True)
class Every:
    """Runs on a timer in the worker."""

    seconds: int
    # Narrows what each run covers, e.g. "races jumping in the next 2 hours".
    covers: str | None = None


@dataclass(frozen=True)
class DailyAt:
    """Runs at fixed times of day, in TZ."""

    times: tuple[time, ...]
    covers: str | None = None


@dataclass(frozen=True)
class WithAgent:
    """Runs as part of another agent's job, just before it."""

    agent: str


@dataclass(frozen=True)
class OnRefresh:
    """Only runs when an admin presses Refresh."""


Schedule = Every | DailyAt | WithAgent | OnRefresh


@dataclass(frozen=True)
class Agent:
    key: str
    name: str
    purpose: str
    how: str
    schedules: tuple[Schedule, ...]
    # None for agents that don't use an LLM.
    model: str | None
    web_search: bool
    looks_at: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    prompt: str | None = None


def _daily_times() -> tuple[time, ...]:
    out = []
    for hhmm in filter(None, (t.strip() for t in settings.odds_check_times.split(","))):
        hour, minute = (int(x) for x in hhmm.split(":"))
        out.append(time(hour, minute))
    return tuple(out)


def _openrouter_model(base: str, *, online: bool) -> str:
    return f"{base}:online" if online and settings.openrouter_web_search and not base.endswith(":online") else base


def agents() -> list[Agent]:
    """The agents, built from current settings (models and timings can change per deploy)."""
    from race_watcher.adapters import openrouter as orr

    llm = settings.odds_source == "openrouter"
    lead_h = settings.race_window_open_min_before / 60
    research = settings.openrouter_research_model

    return [
        Agent(
            key="odds",
            name="Odds agent",
            purpose="Finds each runner's current fixed-odds win price, one race at a time.",
            how=(
                "Sends one web-search request per race with that race's runners, and gets back a "
                f"price for each from a single bookmaker ({', then '.join(orr.BOOKMAKERS)}). Each "
                "price is saved as a new snapshot. A move of "
                f"{settings.movement_threshold_pct:g}% or more against the same bookmaker's "
                "earlier price is saved as a market move. Up to 4 races are checked at once."
            ),
            schedules=(
                Every(settings.poll_interval_seconds, covers=f"races jumping in the next {lead_h:g} hours"),
                DailyAt(_daily_times(), covers="every race on the day's card"),
                OnRefresh(),
            ),
            model=_openrouter_model(settings.openrouter_model, online=True) if llm else None,
            web_search=llm,
            looks_at=f"Bookmaker markets found by web search: {', '.join(orr.BOOKMAKERS)}",
            reads=("Race card: runners and saddlecloth numbers",),
            writes=("Price snapshots", "Market moves"),
            prompt=orr.SYSTEM_PROMPT if llm else None,
        ),
        Agent(
            key="ratings",
            name="Ratings",
            purpose="Turns prices into a win chance for every runner. Not AI: a simple formula.",
            how=(
                "Converts each runner's latest price (or the card's preview price) into an implied "
                "chance, adds a little for tipster consensus and wet-track form, then scales the "
                "race to 100%. Races that have run are skipped."
            ),
            schedules=(WithAgent("notes"), OnRefresh()),
            model=None,
            web_search=False,
            looks_at="Nothing outside the database",
            reads=("Latest prices", "Preview prices", "Form notes"),
            writes=("Win chance and rating per runner",),
        ),
        Agent(
            key="notes",
            name="Race-note writer",
            purpose="Writes the short plain-English note on why the picks are the picks.",
            how=(
                "Builds a fixed list of facts for each race still to run (picks, prices, form, "
                "ratings) and asks the model to explain them using nothing else. A race is only "
                "rewritten when its facts have changed, so a quiet market costs nothing."
            ),
            schedules=(Every(600, covers="races still to run whose facts changed"), OnRefresh()),
            model=settings.openrouter_model if llm else None,
            web_search=False,
            looks_at="Nothing outside the database: no web access",
            reads=("Top picks", "Prices", "Form", "Ratings"),
            writes=("Race notes",),
            prompt=orr.SUMMARY_SYSTEM if llm else None,
        ),
        Agent(
            key="tipster",
            name="Tipster",
            purpose="Researches three picks per race, with links to its sources.",
            how=(
                "Reads the racing.com form guide and tips for the race first, then broadens to "
                "other tipsters and previews. Every claim in a pick's reasoning must carry a "
                "numbered link to where it was read."
            ),
            schedules=(OnRefresh(),),
            model=research if llm else None,
            web_search=llm,
            looks_at="racing.com first, then punters.com.au, racenet.com.au, bookmaker previews and tipster columns",
            reads=("Race card: runners",),
            writes=("Top picks and their sources",),
            prompt=orr.TOP_PICKS_SYSTEM if llm else None,
        ),
        Agent(
            key="field",
            name="Field checker",
            purpose="Looks for runners missing from the race card and adds them as unverified.",
            how=(
                "Reads the full field for one race from a single racing.com or racenet.com.au "
                "page. Answers citing any other site are thrown away. Runners already on the "
                "card are kept; missing jockey, trainer or barrier details are filled in."
            ),
            schedules=(OnRefresh(),),
            model=research if llm else None,
            web_search=llm,
            looks_at="racing.com, else racenet.com.au. Nothing else is accepted",
            reads=("Race card: race name, distance",),
            writes=("Extra runners (marked unverified)",),
            prompt=orr.FIELD_SYSTEM if llm else None,
        ),
    ]


def agent(key: str) -> Agent:
    return next(a for a in agents() if a.key == key)


def interval_seconds(key: str) -> int | None:
    return next((s.seconds for s in agent(key).schedules if isinstance(s, Every)), None)


def daily_times(key: str) -> tuple[time, ...]:
    return next((s.times for s in agent(key).schedules if isinstance(s, DailyAt)), ())
