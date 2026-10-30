from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.core.watchlist import watchlist
from race_watcher.db import models as m
from race_watcher.domain.models import DomainMeeting
from race_watcher.domain.ports import OddsSource
from race_watcher.repositories import alert_repo, price_repo
from race_watcher.services.movement import evaluate_movement
from race_watcher.services.watched import watched_meetings, watched_races

log = get_logger("poller")

def _meeting_window_utc(meeting: m.Meeting) -> tuple[datetime, datetime] | None:
    races = watched_races(meeting)
    if not races:
        return None
    starts = [r.start_time_local for r in races if r.start_time_local]
    if not starts:
        return None
    tz = ZoneInfo(meeting.timezone)
    first_utc = datetime.combine(meeting.date, min(starts), tzinfo=tz).astimezone(UTC)
    last_utc = datetime.combine(meeting.date, max(starts), tzinfo=tz).astimezone(UTC)
    return (
        first_utc - timedelta(minutes=settings.race_window_open_min_before),
        last_utc + timedelta(minutes=settings.race_window_close_min_after),
    )


def in_race_window(meeting: m.Meeting, now: datetime | None = None) -> bool:
    win = _meeting_window_utc(meeting)
    if win is None:
        return False
    now = now or datetime.now(UTC)
    return win[0] <= now <= win[1]


def poll_once(
    session: Session,
    odds: OddsSource,
    *,
    meeting_id: int | None = None,
    now: datetime | None = None,
    force: bool = False,
) -> dict:
    """One poll cycle across every meeting in the race-day window (or just `meeting_id`). Idempotent."""
    now = now or datetime.now(UTC)
    meetings = watched_meetings(session, meeting_id)
    if not meetings:
        log.warning("poller.no_meeting", watching=f"{watchlist().start}..{watchlist().end}")
        return {"snapshots": 0, "alerts": 0, "skipped": "no_meeting"}

    snapshots = alerts = 0
    for meeting in meetings:
        if not force and not in_race_window(meeting, now=now):
            log.info("poller.outside_window", track=meeting.track)
            continue
        result = _poll_meeting(session, odds, meeting, now=now, force=force)
        snapshots += result["snapshots"]
        alerts += result["alerts"]
    return {"snapshots": snapshots, "alerts": alerts, "meetings": len(meetings)}


def _domain_race_meeting(meeting: m.Meeting, race: m.Race) -> DomainMeeting:
    """The adapter's lightweight shape, holding just one race."""
    from race_watcher.domain.models import DomainRace
    from race_watcher.services.predictions import _to_domain_runner

    return DomainMeeting(
        track=meeting.track,
        date=meeting.date,
        timezone=meeting.timezone,
        races=(
            DomainRace(
                number=race.number,
                name=race.name,
                distance_m=race.distance_m,
                klass=race.klass,
                start_time_local=race.start_time_local,
                runners=tuple(_to_domain_runner(rn) for rn in race.runners),
            ),
        ),
    )


def races_to_price(meeting: m.Meeting, now: datetime, *, force: bool = False) -> list[m.Race]:
    """Watched races worth fetching odds for: still to run and, unless forced, jumping within
    RACE_WINDOW_OPEN_MIN_BEFORE minutes. Prices only matter in a race's build-up, so a race is
    fetched about 8 times (every 15 min for 2 hours) rather than all day."""
    from race_watcher.services.race_summary import has_jumped

    lead = timedelta(minutes=settings.race_window_open_min_before)
    tz = ZoneInfo(meeting.timezone)
    out = []
    for race in watched_races(meeting):
        if not race.runners or has_jumped(meeting, race, now):
            continue
        if not force and race.start_time_local is not None:
            start = datetime.combine(meeting.date, race.start_time_local, tzinfo=tz).astimezone(UTC)
            if now < start - lead:
                continue
        out.append(race)
    return out


def _poll_meeting(
    session: Session,
    odds: OddsSource,
    meeting: m.Meeting,
    *,
    now: datetime | None = None,
    force: bool = False,
) -> dict:
    now = now or datetime.now(UTC)
    races = races_to_price(meeting, now, force=force)
    if not races:
        return {"snapshots": 0, "alerts": 0}

    # One request per race: a whole day in one request (~130 runners) came back with only the
    # first race or two priced. Requests run a few at a time; DB writes stay on this thread.
    requests = [_domain_race_meeting(meeting, r) for r in races]  # ORM reads stay on this thread
    with ThreadPoolExecutor(max_workers=4) as pool:
        batches = list(pool.map(odds.fetch_prices, requests))
    prices = [p for batch in batches for p in batch]
    log.info(
        "poller.fetched",
        track=meeting.track,
        races=[r.number for r in races],
        priced=[len(b) for b in batches],
        source=odds.name,
    )

    # index runners by (race_number, runner_number)
    runner_index: dict[tuple[int, int], m.Runner] = {}
    for race in watched_races(meeting):
        for runner in race.runners:
            runner_index[(race.number, runner.number)] = runner

    threshold = Decimal(str(settings.movement_threshold_pct))
    snapshots_written = 0
    alerts_written = 0

    for p in prices:
        runner = runner_index.get((p.race_number, p.runner_number))
        if runner is None:
            continue

        # Moves only count against the same bookmaker's earlier prices: a change of source
        # isn't the market moving.
        prev = price_repo.latest_price(session, runner.id, source=p.source)
        baseline = price_repo.open_baseline_price(session, runner.id, source=p.source)

        price_repo.insert_price(
            session, runner_id=runner.id, source=p.source, price=p.price, taken_at=p.taken_at
        )
        snapshots_written += 1

        if prev is not None:
            dec = evaluate_movement(
                from_price=Decimal(prev.price), to_price=p.price, threshold_pct=threshold
            )
            if dec.alert and not alert_repo.recent_alert_for_runner(
                session, runner.id, since_minutes=15, baseline="previous"
            ):
                alert_repo.insert_alert(
                    session,
                    runner_id=runner.id,
                    from_price=Decimal(prev.price),
                    to_price=p.price,
                    pct_change=dec.pct_change,
                    direction=dec.direction,
                    baseline="previous",
                )
                alerts_written += 1

        if baseline is not None and baseline.id != (prev.id if prev else None):
            dec_open = evaluate_movement(
                from_price=Decimal(baseline.price), to_price=p.price, threshold_pct=threshold
            )
            if dec_open.alert and not alert_repo.recent_alert_for_runner(
                session, runner.id, since_minutes=60, baseline="open"
            ):
                alert_repo.insert_alert(
                    session,
                    runner_id=runner.id,
                    from_price=Decimal(baseline.price),
                    to_price=p.price,
                    pct_change=dec_open.pct_change,
                    direction=dec_open.direction,
                    baseline="open",
                )
                alerts_written += 1

    session.commit()
    log.info("poller.done", track=meeting.track, snapshots=snapshots_written, alerts=alerts_written)
    return {"snapshots": snapshots_written, "alerts": alerts_written}
