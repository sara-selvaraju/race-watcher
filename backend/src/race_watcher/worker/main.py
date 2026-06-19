from __future__ import annotations

import signal
import time

from apscheduler.schedulers.background import BackgroundScheduler

from race_watcher.adapters import get_odds_source, get_prediction_engine, get_race_card_source
from race_watcher.core.config import settings
from race_watcher.core.logging import configure_logging, get_logger
from race_watcher.db.session import SessionLocal
from race_watcher.repositories import race_repo
from race_watcher.services.ingest import ingest_meeting
from race_watcher.services.poller import poll_once
from race_watcher.services.predictions import run_predictions_for_race

configure_logging()
log = get_logger("worker")


def _ensure_meeting_loaded() -> None:
    with SessionLocal() as session:
        meeting = race_repo.get_meeting_by_date(session, settings.race_date)
        if meeting is not None:
            return
        log.info("worker.ingesting_seed", race_date=str(settings.race_date))
        ingest_meeting(session, get_race_card_source())


def _refresh_predictions() -> None:
    engine = get_prediction_engine()
    with SessionLocal() as session:
        meeting = race_repo.get_meeting_by_date(session, settings.race_date)
        if meeting is None:
            return
        for race in meeting.races:
            run_predictions_for_race(session, race, engine)
        session.commit()


def _poll_job() -> None:
    odds = get_odds_source()
    with SessionLocal() as session:
        try:
            poll_once(session, odds)
        except Exception as exc:
            log.error("worker.poll_failed", error=str(exc))


def main() -> None:
    log.info(
        "worker.boot",
        race_date=str(settings.race_date),
        poll_seconds=settings.poll_interval_seconds,
        threshold=settings.movement_threshold_pct,
        odds_source=settings.odds_source,
    )

    _ensure_meeting_loaded()
    _refresh_predictions()

    sched = BackgroundScheduler(timezone="UTC")
    sched.add_job(
        _poll_job,
        "interval",
        seconds=settings.poll_interval_seconds,
        id="poll",
        max_instances=1,
        coalesce=True,
    )
    sched.add_job(
        _refresh_predictions,
        "interval",
        minutes=30,
        id="predict",
        max_instances=1,
        coalesce=True,
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
