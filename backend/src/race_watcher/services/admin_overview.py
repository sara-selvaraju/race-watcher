"""What the admin page shows: the agents with their schedules and recent runs, what's being
watched, and the settings that shape them."""

from __future__ import annotations

from datetime import UTC, datetime, time, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from race_watcher.agents import Agent, DailyAt, Every, OnRefresh, WithAgent, agent, agents
from race_watcher.api.v1.schemas.responses import (
    AdminOverviewOut,
    AgentModelOut,
    AgentOut,
    AgentRunOut,
    ModelOptionOut,
    SettingOut,
    WatchOut,
)
from race_watcher.core.config import settings
from race_watcher.core.watchlist import watchlist
from race_watcher.services.agent_models import ModelInfo, catalogue, model_choices
from race_watcher.services.agent_runs import last_run, recent_runs
from race_watcher.services.watched import watched_meetings, watched_races


def _minutes(seconds: int) -> str:
    return f"{seconds // 60} min" if seconds % 60 == 0 else f"{seconds} s"


def _clock(t: time) -> str:
    return f"{t.hour % 12 or 12}:{t.minute:02d}{'am' if t.hour < 12 else 'pm'}"


def describe_schedule(when) -> str:
    match when:
        case Every(seconds, covers):
            return f"Every {_minutes(seconds)}" + (f", for {covers}" if covers else "")
        case DailyAt(times, covers):
            at = ", ".join(_clock(t) for t in times)
            return f"{at} on race days ({settings.tz})" + (f", for {covers}" if covers else "")
        case WithAgent(key):
            return f"Just before the {agent(key).name.lower()}, in the same job"
        case OnRefresh():
            return "When an admin presses Refresh"
    return str(when)


def _next_run(session: Session, spec: Agent, race_days: list, now: datetime) -> datetime | None:
    found: list[datetime] = []
    tz = ZoneInfo(settings.tz)
    for when in spec.schedules:
        if isinstance(when, Every):
            last = last_run(session, spec.key, "timer")
            if last is not None:
                due = _aware(last.started_at) + timedelta(seconds=when.seconds)
                found.append(max(due, now))
        elif isinstance(when, DailyAt):
            for day in race_days:
                for t in when.times:
                    at = datetime.combine(day, t, tzinfo=tz).astimezone(UTC)
                    if at > now:
                        found.append(at)
        elif isinstance(when, WithAgent):
            other = _next_run(session, agent(when.agent), race_days, now)
            if other is not None:
                found.append(other)
    return min(found) if found else None


def _aware(dt: datetime) -> datetime:
    # SQLite hands back naive datetimes; Postgres keeps the zone.
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


def model_option(info: ModelInfo) -> ModelOptionOut:
    return ModelOptionOut(
        id=info.id,
        name=info.name,
        input_per_m=info.input_per_m,
        output_per_m=info.output_per_m,
        tools=info.tools,
    )


def _model_choice(spec: Agent, choices: dict, listed: dict[str, ModelInfo] | None) -> AgentModelOut | None:
    if spec.model_id is None or spec.model_setting is None or spec.default_model is None:
        return None
    row = choices.get(spec.key)
    info = listed.get(spec.model_id) if listed else None
    return AgentModelOut(
        id=spec.model_id,
        setting=spec.model_setting,
        default=spec.default_model,
        changed_at=_aware(row.updated_at) if row else None,
        suggested=[s for s in spec.suggested if listed is None or s in listed],
        needs_tools=spec.needs_tools,
        info=model_option(info) if info else None,
    )


def overview(
    session: Session, now: datetime | None = None, *, listed: dict[str, ModelInfo] | None = None
) -> AdminOverviewOut:
    """`listed`: OpenRouter's model list, fetched (and cached) when not given."""
    now = now or datetime.now(UTC)
    choices = model_choices(session)
    listed = listed if listed is not None else catalogue()
    wl = watchlist()
    meetings = watched_meetings(session)
    race_days = sorted({mt.date for mt in meetings})

    agent_rows = []
    for spec in agents({k: row.model for k, row in choices.items()}):
        last = last_run(session, spec.key)
        agent_rows.append(
            AgentOut(
                key=spec.key,
                name=spec.name,
                purpose=spec.purpose,
                how=spec.how,
                schedule=[describe_schedule(w) for w in spec.schedules],
                next_run=_next_run(session, spec, race_days, now),
                model=spec.model,
                model_choice=_model_choice(spec, choices, listed),
                web_search=spec.web_search,
                looks_at=spec.looks_at,
                reads=list(spec.reads),
                writes=list(spec.writes),
                prompt=spec.prompt,
                last_checked=_aware(last.started_at) if last else None,
                runs=[
                    AgentRunOut(
                        trigger=r.trigger,
                        started_at=_aware(r.started_at),
                        finished_at=_aware(r.finished_at) if r.finished_at else None,
                        status=r.status,
                        races=r.races,
                        result=r.result,
                        sites=r.sites or {},
                        error=r.error,
                        model=r.model,
                        tokens=r.tokens,
                        cost_usd=r.cost_usd,
                    )
                    for r in recent_runs(session, spec.key)
                ],
            )
        )

    loaded = {(mt.track.casefold(), mt.date): len(watched_races(mt)) for mt in meetings}
    if wl.entries is None:
        watching = [
            WatchOut(track=mt.track, date=mt.date, races=None, loaded_races=len(watched_races(mt)))
            for mt in meetings
        ]
    else:
        watching = [
            WatchOut(
                track=e.track,
                date=e.date,
                races=sorted(e.races) if e.races else None,
                loaded_races=loaded.get((e.track.casefold(), e.date), 0),
            )
            for e in wl.entries
        ]

    card = wl.card or settings.seed_file_path
    return AdminOverviewOut(
        agents=agent_rows,
        watching=watching,
        card=card.name if card else None,
        settings=[
            SettingOut(name="ODDS_SOURCE", value=settings.odds_source, about="Where odds come from"),
            SettingOut(
                name="OPENROUTER_MODEL",
                value=settings.openrouter_model,
                about="Default model for the odds agent and race notes",
            ),
            SettingOut(
                name="OPENROUTER_RESEARCH_MODEL",
                value=settings.openrouter_research_model,
                about="Default model for the tipster and field checker",
            ),
            SettingOut(
                name="OPENROUTER_WEB_SEARCH",
                value="on" if settings.openrouter_web_search else "off",
                about="Lets the odds agent search the web",
            ),
            SettingOut(
                name="OPENROUTER_API_KEY",
                value="set" if settings.openrouter_api_key else "not set",
                about="Needed for every AI agent",
            ),
            SettingOut(
                name="POLL_INTERVAL_SECONDS",
                value=str(settings.poll_interval_seconds),
                about="How often the odds agent runs",
            ),
            SettingOut(
                name="ODDS_CHECK_TIMES",
                value=settings.odds_check_times,
                about="Fixed times each race day to price the whole card",
            ),
            SettingOut(
                name="RACE_WINDOW_OPEN_MIN_BEFORE",
                value=str(settings.race_window_open_min_before),
                about="Minutes before a race that the odds agent starts checking it",
            ),
            SettingOut(
                name="MOVEMENT_THRESHOLD_PCT",
                value=f"{settings.movement_threshold_pct:g}",
                about="Price move that counts as a market move",
            ),
            SettingOut(name="TZ", value=settings.tz, about="Time zone for schedules"),
        ],
    )
