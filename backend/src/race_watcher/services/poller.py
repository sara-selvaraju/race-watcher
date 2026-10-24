from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy.orm import Session

from race_watcher.core.config import settings
from race_watcher.core.logging import get_logger
from race_watcher.db import models as m
from race_watcher.domain.models import DomainMeeting
from race_watcher.domain.ports import OddsSource
from race_watcher.repositories import alert_repo, price_repo, race_repo
from race_watcher.services.movement import evaluate_movement

log = get_logger("poller")

def _meeting_window_utc(meeting: m.Meeting) -> tuple[datetime, datetime] | None:
    if not meeting.races:
        return None
    starts = [r.start_time_local for r in meeting.races if r.start_time_local]
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
    """One poll cycle across every meeting on the race date (or just `meeting_id`). Idempotent."""
    now = now or datetime.now(UTC)
    meetings = race_repo.list_meetings_by_date(session, settings.race_date, meeting_id)
    if not meetings:
        log.warning("poller.no_meeting", race_date=str(settings.race_date))
        return {"snapshots": 0, "alerts": 0, "skipped": "no_meeting"}

    snapshots = alerts = 0
    for meeting in meetings:
        if not force and not in_race_window(meeting, now=now):
            log.info("poller.outside_window", track=meeting.track)
            continue
        result = _poll_meeting(session, odds, meeting)
        snapshots += result["snapshots"]
        alerts += result["alerts"]
    return {"snapshots": snapshots, "alerts": alerts, "meetings": len(meetings)}


def _poll_meeting(
    session: Session,
    odds: OddsSource,
    meeting: m.Meeting,
    domain_meeting: DomainMeeting | None = None,
) -> dict:

    if domain_meeting is None:
        # Adapter needs the lightweight domain shape; rebuild from DB if not supplied.
        from race_watcher.services.predictions import _to_domain_runner
        from race_watcher.domain.models import DomainMeeting as DM, DomainRace as DR

        domain_meeting = DM(
            track=meeting.track,
            date=meeting.date,
            timezone=meeting.timezone,
            races=tuple(
                DR(
                    number=r.number,
                    name=r.name,
                    distance_m=r.distance_m,
                    klass=r.klass,
                    start_time_local=r.start_time_local,
                    runners=tuple(_to_domain_runner(rn) for rn in r.runners),
                )
                for r in meeting.races
            ),
        )

    prices = odds.fetch_prices(domain_meeting)
    log.info("poller.fetched", count=len(prices), source=odds.name)

    # index runners by (race_number, runner_number)
    runner_index: dict[tuple[int, int], m.Runner] = {}
    for race in meeting.races:
        for runner in race.runners:
            runner_index[(race.number, runner.number)] = runner

    threshold = Decimal(str(settings.movement_threshold_pct))
    snapshots_written = 0
    alerts_written = 0

    for p in prices:
        runner = runner_index.get((p.race_number, p.runner_number))
        if runner is None:
            continue

        prev = price_repo.latest_price(session, runner.id)
        baseline = price_repo.open_baseline_price(session, runner.id)

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
