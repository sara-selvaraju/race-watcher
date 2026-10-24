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

configure_logging()
log = get_logger("worker")


def _ensure_meeting_loaded() -> None:
    with SessionLocal() as session:
        if race_repo.list_meetings_by_date(session, settings.race_date):
            return
        log.info("worker.ingesting_seed", race_date=str(settings.race_date))
        ingest_meetings(session, get_race_card_source())


def _refresh_predictions() -> None:
    engine = get_prediction_engine()
    with SessionLocal() as session:
        for meeting in race_repo.list_meetings_by_date(session, settings.race_date):
            for race in meeting.races:
                run_predictions_for_race(session, race, engine)
        session.commit()


def _refresh_summaries() -> None:
    """Re-rate, then rewrite notes for any upcoming race whose picks, prices or field changed."""
    from race_watcher.services.race_summary import summarize_all

    _refresh_predictions()
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
        race_date=str(settings.race_date),
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
