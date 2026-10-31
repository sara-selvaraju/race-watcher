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

An agent's model can be changed on the admin page (saved in the database, see
`services/agent_models.py`); otherwise it uses the Railway variable named in `model_setting`.
"""

from __future__ import annotations

from collections.abc import Mapping
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
    # The model as called, e.g. with ":online" for web search. None for agents that don't use an LLM.
    model: str | None
    web_search: bool
    looks_at: str
    reads: tuple[str, ...]
    writes: tuple[str, ...]
    prompt: str | None = None
    # The model chosen on the admin page, else the default below.
    model_id: str | None = None
    # The Railway variable giving the default model, and its value.
    model_setting: str | None = None
    default_model: str | None = None
    # Suggested models for the admin page's picker (any OpenRouter model can be typed in).
    suggested: tuple[str, ...] = ()
    # The agent calls a tool to return its answer, so its model must support tool calling.
    needs_tools: bool = False


def _daily_times() -> tuple[time, ...]:
    out = []
    for hhmm in filter(None, (t.strip() for t in settings.odds_check_times.split(","))):
        hour, minute = (int(x) for x in hhmm.split(":"))
        out.append(time(hour, minute))
    return tuple(out)


def _with_web(base: str) -> str:
    """As the OpenRouter adapter calls it: ":online" adds web search; Perplexity has it built in."""
    if not settings.openrouter_web_search or base.startswith("perplexity/") or base.endswith(":online"):
        return base
    return f"{base}:online"


# Suggestions only: they're checked against OpenRouter's live list, and any model can be typed in.
GENERAL_MODELS = (
    "anthropic/claude-sonnet-4.5",
    "anthropic/claude-sonnet-5.5",
    "anthropic/claude-haiku-5.5",
    "openai/gpt-5-mini",
    "google/gemini-2.5-flash",
    "z-ai/glm-5.3",
)
RESEARCH_MODELS = (
    "perplexity/sonar-pro",
    "perplexity/sonar",
    "perplexity/sonar-reasoning-pro",
    "anthropic/claude-sonnet-5.5",
)


def agents(models: Mapping[str, str] | None = None) -> list[Agent]:
    """The agents, built from current settings and `models` (choices from the admin page)."""
    from race_watcher.adapters import openrouter as orr

    models = models or {}
    llm = settings.odds_source == "openrouter"
    lead_h = settings.race_window_open_min_before / 60
    chosen = {
        "odds": models.get("odds", settings.openrouter_model),
        "notes": models.get("notes", settings.openrouter_model),
        "tipster": models.get("tipster", settings.openrouter_research_model),
        "field": models.get("field", settings.openrouter_research_model),
    }

    def model_fields(key: str, *, web: bool, default_setting: str, suggested: tuple[str, ...]) -> dict:
        if not llm:
            return {"model": None}
        default = getattr(settings, default_setting.lower())
        return {
            "model": _with_web(chosen[key]) if web else chosen[key],
            "model_id": chosen[key],
            "model_setting": default_setting,
            "default_model": default,
            "suggested": suggested,
        }

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
            **model_fields("odds", web=True, default_setting="OPENROUTER_MODEL", suggested=GENERAL_MODELS),
            needs_tools=llm,
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
            **model_fields("notes", web=False, default_setting="OPENROUTER_MODEL", suggested=GENERAL_MODELS),
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
            **model_fields("tipster", web=True, default_setting="OPENROUTER_RESEARCH_MODEL", suggested=RESEARCH_MODELS),
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
            **model_fields("field", web=True, default_setting="OPENROUTER_RESEARCH_MODEL", suggested=RESEARCH_MODELS),
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
