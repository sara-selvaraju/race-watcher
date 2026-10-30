from __future__ import annotations

import signal
import time
from datetime import UTC, datetime

from apscheduler.schedulers.background import BackgroundScheduler

from race_watcher.adapters import get_odds_source, get_prediction_engine, get_race_card_source
from race_watcher.core.config import settings
from race_watcher.core.logging import configure_logging, get_logger
from race_watcher.db.session import SessionLocal
from race_watcher.repositories import race_repo
from race_watcher.services.ingest import ingest_meetings
from race_watcher.services.predictions import run_predictions_for_race
from race_watcher.services.race_summary import has_jumped, summarize_all

configure_logging()
log = get_logger("worker")


def _ensure_meeting_loaded() -> None:
    with SessionLocal() as session:
        if race_repo.list_meetings_between(session, *settings.race_days):
            return
        log.info("worker.ingesting_seed", race_days=f"{settings.race_days[0]}..{settings.race_days[1]}")
        ingest_meetings(session, get_race_card_source())


def _refresh_predictions() -> int:
    """Re-rate runners in races still to run; returns how many races were re-rated."""
    engine = get_prediction_engine()
    now = datetime.now(UTC)
    rated = 0
    with SessionLocal() as session:
        for meeting in race_repo.list_meetings_between(session, *settings.race_days):
            for race in meeting.races:
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
        log.info("worker.idle", reason="no races left to run", race_days=f"{settings.race_days[0]}..{settings.race_days[1]}")
        return
    try:
        adapter = get_odds_source()
    except Exception as exc:  # missing API key etc. — keep the worker alive
        log.warning("worker.summary_adapter_unavailable", error=str(exc))
        return
    with SessionLocal() as session:
        result = summarize_all(session, adapter)
    log.info("worker.summaries", **result)


def main() -> None:
    log.info(
        "worker.boot",
        race_days=f"{settings.race_days[0]}..{settings.race_days[1]}",
        odds_source=settings.odds_source,
        prediction_engine=settings.prediction_engine,
        note="live polling disabled — use POST /api/v1/admin/refresh-odds on demand",
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
