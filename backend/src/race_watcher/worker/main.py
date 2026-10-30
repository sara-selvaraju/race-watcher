from __future__ import annotations

import signal
import time
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.background import BackgroundScheduler

from race_watcher.adapters import get_odds_source, get_prediction_engine, get_race_card_source
from race_watcher.core.config import settings
from race_watcher.core.logging import configure_logging, get_logger
from race_watcher.core.watchlist import watchlist
from race_watcher.db.session import SessionLocal
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.poller import poll_once, poll_race_day
from race_watcher.services.predictions import run_predictions_for_race
from race_watcher.services.race_summary import has_jumped, summarize_all
from race_watcher.services.watched import watched_meetings, watched_races

configure_logging()
log = get_logger("worker")


def _watching() -> str:
    wl = watchlist()
    if wl.entries is None:
        return f"all races {wl.start}..{wl.end}"
    return ", ".join(
        f"{e.track} {e.date}" + (f" R{','.join(map(str, sorted(e.races)))}" if e.races else "")
        for e in wl.entries
    )


def _ensure_meeting_loaded() -> None:
    with SessionLocal() as session:
        if watched_meetings(session):
            return
        log.info("worker.ingesting_seed", watching=_watching())
        ingest_meetings(session, get_race_card_source())


def _refresh_predictions() -> int:
    """Re-rate runners in races still to run; returns how many races were re-rated."""
    engine = get_prediction_engine()
    now = datetime.now(UTC)
    rated = 0
    with SessionLocal() as session:
        for meeting in watched_meetings(session):
            for race in watched_races(meeting):
                if has_jumped(meeting, race, now):
                    continue
                run_predictions_for_race(session, race, engine)
                rated += 1
        session.commit()
    return rated


def _refresh_summaries() -> None:
    """Re-rate, then rewrite notes for any upcoming race whose picks, prices or field changed.
    Idle once every race on the card has jumped."""
    if not _refresh_predictions():
        log.info("worker.idle", reason="no races left to run", watching=_watching())
        return
    try:
        adapter = get_odds_source()
    except Exception as exc:  # missing API key etc. — keep the worker alive
        log.warning("worker.summary_adapter_unavailable", error=str(exc))
        return
    with SessionLocal() as session:
        result = summarize_all(session, adapter)
    log.info("worker.summaries", **result)


def _poll_odds() -> None:
    """Fetch live odds for every meeting whose race window is open.

    poll_once checks each meeting's window itself (2 hours before the first race to 15 minutes
    after the last), so outside race hours this does nothing and costs nothing. New prices
    feed the next _refresh_summaries run, which re-rates runners and rewrites notes.
    """
    try:
        adapter = get_odds_source()
    except Exception as exc:  # missing API key etc. — keep the worker alive
        log.warning("worker.odds_adapter_unavailable", error=str(exc))
        return
    with SessionLocal() as session:
        result = poll_once(session, adapter)
    log.info("worker.odds", **result)


def _odds_check() -> None:
    """Fixed-time check (ODDS_CHECK_TIMES): price every race on today's card, whatever its start."""
    try:
        adapter = get_odds_source()
    except Exception as exc:  # missing API key etc. — keep the worker alive
        log.warning("worker.odds_adapter_unavailable", error=str(exc))
        return
    today = datetime.now(ZoneInfo(settings.tz)).date()
    with SessionLocal() as session:
        result = poll_race_day(session, adapter, today)
    log.info("worker.odds_check", day=str(today), **result)


def main() -> None:
    log.info(
        "worker.boot",
        watching=_watching(),
        odds_source=settings.odds_source,
        prediction_engine=settings.prediction_engine,
        poll_every_min=settings.poll_interval_seconds // 60,
        odds_checks=settings.odds_check_times,
    )

    _ensure_meeting_loaded()
    _refresh_predictions()

    sched = BackgroundScheduler(timezone="UTC")
    # Re-rates every runner, then rewrites race notes. Cheap when nothing changed: unchanged
    # races are skipped on an inputs hash, so no LLM call.
    sched.add_job(
        _refresh_summaries,
        "interval",
        minutes=10,
        id="summaries",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    # Live odds on a timer. Only spends anything inside a meeting's race window.
    sched.add_job(
        _poll_odds,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="odds",
        max_instances=1,
        coalesce=True,
        next_run_time=datetime.now(UTC),
    )
    # Fixed daily checks, e.g. 09:15 Melbourne time. On days with no watched meeting they find
    # nothing to price and cost nothing.
    for hhmm in filter(None, (t.strip() for t in settings.odds_check_times.split(","))):
        hour, minute = (int(x) for x in hhmm.split(":"))
        sched.add_job(
            _odds_check,
            "cron",
            hour=hour,
            minute=minute,
            timezone=ZoneInfo(settings.tz),
            id=f"odds_check_{hour:02d}{minute:02d}",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=30 * 60,
        )
    sched.start()
    log.info("worker.scheduled")

    stop = False

    def _shutdown(*_: object) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    while not stop:
        time.sleep(1)

    log.info("worker.shutting_down")
    sched.shutdown(wait=False)


if __name__ == "__main__":
    main()
